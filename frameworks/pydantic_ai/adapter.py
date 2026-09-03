"""Pydantic AI adapter for agentic-arena.

A single `pydantic_ai.Agent` with the shared tools. Pydantic AI talks to any
OpenAI-compatible endpoint through `OpenAIChatModel` +
`OpenAIProvider(base_url=..., api_key=...)`, so the shared gateway (real provider in
live mode, the stdlib mock server in mock mode) drives it unchanged.

Suspend/resume (`arena.types.ResumableRunner`) uses Pydantic AI's own **deferred
tools**: the interrupt tool raises `CallDeferred`, the run comes back with a
`DeferredToolRequests` output instead of a string, and `resume` continues with
`deferred_tool_results`. The conversation is carried across as JSON via
`ModelMessagesTypeAdapter`, which is what lets it also satisfy `durable_state` —
the harness discards the runner there, so nothing in memory survives.
"""

from __future__ import annotations

from typing import Annotated, Any

# Guarded: every framework here depends on pydantic, but the harness itself has
# zero runtime deps and CI's lint job installs none of them - an adapter module
# must still import cleanly there. The annotation below is only evaluated when a
# runner is built, by which point the framework (and pydantic) is present.
try:
    from pydantic import Field
except ImportError:  # pragma: no cover - adapter is unbuildable without it anyway
    Field = None  # type: ignore[assignment]

