"""LangGraph adapter for agentic-arena.

Uses `langgraph.prebuilt.create_react_agent` with an OpenAI-compatible chat model
pointed at the shared gateway (real provider in live mode, the mock server in mock
mode). The shared `search` / `calculator` tools are wrapped as LangChain tools
without changing their behaviour.
"""

from __future__ import annotations

from typing import Any

from arena.config import ArenaConfig
from arena.tools import calculator as _calculator
from arena.tools import names_for as _tool_names
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem


def _make_tools(names: list[str]) -> list[Any]:
    from langchain_core.tools import tool

    @tool
    def search(query: str, k: int = 3) -> str:
        """Search a small knowledge base of general facts."""
        return _search(query, k)

    @tool
    def calculator(expr: str) -> str:
        """Evaluate a basic arithmetic expression such as '330 / 0.3048'."""
        return _calculator(expr)

    available = {"search": search, "calculator": calculator}
    return [available[name] for name in names if name in available]


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent

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
        self.agent = create_react_agent(model, _make_tools(_tool_names(arena.tools)))

    def run(self, item: EvalItem) -> AgentResult:
        state = self.agent.invoke(
            {
                "messages": [
                    ("system", self.system_prompt),
                    ("user", item.input),
                ]
            },
            # One tool round = two graph steps (model node + tool node), so the
            # recursion limit must be 2x the LLM-call budget to match the other
            # adapters. The old +2 bought this framework an extra model call.
            config={"recursion_limit": 2 * self.config.max_tool_iterations},
        )
        messages = state["messages"]

        tool_calls: list[dict[str, Any]] = []
        prompt_tokens = completion_tokens = llm_calls = 0
        final_text = ""
        for msg in messages:
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
    name = "langgraph"

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return f"langgraph {version('langgraph')}"
        except PackageNotFoundError:
            return "langgraph (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
