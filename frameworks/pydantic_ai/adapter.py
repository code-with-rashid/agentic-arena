"""Pydantic AI adapter for agentic-arena.

A single `pydantic_ai.Agent` with the shared search / calculator tools. Pydantic AI
talks to any OpenAI-compatible endpoint through `OpenAIChatModel` +
`OpenAIProvider(base_url=..., api_key=...)`, so the shared gateway (real provider in
live mode, the stdlib mock server in mock mode) drives it unchanged.
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


class _Runner:
    def __init__(self, config: ArenaConfig) -> None:
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
        from pydantic_ai.providers.openai import OpenAIProvider

        self.config = config
        model = OpenAIChatModel(
            config.model,
            provider=OpenAIProvider(base_url=config.base_url, api_key=config.api_key),
        )
        self._agent = Agent(
            model,
            system_prompt=SYSTEM_PROMPT,
            model_settings=OpenAIChatModelSettings(temperature=0.0),
            retries=config.max_tool_iterations,
        )

        @self._agent.tool_plain
        def search(query: str, k: int = 3) -> str:
            """Search a small knowledge base of general facts."""
            return _search(query, k)

        @self._agent.tool_plain
        def calculator(expr: str) -> str:
            """Evaluate a basic arithmetic expression such as '330 / 0.3048'."""
            return _calculator(expr)

    def run(self, item: EvalItem) -> AgentResult:
        from pydantic_ai.messages import ToolCallPart

        result = self._agent.run_sync(item.input)

        tool_calls: list[dict[str, Any]] = []
        for message in result.all_messages():
            for part in getattr(message, "parts", []):
                if isinstance(part, ToolCallPart):
                    tool_calls.append({"name": part.tool_name, "arguments": part.args})

        usage = result.usage
        return AgentResult(
            output_text=str(result.output),
            tool_calls=tool_calls,
            prompt_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            llm_calls=int(getattr(usage, "requests", 0) or 0),
        )


class Adapter:
    name = "pydantic_ai"

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        for dist in ("pydantic-ai", "pydantic-ai-slim"):
            try:
                return f"{dist} {version(dist)}"
            except PackageNotFoundError:
                continue
        return "pydantic-ai (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(config)
