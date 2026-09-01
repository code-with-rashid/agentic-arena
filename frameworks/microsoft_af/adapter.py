"""Microsoft Agent Framework adapter for agentic-arena.

A single `agent_framework.Agent` with the shared search / calculator tools.

Notes specific to this framework:
  * `OpenAIChatClient` defaults to the OpenAI *Responses* API (`/v1/responses`).
    The arena gateway / mock server speaks Chat Completions, so this adapter uses
    `OpenAIChatCompletionClient` explicitly.
  * The framework is async-only. A fresh `AsyncOpenAI` client, agent, and event
    loop are built per item so the httpx client never outlives its loop.
"""

from __future__ import annotations

import asyncio
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


def search(query: str, k: int = 3) -> str:
    """Search a small knowledge base of general facts."""
    return _search(query, k)


def calculator(expr: str) -> str:
    """Evaluate a basic arithmetic expression such as '330 / 0.3048'."""
    return _calculator(expr)


class _Runner:
    def __init__(self, config: ArenaConfig) -> None:
        # Import eagerly so a missing install degrades to "unavailable" at build
        # time, like the other adapters, rather than erroring on every item.
        import agent_framework  # noqa: F401
        import agent_framework.openai  # noqa: F401

        self.config = config

    async def _run_async(self, prompt: str) -> AgentResult:
        from agent_framework import Agent, ChatOptions
        from agent_framework.openai import OpenAIChatCompletionClient
        from openai import AsyncOpenAI

        client = OpenAIChatCompletionClient(
            model=self.config.model,
            async_client=AsyncOpenAI(base_url=self.config.base_url, api_key=self.config.api_key),
        )
        agent = Agent(
            client,
            instructions=INSTRUCTIONS,
            tools=[search, calculator],
            default_options=ChatOptions(temperature=0.0),
        )
        response = await agent.run(prompt)

        tool_calls: list[dict[str, Any]] = []
        llm_calls = 0
        for message in response.messages:
            if getattr(message, "role", None) == "assistant":
                llm_calls += 1
            for content in getattr(message, "contents", []):
                if getattr(content, "type", None) == "function_call":
                    tool_calls.append({"name": content.name, "arguments": content.arguments})

        usage = getattr(response, "usage_details", None) or {}
        return AgentResult(
            output_text=response.text or "",
            tool_calls=tool_calls,
            prompt_tokens=int(usage.get("input_token_count", 0) or 0),
            completion_tokens=int(usage.get("output_token_count", 0) or 0),
            llm_calls=llm_calls,
        )

    def run(self, item: EvalItem) -> AgentResult:
        return asyncio.run(self._run_async(item.input))


class Adapter:
    name = "microsoft_af"

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return f"agent-framework-core {version('agent-framework-core')}"
        except PackageNotFoundError:
            return "agent-framework (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(config)
