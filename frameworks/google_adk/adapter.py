"""Google ADK adapter for agentic-arena.

A single `LlmAgent` driven by `InMemoryRunner`. ADK is Gemini-first, so reaching
the shared OpenAI-compatible gateway goes through its LiteLLM backend:

    LiteLlm(model=f"openai/{model}", api_base=..., api_key=...)

which is why `litellm` is a hard requirement of this adapter rather than an
optional extra — see requirements.txt for what that costs.

Two things this framework gets right that most of the others do not:

  * `RunConfig(max_llm_calls=N)` is a real loop cap. Measured against a mock that
    never stops asking for tools, a budget of N produces exactly N requests on the
    wire - no off-by-one, no uncapped default. It raises
    `LlmCallsLimitExceededError` rather than silently returning a blank answer.
  * Per-event `usage_metadata` sums exactly to what the gateway served, so the
    cost this adapter reports needs no reconstruction.
"""

from __future__ import annotations

import asyncio
from typing import Any

from arena import tools as arena_tools
from arena.config import ArenaConfig
from arena.tools import calculator as _calculator
from arena.tools import names_for as _tool_names
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem

# ADK builds each tool's schema from the signature and the Google-style
# docstring, so the `Args:` blocks below are load-bearing, not decoration.


def search(query: str) -> str:
    """Search a small knowledge base of general facts.

    Args:
        query: What to look up.
    """
    return _search(query)


def calculator(expr: str) -> str:
    """Evaluate a basic arithmetic expression such as '330 / 0.3048'.

    Args:
        expr: The arithmetic expression to evaluate.
    """
    return _calculator(expr)


def search_rooms(capacity: int, day: str) -> str:
    """List meeting rooms that seat at least `capacity` and are free on `day`.

    Args:
        capacity: How many people the room must seat.
        day: Day of the week, e.g. 'tuesday'.
    """
    return arena_tools.search_rooms(capacity, day)


def book_room(room_id: str) -> str:
    """Book a meeting room by id. Only call this after approval.

    Args:
        room_id: The room id, e.g. 'R3'.
    """
    return arena_tools.book_room(room_id)


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        # Import eagerly so a missing install degrades to "unavailable" at build
        # time, like the other adapters, rather than erroring on every item.
        import google.adk  # noqa: F401
        from google.adk.models.lite_llm import LiteLlm  # noqa: F401

        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        available = {
            "search": search,
            "calculator": calculator,
            "search_rooms": search_rooms,
            "book_room": book_room,
        }
        self.tools = [available[n] for n in _tool_names(arena.tools) if n in available]

    def _build(self) -> Any:
        from google.adk.agents import LlmAgent
        from google.adk.models.lite_llm import LiteLlm
        from google.adk.runners import InMemoryRunner

        model = LiteLlm(
            model=f"openai/{self.config.model}",
            api_base=self.config.base_url,
            api_key=self.config.api_key,
            temperature=0.0,
        )
        agent = LlmAgent(
            name="arena_agent",
            model=model,
            instruction=self.system_prompt,
            tools=self.tools,
        )
        return InMemoryRunner(agent=agent, app_name="arena")

    async def _run_async(self, prompt: str) -> AgentResult:
        from google.adk.agents.invocation_context import LlmCallsLimitExceededError
        from google.adk.agents.run_config import RunConfig
        from google.genai import types

        runner = self._build()
        session = await runner.session_service.create_session(app_name="arena", user_id="arena")

        text = ""
        tool_calls: list[dict[str, Any]] = []
        prompt_tokens = completion_tokens = llm_calls = 0
        error: str | None = None

        message = types.Content(role="user", parts=[types.Part(text=prompt)])
        stream = runner.run_async(
            user_id="arena",
            session_id=session.id,
            new_message=message,
            # A real loop cap: a budget of N yields exactly N requests.
            run_config=RunConfig(max_llm_calls=self.config.max_tool_iterations),
        )
        try:
            async for event in stream:
                usage = getattr(event, "usage_metadata", None)
                if usage is not None:
                    prompt_tokens += int(getattr(usage, "prompt_token_count", 0) or 0)
                    completion_tokens += int(getattr(usage, "candidates_token_count", 0) or 0)
                    llm_calls += 1
                content = getattr(event, "content", None)
                for part in (getattr(content, "parts", None) or []) if content else []:
                    call = getattr(part, "function_call", None)
                    if call is not None:
                        tool_calls.append({"name": call.name, "arguments": dict(call.args or {})})
                    part_text = getattr(part, "text", None)
                    if part_text:
                        text = part_text
        except LlmCallsLimitExceededError as exc:
            # Reported rather than swallowed: the other adapters surface a spent
            # budget as an error too, and `resilience` reads it.
            error = f"{type(exc).__name__}: {exc}"

        return AgentResult(
            output_text=text,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            llm_calls=llm_calls,
            error=None if text else error,
        )

    def run(self, item: EvalItem) -> AgentResult:
        return asyncio.run(self._run_async(item.input))


class Adapter:
    name = "google_adk"

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return f"google-adk {version('google-adk')}"
        except PackageNotFoundError:
            return "google-adk (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
