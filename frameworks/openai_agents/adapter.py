"""OpenAI Agents SDK adapter for agentic-arena.

A single `agents.Agent` with the shared search / calculator tools. The SDK is
pointed at the shared gateway by handing it an `AsyncOpenAI` client with our
`base_url` / `api_key` and wrapping it in `OpenAIChatCompletionsModel`, so the
stdlib mock server stands in for a real provider in mock mode.

Tracing is disabled: by default the SDK tries to upload traces to OpenAI, which
would fail (and leak) against the mock or a third-party gateway.

Suspend/resume (`arena.types.ResumableRunner`) uses the SDK's own **approval
interruptions**: the interrupt tool is declared `needs_approval=True`, the run
comes back with `final_output is None` and a `ToolApprovalItem` in
`result.to_state().get_interruptions()`, and `resume` calls `approve`/`reject` on
the restored state. `RunState.to_json()` / `from_json()` serialise the whole run,
so the same path also satisfies `durable_state`, where the harness discards the
runner and only JSON survives.
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


def _make_tools(names: list[str]) -> list[Any]:
    """Signatures, wording and parameter descriptions track `arena.tools.specs_for`.

    The SDK emits `strict: true`, which forces *every* property into `required`
    even where the arena gave one a default. That is a framework property rather
    than an adapter choice, and it is a finding in docs/tool-schemas.md.
    """
    from agents import function_tool

    @function_tool
    def search(
        query: Annotated[str, Field(description="What to look up.")],
        k: Annotated[int, Field(description="How many snippets.")] = 3,
    ) -> str:
        """Search a knowledge base of general facts. Returns up to k text snippets."""
        return _search(query, k)

    @function_tool
    def calculator(expr: Annotated[str, Field(description="Arithmetic expression.")]) -> str:
        """Evaluate a basic arithmetic expression, e.g. '330 / 0.3048'."""
        return _calculator(expr)

    @function_tool
    def search_rooms(capacity: int, day: str) -> str:
        """List meeting rooms that seat at least `capacity` and are free on `day`."""
        return arena_tools.search_rooms(capacity, day)

    @function_tool
    def book_room(room_id: str) -> str:
        """Book a meeting room by id. Only call this after approval."""
        return arena_tools.book_room(room_id)

    # `needs_approval` is the native pause: the SDK stops the run and surfaces a
    # ToolApprovalItem instead of executing the body.
    @function_tool(needs_approval=True)
    def request_approval(summary: str) -> str:
        """Ask a human to approve a consequential action before taking it."""
        return f"Approved: {summary}"

    @function_tool(needs_approval=True)
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
        client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.request_timeout_s,
        )
        names = _tool_names(arena.tools)
        self._pausable = any(n in names for n in arena_tools.SUSPEND_TOOLS)
        self._agent = Agent(
            name="arena-agent",
            instructions=self.system_prompt,
            model=OpenAIChatCompletionsModel(model=config.model, openai_client=client),
            model_settings=ModelSettings(temperature=0.0),
            tools=_make_tools(names),
        )

    def _result(self, result: Any, seen: dict[str, int]) -> AgentResult:
        """Build a result from the work done since `seen`.

        A resumed run reports `new_items` and `usage` **cumulatively** — leg two
        comes back holding leg one's numbers too. The harness sums across legs, so
        without subtracting here every paused item would report roughly double its
        real cost, and still pass.
        """
        items = result.new_items[seen.get("items", 0) :]
        tool_calls: list[dict[str, Any]] = []
        for run_item in items:
            if type(run_item).__name__ != "ToolCallItem":
                continue
            raw = run_item.raw_item
            name = getattr(raw, "name", "")
            # Asking for permission is the pause, not an action taken.
            if name in arena_tools.SUSPEND_TOOLS:
                continue
            tool_calls.append({"name": name, "arguments": getattr(raw, "arguments", "")})

        usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
        out = AgentResult(
            output_text=str(result.final_output or ""),
            tool_calls=tool_calls,
            prompt_tokens=max(
                0, int(getattr(usage, "input_tokens", 0) or 0) - seen.get("input", 0)
            ),
            completion_tokens=max(
                0, int(getattr(usage, "output_tokens", 0) or 0) - seen.get("output", 0)
            ),
            llm_calls=max(0, int(getattr(usage, "requests", 0) or 0) - seen.get("requests", 0)),
        )
        if not self._pausable:
            return out

        state = result.to_state()
        interruptions = state.get_interruptions()
        if not interruptions:
            return out

        out.output_text = ""
        out.suspended = True
        out.suspend_request = str(getattr(interruptions[0], "name", ""))
        # RunState.to_json() is a plain dict, so this crosses `durable_state`'s
        # JSON gap intact - the SDK serialises the whole run, not just messages.
        out.resume_state = {
            "state": state.to_json(),
            "seen": {
                "items": len(result.new_items),
                "input": int(getattr(usage, "input_tokens", 0) or 0),
                "output": int(getattr(usage, "output_tokens", 0) or 0),
                "requests": int(getattr(usage, "requests", 0) or 0),
            },
        }
        return out

    def run(self, item: EvalItem) -> AgentResult:
        from agents import Runner

        result = Runner.run_sync(self._agent, item.input, max_turns=self.config.max_tool_iterations)
        return self._result(result, seen={})

    def resume(self, item: EvalItem, state: Any, decision: str) -> AgentResult:
        import asyncio

        from agents import Runner
        from agents.run_state import RunState

        if not isinstance(state, dict) or "state" not in state:
            return AgentResult(error=f"cannot resume: unusable state {type(state).__name__}")
        restored = asyncio.run(RunState.from_json(self._agent, state["state"]))
        for interruption in restored.get_interruptions():
            if decision == "deny":
                restored.reject(interruption)
            else:
                restored.approve(interruption)
        result = Runner.run_sync(self._agent, restored, max_turns=self.config.max_tool_iterations)
        return self._result(result, seen=dict(state.get("seen", {})))


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
