"""LangGraph adapter for agentic-arena, wired as a *real* three-role pipeline.

This is the multi-agent contrast entry for the `multi_agent` arena. `langgraph`
(the single-agent adapter) role-plays researcher, writer and editor inside one
agent loop; this one gives each role its own node in a `StateGraph`:

    START -> researcher <-> tools -> writer -> editor -> END

The three nodes share one `MessagesState`, which is what a LangGraph supervisor
pipeline actually looks like: every stage sees the accumulated conversation, and
each stage adds its own role instruction on top of the arena's task prompt.

The point of the entry is cost, not quality. In mock mode the scripted turns are
identical for every adapter, so a pipeline cannot produce a *better* brief here —
it can only show what the structure costs in LLM calls and prompt tokens against
the single-agent entry running the same items. Mock mode cannot measure the
benefit of delegation; it can measure its overhead exactly. See
docs/multi-agent.md.

Fairness notes:

  * Same arena, same eval set, same tools, same shared gateway as every other
    entry. `arena.system_prompt` goes to every node verbatim, with one role line
    appended - the contract test that forbids hard-coded task instructions still
    applies to this adapter.
  * The iteration budget is per *item*, not per agent. Three roles divide one
    `max_tool_iterations` between them rather than getting one each, or the
    comparison would be against an adapter allowed to spend more.
"""

from __future__ import annotations

from typing import Annotated, Any

from arena.config import ArenaConfig
from arena.tools import calculator as _calculator
from arena.tools import names_for as _tool_names
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem

# Each role gets the arena's task prompt plus one line saying which part of it is
# theirs. Kept here, next to the adapter, so the wording is inspectable - the
# arena spec owns the task, this file owns only the division of labour.
ROLES = {
    "researcher": (
        "You are the researcher on this pipeline. Use the `search` tool to gather "
        "the facts the brief needs. Do not write the brief yourself."
    ),
    "writer": (
        "You are the writer on this pipeline. Using only the facts already "
        "gathered above, write the brief. Reply with the brief and nothing else."
    ),
    "editor": (
        "You are the editor on this pipeline. Check the draft above against the "
        "task and reply with the final brief, revised if needed and unchanged if "
        "not. Reply with the brief and nothing else."
    ),
}


def _make_tools(names: list[str]) -> list[Any]:
    from langchain_core.tools import tool

    @tool
    def search(
        query: Annotated[str, "What to look up."],
        k: Annotated[int, "How many snippets."] = 3,
    ) -> str:
        """Search a knowledge base of general facts. Returns up to k text snippets."""
        return _search(query, k)

    @tool
    def calculator(expr: Annotated[str, "Arithmetic expression."]) -> str:
        """Evaluate a basic arithmetic expression, e.g. '330 / 0.3048'."""
        return _calculator(expr)

    available = {"search": search, "calculator": calculator}
    return [available[name] for name in names if name in available]


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        from langchain_core.messages import SystemMessage
        from langchain_openai import ChatOpenAI
        from langgraph.graph import END, START, MessagesState, StateGraph
        from langgraph.prebuilt import ToolNode, tools_condition

        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        model = ChatOpenAI(
            model=config.model,
            base_url=config.base_url,
            api_key=config.api_key,
            temperature=0.0,
            timeout=config.request_timeout_s,
            max_retries=1,
        )
        tools = _make_tools(_tool_names(arena.tools))
        researcher_model = model.bind_tools(tools) if tools else model

        def _node(role: str, bound: Any) -> Any:
            def run(state: MessagesState) -> dict[str, list[Any]]:
                # The arena prompt is re-sent by every stage rather than carried
                # in the shared state: each node is a separate agent with its own
                # instruction, and that repetition is part of what the structure
                # costs. Measuring it away would flatter the pipeline.
                prompt = SystemMessage(content=f"{self.system_prompt}\n\n{ROLES[role]}")
                return {"messages": [bound.invoke([prompt] + list(state["messages"]))]}

            return run

        graph = StateGraph(MessagesState)
        graph.add_node("researcher", _node("researcher", researcher_model))
        graph.add_node("writer", _node("writer", model))
        graph.add_node("editor", _node("editor", model))
        graph.add_edge(START, "researcher")
        if tools:
            graph.add_node("tools", ToolNode(tools))
            # `tools_condition` routes back to the researcher while it is still
            # calling tools, and onward to the writer once it stops.
            graph.add_conditional_edges(
                "researcher", tools_condition, {"tools": "tools", END: "writer"}
            )
            graph.add_edge("tools", "researcher")
        else:
            graph.add_edge("researcher", "writer")
        graph.add_edge("writer", "editor")
        graph.add_edge("editor", END)
        self.agent = graph.compile()

    def _config(self) -> dict[str, Any]:
        # One tool round is two graph steps, and the writer and editor are one
        # step each, so the budget converts the same way the single-agent adapter
        # converts it. Three roles share one item budget; they do not get one each.
        return {"recursion_limit": 2 * self.config.max_tool_iterations}

    def run(self, item: EvalItem) -> AgentResult:
        from langchain_core.messages import HumanMessage

        try:
            state = self.agent.invoke(
                {"messages": [HumanMessage(content=item.input)]}, config=self._config()
            )
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            return AgentResult(error=f"{type(exc).__name__}: {exc}")

        tool_calls: list[dict[str, Any]] = []
        prompt_tokens = completion_tokens = llm_calls = 0
        final_text = ""
        for msg in state.get("messages", []):
            usage = getattr(msg, "usage_metadata", None)
            if usage:
                prompt_tokens += int(usage.get("input_tokens", 0))
                completion_tokens += int(usage.get("output_tokens", 0))
                llm_calls += 1
            for call in getattr(msg, "tool_calls", None) or []:
                tool_calls.append({"name": call.get("name", ""), "arguments": call.get("args", {})})
            if msg.__class__.__name__ == "AIMessage" and getattr(msg, "content", ""):
                final_text = msg.content if isinstance(msg.content, str) else str(msg.content)

        return AgentResult(
            output_text=final_text,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            llm_calls=llm_calls,
        )


class Adapter:
    name = "langgraph_multi"
    # A contrast entry, not a general-purpose adapter: `--framework all` runs it
    # only on the arena it was built to contrast on. Naming it explicitly still
    # works anywhere. See arena.registry.frameworks_for_arena.
    arenas = ("multi_agent",)

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return f"langgraph {version('langgraph')} (3-role pipeline)"
        except PackageNotFoundError:
            return "langgraph (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
