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
from arena.tools import names_for as _tool_names
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem


def _make_tools(names: list[str]) -> list[Any]:
    from agents import function_tool

    @function_tool
    def search(query: str, k: int = 3) -> str:
        """Search a small knowledge base of general facts."""
        return _search(query, k)

    @function_tool
    def calculator(expr: str) -> str:
        """Evaluate a basic arithmetic expression such as '330 / 0.3048'."""
        return _calculator(expr)

    available = {"search": search, "calculator": calculator}
    return [available[name] for name in names if name in available]


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        from agents import (
            Agent,
            AsyncOpenAI,
            ModelSettings,
            OpenAIChatCompletionsModel,
            set_tracing_disabled,
        )

        set_tracing_disabled(True)
        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        client = AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)
        self._agent = Agent(
            name="arena-agent",
            instructions=self.system_prompt,
            model=OpenAIChatCompletionsModel(model=config.model, openai_client=client),
            model_settings=ModelSettings(temperature=0.0),
            tools=_make_tools(_tool_names(arena.tools)),
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
        return _Runner(arena, config)