from arena import tools as arena_tools
from arena.config import ArenaConfig
from arena.tools import calculator as _calculator
from arena.tools import names_for as _tool_names
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        from openai import AsyncOpenAI
        from pydantic_ai import Agent, CallDeferred, DeferredToolRequests
        from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
        from pydantic_ai.providers.openai import OpenAIProvider
        from pydantic_ai.usage import UsageLimits

        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        model = OpenAIChatModel(
            config.model,
            # `OpenAIProvider(base_url=...)` builds its own client with the
            # library default timeout, so the shared `request_timeout_s` would be
            # ignored. Handing it a client is the only way to set it here.
            provider=OpenAIProvider(
                openai_client=AsyncOpenAI(
                    base_url=config.base_url,
                    api_key=config.api_key,
                    timeout=config.request_timeout_s,
                )
            ),
        )
        names = _tool_names(arena.tools)
        # Only widen the output type for arenas that actually ask for a pause:
        # `[str, DeferredToolRequests]` changes what a finished run returns, and
        # every other arena expects a plain string.
        self._pausable = any(n in names for n in arena_tools.SUSPEND_TOOLS)
        output_type: Any = [str, DeferredToolRequests] if self._pausable else str
        self._agent = Agent(
            model,
            system_prompt=self.system_prompt,
            model_settings=OpenAIChatModelSettings(temperature=config.temperature),
            output_type=output_type,
        )
        # `Agent(retries=...)` is a tool/output-validation retry budget, NOT an
        # agent-loop cap — setting it from max_tool_iterations left this adapter
        # effectively uncapped (it ran to the library's default request_limit of
        # 50). The loop cap is a per-run usage limit.
        self._limits = UsageLimits(request_limit=config.max_tool_iterations)

        if "search" in names:
            # Signatures, wording and parameter descriptions track
            # `arena.tools.specs_for`. Pydantic AI reads a parameter description
            # from `Field`, not from the docstring - see docs/tool-schemas.md.
            @self._agent.tool_plain
            def search(
                query: Annotated[str, Field(description="What to look up.")],
                k: Annotated[int, Field(description="How many snippets.")] = 3,
            ) -> str:
                """Search a knowledge base of general facts. Returns up to k text snippets."""
                return _search(query, k)

        if "calculator" in names:

            @self._agent.tool_plain
            def calculator(
                expr: Annotated[str, Field(description="Arithmetic expression.")],
            ) -> str:
                """Evaluate a basic arithmetic expression, e.g. '330 / 0.3048'."""
                return _calculator(expr)

        if "search_rooms" in names:

            @self._agent.tool_plain
            def search_rooms(
                capacity: Annotated[int, Field(description="People to seat.")],
                day: Annotated[str, Field(description="Day of the week, e.g. 'tuesday'.")],
            ) -> str:
                """List meeting rooms that seat at least `capacity` and are free on `day`."""
                return arena_tools.search_rooms(capacity, day)

        if "book_room" in names:

            @self._agent.tool_plain
            def book_room(room_id: Annotated[str, Field(description="Room id, e.g. 'R3'.")]) -> str:
                """Book a meeting room by id. Only call this after approval."""
                return arena_tools.book_room(room_id)

        if "request_approval" in names:

            @self._agent.tool_plain
            def request_approval(
                summary: Annotated[str, Field(description="What you want approved.")],
            ) -> str:
                """Ask a human to approve a consequential action before you take it.

                Call this and stop; you will be told the decision.
                """
                # The native pause. Raising CallDeferred makes the run finish with a
                # DeferredToolRequests output instead of executing this body.
                raise CallDeferred

        if "save_progress" in names:

            @self._agent.tool_plain
            def save_progress(
                note: Annotated[str, Field(description="What you have established so far.")],
            ) -> str:
                """Checkpoint what you have gathered so far, then stop.

                You will be resumed and can carry on from where you left off.
                """
                raise CallDeferred

    def _result(self, result: Any, seen: int) -> AgentResult:
        """Build a result from the messages added since `seen`.

        Slicing matters: a resumed run returns the *whole* conversation, and the
        harness sums cost across legs, so counting from zero twice would report
        every tool call on a paused item twice.
        """
        from pydantic_ai import DeferredToolRequests
        from pydantic_ai.messages import ModelMessagesTypeAdapter, ToolCallPart

        history = result.all_messages()
        tool_calls: list[dict[str, Any]] = []
        for message in history[seen:]:
            for part in getattr(message, "parts", []):
                if isinstance(part, ToolCallPart):
                    # Asking for permission (or checkpointing) is the pause, not
                    # an action taken - the other adapters do not log it either.
                    if part.tool_name in arena_tools.SUSPEND_TOOLS:
                        continue
                    tool_calls.append({"name": part.tool_name, "arguments": part.args})

        usage = result.usage
        out = AgentResult(
            tool_calls=tool_calls,
            prompt_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            llm_calls=int(getattr(usage, "requests", 0) or 0),
        )

        requests = result.output
        if not isinstance(requests, DeferredToolRequests):
            out.output_text = str(result.output)
            return out

        pending = list(requests.calls) + list(requests.approvals)
        out.suspended = True
        out.suspend_request = str(getattr(pending[0], "args", "")) if pending else ""
        # Plain JSON on purpose: `durable_state` round-trips this through
        # json.dumps and rebuilds the runner, so anything not in here is gone.
        out.resume_state = {
            "history": ModelMessagesTypeAdapter.dump_json(history).decode("utf-8"),
            "call_ids": [c.tool_call_id for c in requests.calls],
            "approval_ids": [c.tool_call_id for c in requests.approvals],
            "seen": len(history),
        }
        return out

    def run(self, item: EvalItem) -> AgentResult:
        return self._result(self._agent.run_sync(item.input, usage_limits=self._limits), seen=0)

    def resume(self, item: EvalItem, state: Any, decision: str) -> AgentResult:
        from pydantic_ai import DeferredToolResults
        from pydantic_ai.messages import ModelMessagesTypeAdapter

        if not isinstance(state, dict) or "history" not in state:
            return AgentResult(error=f"cannot resume: unusable state {type(state).__name__}")
        history = ModelMessagesTypeAdapter.validate_json(state["history"])
        results = DeferredToolResults(
            calls={cid: f"Decision: {decision}." for cid in state.get("call_ids", [])},
            approvals={cid: decision != "deny" for cid in state.get("approval_ids", [])},
        )
        result = self._agent.run_sync(
            message_history=history,
            deferred_tool_results=results,
            usage_limits=self._limits,
        )
        return self._result(result, seen=int(state.get("seen", 0)))


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
        return _Runner(arena, config)
