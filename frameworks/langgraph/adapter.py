"""LangGraph adapter for agentic-arena.

Uses `langgraph.prebuilt.create_react_agent` with an OpenAI-compatible chat model
pointed at the shared gateway (real provider in live mode, the mock server in mock
mode). The shared `search` / `calculator` tools are wrapped as LangChain tools
without changing their behaviour.

Suspend/resume (`arena.types.ResumableRunner`) is implemented **natively**: the
`request_approval` tool calls `langgraph.types.interrupt`, which pauses the graph
and checkpoints it, and `resume` continues the same thread with
`Command(resume=decision)`. Nothing about the transcript is reconstructed by hand
— that is the distinction from the `vanilla` baseline's emulated pause.
"""

from __future__ import annotations

import contextlib
import tempfile
from contextlib import ExitStack
from pathlib import Path
from typing import Annotated, Any

from arena import tools as arena_tools
from arena.config import ArenaConfig
from arena.tools import calculator as _calculator
from arena.tools import names_for as _tool_names
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem


def _make_tools(names: list[str]) -> list[Any]:
    """Signatures, wording and parameter descriptions track `arena.tools.specs_for`.

    They are not this adapter's to choose. LangChain reads a parameter
    description only from `Annotated`, not from the docstring, so without the
    annotations below this adapter sent bare types where the arena had described
    every argument - part of why it measured leanest on the wire. See
    docs/tool-schemas.md.
    """
    from langchain_core.tools import tool
    from langgraph.types import interrupt

    @tool
    def search(
        query: Annotated[str, "What to look up."],
        k: Annotated[int, "How many snippets."] = 3,
    ) -> str:
        """Search a knowledge base of general facts. Returns up to k text snippets."""
        return _search(query, k)

    @tool
    def calculator(expr: Annotated[str, "Arithmetic expression."]) -> str:
        """Evaluate a basic arithmetic expression, e.g. '330 / 0.3048'."""
        return _calculator(expr)

    @tool
    def search_rooms(
        capacity: Annotated[int, "People to seat."],
        day: Annotated[str, "Day of the week, e.g. 'tuesday'."],
    ) -> str:
        """List meeting rooms that seat at least `capacity` and are free on `day`."""
        return arena_tools.search_rooms(capacity, day)

    @tool
    def book_room(room_id: Annotated[str, "Room id, e.g. 'R3'."]) -> str:
        """Book a meeting room by id. Only call this after approval."""
        return arena_tools.book_room(room_id)

    @tool
    def request_approval(summary: Annotated[str, "What you want approved."]) -> str:
        """Ask a human to approve a consequential action before you take it.

        Call this and stop; you will be told the decision.
        """
        # The native pause: LangGraph checkpoints the graph here and `invoke`
        # returns with `__interrupt__` set. On resume, this call returns the
        # decision the harness injected and the graph carries on from this point.
        decision = interrupt({"request": summary})
        return f"Decision: {decision}."

    @tool
    def save_progress(note: Annotated[str, "What you have established so far."]) -> str:
        """Checkpoint what you have gathered so far, then stop.

        You will be resumed and can carry on from where you left off.
        """
        # Same primitive, different arena. In `durable_state` the harness throws
        # the runner away here, so the checkpoint has to be on disk for the graph
        # to still exist when a fresh runner reconnects to the same thread.
        decision = interrupt({"request": note})
        return f"Resumed: {decision}."

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
        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent

        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        model = ChatOpenAI(
            model=config.model,
            base_url=config.base_url,
            api_key=config.api_key,
            temperature=0.0,
            timeout=config.request_timeout_s,
            max_retries=1,
        )
        # `interrupt` needs somewhere to checkpoint, and a checkpointer needs a
        # thread id, so both only appear for arenas that actually ask for a pause.
        self._pausable = any(name in (arena.tools or []) for name in arena_tools.SUSPEND_TOOLS)
        self._stack = ExitStack()
        checkpointer = None
        if self._pausable and arena.durable:
            # A durable arena discards this runner at the pause, so an in-memory
            # saver would take the graph with it. SqliteSaver writes to the
            # harness-owned checkpoint dir, which the next runner reopens.
            from langgraph.checkpoint.sqlite import SqliteSaver

            # Never fall back to the working directory: a contract test builds
            # this adapter with no checkpoint_dir set, and a stray sqlite file in
            # the repo root is the kind of thing that gets committed by accident.
            base = config.checkpoint_dir or tempfile.mkdtemp(prefix="arena-langgraph-")
            store = Path(base) / "langgraph.sqlite"
            store.parent.mkdir(parents=True, exist_ok=True)
            checkpointer = self._stack.enter_context(SqliteSaver.from_conn_string(str(store)))
        elif self._pausable:
            from langgraph.checkpoint.memory import MemorySaver

            checkpointer = MemorySaver()
        self.agent = create_react_agent(
            model, _make_tools(_tool_names(arena.tools)), checkpointer=checkpointer
        )
        self._threads = 0

    def _config_for(self, item: EvalItem) -> dict[str, Any]:
        # One tool round = two graph steps (model node + tool node), so the
        # recursion limit must be 2x the LLM-call budget to match the other
        # adapters. The old +2 bought this framework an extra model call.
        cfg: dict[str, Any] = {"recursion_limit": 2 * self.config.max_tool_iterations}
        if self._pausable:
            self._threads += 1
            cfg["configurable"] = {"thread_id": f"{item.id}-{self._threads}"}
        return cfg

    def __del__(self) -> None:  # pragma: no cover - best-effort cleanup
        with contextlib.suppress(Exception):
            self._stack.close()

    def _result(
        self, state: dict[str, Any], cfg: dict[str, Any], counted: list[str]
    ) -> AgentResult:
        """Build a result from the messages not already counted on an earlier leg.

        The harness sums cost across legs, so each message must be counted once
        and only once. What `invoke` hands back is **not the same shape in both
        pause arenas**, which is why this counts by message id rather than by
        position:

          * `human_in_the_loop` (in-memory saver, same runner) returns the *whole
            thread* — counting from zero twice would double every token.
          * `durable_state` (on-disk saver, runner rebuilt) returns only the
            *new* messages — and an index-based `seen` slice then discarded all
            of leg two, under-reporting the run by a whole LLM call while every
            correctness check still passed.

        Message ids are stable across a resume and unique within a thread, so the
        set of already-counted ids is exact for both shapes. A message with no id
        is counted rather than dropped: over-reporting cost is the safer error.
        """
        all_messages = state.get("messages", [])
        already = set(counted)
        messages = [m for m in all_messages if (getattr(m, "id", None) or "") not in already]

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
                # Asking permission is the pause, not an action taken - the
                # baseline does not log it either, and the arena's
                # `no_tool_before_suspend` check compares the two.
                if call.get("name") in arena_tools.SUSPEND_TOOLS:
                    continue
                tool_calls.append({"name": call.get("name", ""), "arguments": call.get("args", {})})
            if msg.__class__.__name__ == "AIMessage" and getattr(msg, "content", ""):
                final_text = msg.content if isinstance(msg.content, str) else str(msg.content)

        interrupts = state.get("__interrupt__") or ()
        result = AgentResult(
            output_text=final_text,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            llm_calls=llm_calls,
        )
        if not interrupts:
            return result

        payload = getattr(interrupts[0], "value", interrupts[0])
        request = payload.get("request", "") if isinstance(payload, dict) else str(payload)
        result.suspended = True
        result.suspend_request = str(request)
        # Every id seen so far, so the next leg counts only what it adds. Plain
        # JSON on purpose: `durable_state` round-trips this through json.dumps.
        result.resume_state = {
            "config": cfg,
            "counted": [str(getattr(m, "id", "") or "") for m in all_messages],
        }
        return result

    def run(self, item: EvalItem) -> AgentResult:
        cfg = self._config_for(item)
        state = self.agent.invoke(
            {"messages": [("system", self.system_prompt), ("user", item.input)]},
            config=cfg,
        )
        return self._result(state, cfg, counted=[])

    def resume(self, item: EvalItem, state: Any, decision: str) -> AgentResult:
        from langgraph.types import Command

        if not isinstance(state, dict) or "config" not in state:
            return AgentResult(error=f"cannot resume: unusable state {type(state).__name__}")
        cfg = state["config"]
        new_state = self.agent.invoke(Command(resume=decision), config=cfg)
        return self._result(new_state, cfg, counted=list(state.get("counted", [])))


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
        return _Runner(arena, config)
