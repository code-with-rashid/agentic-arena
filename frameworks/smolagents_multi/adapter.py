"""smolagents wired as a *managed-agent* pipeline. A third shape of delegation.

`multi_agent` now carries three mechanisms, and they are genuinely different:

  * **Structural** (`vanilla_multi`, `langgraph_multi`) — the wiring always
    visits researcher, writer and editor. Delegation is a property of the graph.
  * **Model-decided, speaker swap** (`openai_agents_multi`) — each agent holds a
    `transfer_to_<agent>` tool. A handoff hands the *same* conversation to the
    next agent, which continues it under its own instructions.
  * **Model-decided, sub-agent as tool** (this entry) — a sub-agent is advertised
    as an ordinary tool named after itself. Calling it runs a whole nested agent
    with its **own fresh conversation**, and its answer comes back as the tool's
    return value. The speaker never changes.

    researcher --writer(task)--> writer --editor(task)--> editor

That third one is not a cosmetic difference. Every delegator here has to produce
its own final answer *after* the sub-agent returns, because the sub-agent's reply
is a tool result rather than the end of the run — so each level of nesting costs
an extra model call that a handoff does not. docs/multi-agent.md has the numbers.

Fairness notes, same as the other pipeline entries:

  * `arena.system_prompt` goes to every agent verbatim with one role line
    appended; the arena owns the task, this file owns only the division of labour.
  * Only the researcher gets tools. Giving them to the writer and editor would
    make this three researchers rather than a pipeline.
  * The iteration budget is per *item*, divided between the agents rather than
    granted to each.
"""

from __future__ import annotations

from typing import Any

from arena import tools as arena_tools
from arena.config import ArenaConfig
from arena.tools import names_for as _tool_names
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem

# Deliberately the same role wording as frameworks/{vanilla,langgraph,
# openai_agents}_multi, so the only thing separating the four pipeline entries is
# the mechanism.
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

# `managed_agents` builds the sub-agent's tool schema from these, so they are
# what the manager's model reads when deciding to delegate.
DESCRIPTIONS = {
    "writer": "Writes the brief from the facts the researcher has gathered.",
    "editor": "Revises a draft brief and returns the final version.",
}


def _make_tools(names: list[str]) -> list[Any]:
    from smolagents import tool

    @tool
    def search(query: str) -> str:
        """Search a small knowledge base of general facts.

        Args:
            query: What to look up.
        """
        return _search(query)

    available = {"search": search}
    return [available[name] for name in names if name in available]


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        from smolagents import OpenAIServerModel, ToolCallingAgent

        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        model = OpenAIServerModel(
            model_id=config.model,
            api_base=config.base_url,
            api_key=config.api_key,
            client_kwargs={"timeout": config.request_timeout_s},
            temperature=0.0,
        )
        # smolagents makes one model call beyond `max_steps`, same as the
        # single-agent entry. Each agent in the chain gets a small budget rather
        # than the whole per-item one, so a stuck sub-agent cannot spend the
        # pipeline's entire allowance on its own.
        steps = max(1, config.max_tool_iterations // 2)

        def agent(role: str, **kw: Any) -> Any:
            return ToolCallingAgent(
                model=model,
                instructions=f"{self.system_prompt}\n\n{ROLES[role]}",
                max_steps=steps,
                verbosity_level=0,
                **kw,
            )

        # Built back to front: a sub-agent must exist before it can be managed.
        # The editor manages nobody, which is what ends the chain - the mock
        # serves it the brief because it is the first agent with no delegate left
        # to call.
        editor = agent("editor", tools=[], name="editor", description=DESCRIPTIONS["editor"])
        writer = agent(
            "writer",
            tools=[],
            name="writer",
            description=DESCRIPTIONS["writer"],
            managed_agents=[editor],
        )
        self._agent = agent(
            "researcher", tools=_make_tools(_tool_names(arena.tools)), managed_agents=[writer]
        )
        self._stages = [self._agent, writer, editor]

    def _collect(self, agent: Any, result: AgentResult) -> None:
        """Fold one agent's memory into the result.

        Every stage is counted, not just the manager's. A nested sub-agent runs
        its own model calls against the same gateway, and leaving them out would
        report a pipeline as costing what a single agent costs - the exact class
        of under-reporting `tests/test_usage_accounting.py` exists to catch.
        """
        for step in getattr(getattr(agent, "memory", None), "steps", []) or []:
            usage = getattr(step, "token_usage", None)
            if usage is not None:
                result.prompt_tokens += int(getattr(usage, "input_tokens", 0) or 0)
                result.completion_tokens += int(getattr(usage, "output_tokens", 0) or 0)
                result.llm_calls += 1
            step_error = getattr(step, "error", None)
            if step_error is not None:
                result.error = f"{type(step_error).__name__}: {step_error}"
            for call in getattr(step, "tool_calls", None) or []:
                name = str(getattr(call, "name", ""))
                # `final_answer` is how this framework returns a value, and a
                # sub-agent's name is how it delegates. Neither is a tool the
                # arena granted, so neither may satisfy a `tool_used` check or
                # count against `max_tool_calls`.
                if name == arena_tools.FINAL_ANSWER_TOOL or name in DESCRIPTIONS:
                    continue
                result.tool_calls.append(
                    {"name": name, "arguments": getattr(call, "arguments", {})}
                )

    def run(self, item: EvalItem) -> AgentResult:
        output = self._agent.run(item.input, reset=True)
        result = AgentResult(output_text=str(output or ""))
        for agent in self._stages:
            self._collect(agent, result)
        if result.output_text:
            result.error = None
        return result


class Adapter:
    name = "smolagents_multi"
    # `managed_agents` advertises each sub-agent as a tool named after itself, so
    # there is no prefix to match on the way `transfer_to_*` is matched. Declaring
    # the names here is what exempts them from the "only the arena's tools" rule -
    # see arena.tools.is_control_tool for why that exemption is sound and what
    # bounds it. They stay fully counted in prompt-size accounting.
    delegates = tuple(DESCRIPTIONS)
    # A pipeline, not a general-purpose entry: scoped so `--framework all` keeps
    # it out of the single-agent overhead table, where 3x would read as this
    # library being wasteful rather than as a different structure being measured.
    arenas = ("multi_agent",)

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return f"smolagents {version('smolagents')} (managed agents)"
        except PackageNotFoundError:
            return "smolagents (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
