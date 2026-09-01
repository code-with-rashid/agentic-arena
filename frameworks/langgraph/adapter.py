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
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem

SYSTEM_PROMPT = (
    "You are a careful assistant with two tools: `search` (a small factual knowledge "
    "base) and `calculator` (basic arithmetic). Use `search` for any fact you are not "
    "certain of and `calculator` for any arithmetic. When you have enough information, "
    "answer directly and concisely, making sure the key number or fact appears in your "
    "final message."
)


def _make_tools() -> list[Any]:
    from langchain_core.tools import tool

    @tool
    def search(query: str, k: int = 3) -> str:
        """Search a small knowledge base of general facts."""
        return _search(query, k)

    @tool
    def calculator(expr: str) -> str:
        """Evaluate a basic arithmetic expression such as '330 / 0.3048'."""
        return _calculator(expr)

    return [search, calculator]


class _Runner:
    def __init__(self, config: ArenaConfig) -> None:
        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent

        self.config = config
        model = ChatOpenAI(
            model=config.model,
            base_url=config.base_url,
            api_key=config.api_key,
            temperature=0.0,
            timeout=config.request_timeout_s,
            max_retries=1,
        )
        self.agent = create_react_agent(model, _make_tools())

    def run(self, item: EvalItem) -> AgentResult:
        state = self.agent.invoke(
            {
                "messages": [
                    ("system", SYSTEM_PROMPT),
                    ("user", item.input),
                ]
            },
            config={"recursion_limit": 2 * self.config.max_tool_iterations + 2},
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
        return _Runner(config)
