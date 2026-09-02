"""Microsoft Agent Framework adapter for agentic-arena.

A single `agent_framework.Agent` with the shared search / calculator tools.

Notes specific to this framework:
  * `OpenAIChatClient` defaults to the OpenAI *Responses* API (`/v1/responses`).
    The arena gateway / mock server speaks Chat Completions, so this adapter uses
    `OpenAIChatCompletionClient` explicitly.
  * The framework is async-only. A fresh `AsyncOpenAI` client, agent, and event
    loop are built per item so the httpx client never outlives its loop.

Suspend/resume (`arena.types.ResumableRunner`) uses the framework's own
**tool-approval middleware**: the interrupt tool is declared
`@tool(approval_mode="always_require")`, `ToolApprovalMiddleware` queues the call
instead of running it, and the run comes back with `user_input_requests`
populated and no text. `resume` answers with
`request.to_function_approval_response(approved)` and runs again.

Two things about this mechanism are worth knowing, because they are why it looks
different from the other four:

  * It requires an `AgentSession`. The middleware refuses to run without one -
    approval bookkeeping lives in `session.state`, not in the agent.
  * `AgentSession` is a state container, **not** a conversation store. The
    transcript is the caller's problem, so `resume` feeds the previous leg's
    messages back in itself. That is also why `durable_state` is not supported
    here: see the note on `resume` below.
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


def search(query: str, k: int = 3) -> str:
    """Search a small knowledge base of general facts."""
    return _search(query, k)


def calculator(expr: str) -> str:
    """Evaluate a basic arithmetic expression such as '330 / 0.3048'."""
    return _calculator(expr)


def search_rooms(capacity: int, day: str) -> str:
    """List meeting rooms that seat at least `capacity` and are free on `day`."""
    return arena_tools.search_rooms(capacity, day)


def book_room(room_id: str) -> str:
    """Book a meeting room by id. Only call this after approval."""
    return arena_tools.book_room(room_id)


def _make_probe():
    """A ChatMiddleware that counts model calls and the tool calls they asked for.

    `response.messages` is not a reliable ledger here: with the approval
    middleware installed it collapses to the final turn, hiding the tool round
    that preceded the pause. Counting assistant messages therefore under-reported
    both `llm_calls` and `tool_calls`, which the usage-accounting gate catches.

    Intercepting at the chat layer counts exactly what crossed the wire, on every
    arena, whether or not the approval middleware is in play. It only observes -
    it never modifies the request.
    """
    from agent_framework import ChatMiddleware

    class _Probe(ChatMiddleware):
        def __init__(self) -> None:
            self.calls = 0
            self.tool_calls: list[dict[str, Any]] = []

        async def process(self, context: Any, call_next: Any) -> None:
            self.calls += 1
            await call_next()
            result = getattr(context, "result", None)
            for message in getattr(result, "messages", None) or []:
                for content in getattr(message, "contents", None) or []:
                    if getattr(content, "type", None) != "function_call":
                        continue
                    # Asking for permission (or checkpointing) is the pause, not
                    # an action taken - the other adapters do not log it either.
                    if content.name in arena_tools.SUSPEND_TOOLS:
                        continue
                    self.tool_calls.append({"name": content.name, "arguments": content.arguments})

    return _Probe()


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        # Import eagerly so a missing install degrades to "unavailable" at build
        # time, like the other adapters, rather than erroring on every item.
        import agent_framework  # noqa: F401
        import agent_framework.openai  # noqa: F401

        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        from agent_framework import tool as af_tool

        # `approval_mode="always_require"` is the native pause: the middleware
        # queues the call and surfaces it instead of executing the body.
        @af_tool(approval_mode="always_require")
        def request_approval(summary: str) -> str:
            """Ask a human to approve a consequential action before taking it."""
            return f"Approved: {summary}"

        @af_tool(approval_mode="always_require")
        def save_progress(note: str) -> str:
            """Checkpoint what you have gathered so far, then stop."""
            return f"Checkpointed: {note}"

        available = {
            "search": search,
            "calculator": calculator,
            "search_rooms": search_rooms,
            "book_room": book_room,
            "request_approval": request_approval,
            "save_progress": save_progress,
        }
        names = _tool_names(arena.tools)
        self.tools = [available[n] for n in names if n in available]
        self._pausable = any(n in names for n in arena_tools.SUSPEND_TOOLS)
        # The approval middleware is opt-in and needs a session; only arenas that
        # ask for a pause pay for either.
        self._durable = arena.durable

    def _build(self, probe: Any):
        """A fresh client + agent. Async-only, so this is per invocation."""
        from agent_framework import Agent, ChatOptions, ToolApprovalMiddleware
        from agent_framework.openai import OpenAIChatCompletionClient
        from openai import AsyncOpenAI

        client = OpenAIChatCompletionClient(
            model=self.config.model,
            async_client=AsyncOpenAI(base_url=self.config.base_url, api_key=self.config.api_key),
            # Without this the tool loop is uncapped: measured against a mock
            # that never stops calling tools, this adapter made 41 LLM calls on
            # a budget of 6. `max_iterations` counts tool-calling roundtrips and
            # the framework then emits one final text response on top, so N-1
            # roundtrips gives the same N total LLM calls the other adapters get.
            function_invocation_configuration={
                "max_iterations": max(1, self.config.max_tool_iterations - 1)
            },
        )
        return Agent(
            client,
            instructions=self.system_prompt,
            tools=self.tools,
            default_options=ChatOptions(temperature=0.0),
            middleware=([ToolApprovalMiddleware()] if self._pausable else []) + [probe],
        )

    def _result(self, response: Any, probe: Any) -> AgentResult:
        usage = getattr(response, "usage_details", None) or {}
        return AgentResult(
            output_text=response.text or "",
            tool_calls=list(probe.tool_calls),
            prompt_tokens=int(usage.get("input_token_count", 0) or 0),
            completion_tokens=int(usage.get("output_token_count", 0) or 0),
            llm_calls=probe.calls,
        )

    async def _run_async(self, prompt: str) -> AgentResult:
        from agent_framework import AgentSession

        probe = _make_probe()
        agent = self._build(probe)
        session = AgentSession() if self._pausable else None
        response = await agent.run(prompt, session=session) if session else await agent.run(prompt)
        self._session = session
        result = self._result(response, probe)

        pending = list(getattr(response, "user_input_requests", None) or [])
        if not pending:
            return result

        request = pending[0]
        call = getattr(request, "function_call", None)
        result.output_text = ""
        result.suspended = True
        result.suspend_request = str(getattr(call, "arguments", "") or "")
        # The runner itself carries the pause: `AgentSession` holds approval
        # bookkeeping but NOT the conversation, so the transcript has to come
        # back with us. It is kept in memory rather than serialised, which is
        # exactly what `durable_state` does not allow - see `resume`.
        # The conversation lives in the *session*, not in `response.messages`
        # (which holds only the final turn) and not in the agent. Carrying the
        # session object forward is what makes the resume see any history at all.
        self._paused = {"prompt": prompt, "messages": list(response.messages), "request": request}
        return result

    async def _resume_async(self, decision: str) -> AgentResult:
        from agent_framework import AgentSession, Message

        paused = getattr(self, "_paused", None)
        if not paused:
            return AgentResult(error="cannot resume: no paused run on this runner")

        answer = paused["request"].to_function_approval_response(decision != "deny")
        # The opening turn goes back as a plain string: `Message(contents=["..."])`
        # does not produce a user text turn.
        conversation = [
            paused["prompt"],
            *paused["messages"],
            Message(role="user", contents=[answer]),
        ]
        # Reuse the session from the paused leg. It carries both the approval
        # bookkeeping and the conversation; a fresh one arrives with neither, and
        # the resumed leg then re-asks the model from an empty transcript.
        session = getattr(self, "_session", None) or AgentSession()
        probe = _make_probe()
        response = await self._build(probe).run(conversation, session=session)
        return self._result(response, probe)

    def run(self, item: EvalItem) -> AgentResult:
        return asyncio.run(self._run_async(item.input))


class _ResumableRunner(_Runner):
    """`_Runner` plus the pause. Used for every pausable arena except a durable one.

    The split is deliberate rather than a flag. `durable_state` throws the runner
    away at the pause, and this pause cannot survive that: the conversation lives
    in the `AgentSession`, whose message store does not round-trip through JSON
    (it comes back as raw strings), and restoring the middleware's approval state
    into a rebuilt agent re-queues the same request instead of consuming the
    answer. Measured both ways, with and without the state restored.

    An adapter that keeps a `resume` it cannot honour would report 0/8 on
    `durable_state` and read as a broken framework. Not having the method at all
    is the honest signal, and the harness reports it as *unsupported*.
    """

    def resume(self, item: EvalItem, state: Any, decision: str) -> AgentResult:
        """Continue the paused run with the human's decision.

        `state` is ignored: the pause is held by this runner, not serialised into
        it, which is exactly the distinction `durable_state` exists to draw.
        """
        return asyncio.run(self._resume_async(decision))


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
        # A durable arena discards the runner at the pause, and this pause cannot
        # survive that - so it does not claim to. See `_ResumableRunner`.
        if arena.durable:
            return _Runner(arena, config)
        return _ResumableRunner(arena, config)
