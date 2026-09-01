"""OpenAI Agents SDK adapter for agentic-arena.

A single `agents.Agent` with the shared search / calculator tools. The SDK is
pointed at the shared gateway by handing it an `AsyncOpenAI` client with our
`base_url` / `api_key` and wrapping it in `OpenAIChatCompletionsModel`, so the
stdlib mock server stands in for a real provider in mock mode.

Tracing is disabled: by default the SDK tries to upload traces to OpenAI, which
would fail (and leak) against the mock or a third-party gateway.
"""

from __future__ import annotations

from typing import Any

from arena.config import ArenaConfig
from arena.tools import calculator as _calculator
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem

INSTRUCTIONS = (
    "You are a careful assistant with two tools: `search` (a small factual knowledge "
    "base) and `calculator` (basic arithmetic). Use `search` for any fact you are not "
    "certain of and `calculator` for any arithmetic. When you have enough information, "
    "answer directly and concisely, making sure the key number or fact appears in your "
    "final message."
)


def _make_tools() -> list[Any]:
    from agents import function_tool

    @function_tool
    def search(query: str, k: int = 3) -> str:
        """Search a small knowledge base of general facts."""
        return _search(query, k)

    @function_tool
    def calculator(expr: str) -> str:
        """Evaluate a basic arithmetic expression such as '330 / 0.3048'."""
        return _calculator(expr)

    return [search, calculator]


class _Runner:
    def __init__(self, config: ArenaConfig) -> None:
        from agents import (
            Agent,
            AsyncOpenAI,
            ModelSettings,
            OpenAIChatCompletionsModel,
            set_tracing_disabled,
        )

        set_tracing_disabled(True)
        self.config = config
        client = AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)
        self._agent = Agent(
            name="arena-agent",
            instructions=INSTRUCTIONS,
            model=OpenAIChatCompletionsModel(model=config.model, openai_client=client),
            model_settings=ModelSettings(temperature=0.0),
            tools=_make_tools(),
        )

    def run(self, item: EvalItem) -> AgentResult:
        from agents import Runner

        result = Runner.run_sync(self._agent, item.input, max_turns=self.config.max_tool_iterations)

        tool_calls: list[dict[str, Any]] = []
        for run_item in result.new_items:
            if type(run_item).__name__ != "ToolCallItem":
                continue
            raw = run_item.raw_item
            tool_calls.append(
                {"name": getattr(raw, "name", ""), "arguments": getattr(raw, "arguments", "")}
            )

        usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
        return AgentResult(
            output_text=str(result.final_output or ""),
            tool_calls=tool_calls,
            prompt_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            llm_calls=int(getattr(usage, "requests", 0) or 0),
        )


class Adapter:
    name = "openai_agents"

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return f"openai-agents {version('openai-agents')}"
        except PackageNotFoundError:
            return "openai-agents (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(config)
