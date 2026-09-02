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
from pathlib import Path
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


def request_approval(summary: str) -> dict[str, str]:
    """Ask a human to approve a consequential action before taking it.

    Args:
        summary: What you want approved.
    """
    # Wrapped in LongRunningFunctionTool, so this "pending" marker is what the
    # framework reports while the real answer is supplied later, by call id.
    return {"status": "pending"}


def save_progress(note: str) -> dict[str, str]:
    """Checkpoint what you have gathered so far, then stop.

    Args:
        note: What you have established so far.
    """
    return {"status": "pending"}


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        # Import eagerly so a missing install degrades to "unavailable" at build
        # time, like the other adapters, rather than erroring on every item.
        import google.adk  # noqa: F401
        from google.adk.models.lite_llm import LiteLlm  # noqa: F401

        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        from google.adk.tools import LongRunningFunctionTool

        available: dict[str, Any] = {
            "search": search,
            "calculator": calculator,
            "search_rooms": search_rooms,
            "book_room": book_room,
            # A long-running tool is how ADK expresses "the answer comes later":
            # the run reports the call in `long_running_tool_ids` and the real
            # result is supplied afterwards against the same call id.
            "request_approval": LongRunningFunctionTool(request_approval),
            "save_progress": LongRunningFunctionTool(save_progress),
        }
        names = _tool_names(arena.tools)
        self.tools = [available[n] for n in names if n in available]
        self._pausable = any(n in names for n in arena_tools.SUSPEND_TOOLS)
        self._durable = arena.durable
        self._checkpoint_dir = config.checkpoint_dir
        self._memory_service: Any = None

    def _session_service(self) -> Any:
        """In-memory normally; on disk when the arena will throw the runner away.

        `durable_state` rebuilds the adapter at the pause, so an in-memory session
        would take the conversation with it. `DatabaseSessionService` writes to
        the harness-owned checkpoint dir, which the next runner reopens - the same
        shape as LangGraph's `SqliteSaver`.
        """
        import tempfile

        from google.adk.sessions import DatabaseSessionService, InMemorySessionService

        if not self._durable:
            # Cached for the life of this runner. `resume` builds a fresh Runner,
            # and a fresh InMemorySessionService with it would arrive empty - the
            # conversation lives in the service, not in the Runner. On a durable
            # arena that does not matter, because the store is on disk.
            if self._memory_service is None:
                self._memory_service = InMemorySessionService()
            return self._memory_service
        # Never fall back to the working directory: a contract test builds this
        # adapter with no checkpoint_dir, and a stray sqlite file in the repo root
        # is the kind of thing that gets committed by accident.
        base = Path(self._checkpoint_dir or tempfile.mkdtemp(prefix="arena-adk-"))
        base.mkdir(parents=True, exist_ok=True)
        # Forward slashes and an *async* driver: a Windows path breaks the URL,
        # and plain `sqlite://` fails with "the asyncio extension requires an
        # async driver". aiosqlite ships with google-adk.
        url = (base / "adk_sessions.sqlite").as_posix()
        return DatabaseSessionService(db_url=f"sqlite+aiosqlite:///{url}")

    def _build(self) -> Any:
        from google.adk.agents import LlmAgent
        from google.adk.models.lite_llm import LiteLlm
        from google.adk.runners import Runner

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
        return Runner(app_name="arena", agent=agent, session_service=self._session_service())

    async def _consume(self, runner: Any, session_id: str, message: Any) -> AgentResult:
        """Drive one leg, stopping at the pause if there is one."""
        import contextlib

        from google.adk.agents.invocation_context import LlmCallsLimitExceededError
        from google.adk.agents.run_config import RunConfig

        result = AgentResult()
        pending: tuple[str, str, str] | None = None

        stream = runner.run_async(
            user_id="arena",
            session_id=session_id,
            new_message=message,
            # A real loop cap: a budget of N yields exactly N requests.
            run_config=RunConfig(max_llm_calls=self.config.max_tool_iterations),
        )
        try:
            async for event in stream:
                usage = getattr(event, "usage_metadata", None)
                if usage is not None:
                    result.prompt_tokens += int(getattr(usage, "prompt_token_count", 0) or 0)
                    result.completion_tokens += int(
                        getattr(usage, "candidates_token_count", 0) or 0
                    )
                    result.llm_calls += 1
                content = getattr(event, "content", None)
                long_running = getattr(event, "long_running_tool_ids", None) or set()
                for part in (getattr(content, "parts", None) or []) if content else []:
                    call = getattr(part, "function_call", None)
                    if call is not None:
                        if call.id in long_running:
                            # THE PAUSE. ADK reports the call but does not stop on
                            # its own: left running, it hands the model a
                            # "pending" result and the model books the room
                            # anyway, which is exactly what
                            # `no_tool_before_suspend` exists to catch. Breaking
                            # out of the stream is what makes the pause real.
                            args = dict(call.args or {})
                            pending = (
                                call.id,
                                call.name,
                                str(args.get("summary") or args.get("note") or ""),
                            )
                            break
                        result.tool_calls.append(
                            {"name": call.name, "arguments": dict(call.args or {})}
                        )
                    part_text = getattr(part, "text", None)
                    if part_text:
                        result.output_text = part_text
                if pending:
                    break
        except LlmCallsLimitExceededError as exc:
            # Reported rather than swallowed: the other adapters surface a spent
            # budget as an error too, and `resilience` reads it.
            result.error = f"{type(exc).__name__}: {exc}"
        finally:
            # Abandoning an async generator mid-iteration leaves ADK's contextvars
            # unwound; closing it explicitly keeps that noise out of the run.
            with contextlib.suppress(Exception):
                await stream.aclose()

        if pending:
            call_id, call_name, summary = pending
            result.output_text = ""
            result.suspended = True
            result.suspend_request = summary
            # Three strings, so this crosses `durable_state`'s JSON gap intact.
            # Everything else the next leg needs is in the session store on disk.
            result.resume_state = {
                "session_id": session_id,
                "call_id": call_id,
                "call_name": call_name,
            }
        return result

    async def _run_async(self, prompt: str) -> AgentResult:
        from google.genai import types

        runner = self._build()
        session = await runner.session_service.create_session(app_name="arena", user_id="arena")
        message = types.Content(role="user", parts=[types.Part(text=prompt)])
        return await self._consume(runner, session.id, message)

    async def _resume_async(self, state: dict[str, Any], decision: str) -> AgentResult:
        from google.genai import types

        runner = self._build()
        # Supplying the deferred result against the same call id is ADK's own
        # resume path; nothing about the transcript is reconstructed by hand.
        message = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=state["call_id"],
                        name=state["call_name"],
                        response={"result": f"Decision: {decision}."},
                    )
                )
            ],
        )
        return await self._consume(runner, state["session_id"], message)

    def run(self, item: EvalItem) -> AgentResult:
        return asyncio.run(self._run_async(item.input))

    def resume(self, item: EvalItem, state: Any, decision: str) -> AgentResult:
        if not isinstance(state, dict) or "call_id" not in state:
            return AgentResult(error=f"cannot resume: unusable state {type(state).__name__}")
        return asyncio.run(self._resume_async(state, decision))


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
