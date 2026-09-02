"""smolagents adapter for agentic-arena.

A single `ToolCallingAgent` with the shared tools, pointed at the arena gateway
through `OpenAIServerModel(api_base=..., api_key=...)`.

Two things about smolagents differ from the other native-tool-calling adapters,
and both are framework facts rather than adapter choices:

  * It advertises its own `final_answer` tool and **ends the loop by calling it**.
    A plain content reply is read as "not finished yet", so the mock server
    renders scripted content turns as a `final_answer` call for clients that
    advertise one (see `arena.llm.mockserver._wants_final_answer_tool`).
  * It feeds tool results back as **`user`** messages, not `role: "tool"`.

Neither grants the agent a capability the arena withheld, so neither breaks the
fairness rules - see docs/methodology.md section 3.
"""

from __future__ import annotations

from typing import Any

from arena import tools as arena_tools
from arena.config import ArenaConfig
from arena.tools import calculator as _calculator
from arena.tools import names_for as _tool_names
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem


def _make_tools(names: list[str]) -> list[Any]:
    """Signatures and wording track `arena.tools.specs_for` exactly.

    They are not this adapter's to choose. The arena declares the tools, and a
    framework offered a narrower one is being handed a different task - this file
    used to declare `search(query)`, silently withholding the `k` parameter the
    arena grants. See docs/tool-schemas.md.
    """
    from smolagents import tool

    @tool
    def search(query: str, k: int = 3) -> str:
        """Search a knowledge base of general facts. Returns up to k text snippets.

        Args:
            query: What to look up.
            k: How many snippets.
        """
        return _search(query, k)

    @tool
    def calculator(expr: str) -> str:
        """Evaluate a basic arithmetic expression, e.g. '330 / 0.3048'.

        Args:
            expr: Arithmetic expression.
        """
        return _calculator(expr)

    @tool
    def search_rooms(capacity: int, day: str) -> str:
        """List meeting rooms that seat at least `capacity` and are free on `day`.

        Args:
            capacity: People to seat.
            day: Day of the week, e.g. 'tuesday'.
        """
        return arena_tools.search_rooms(capacity, day)

    @tool
    def book_room(room_id: str) -> str:
        """Book a meeting room by id. Only call this after approval.

        Args:
            room_id: Room id, e.g. 'R3'.
        """
        return arena_tools.book_room(room_id)

    available = {
        "search": search,
        "calculator": calculator,
        "search_rooms": search_rooms,
        "book_room": book_room,
    }
    return [available[name] for name in names if name in available]


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        from smolagents import OpenAIServerModel, ToolCallingAgent

        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        model = OpenAIServerModel(
            model_id=config.model,
            api_base=config.base_url,
            api_key=config.api_key,
            # smolagents builds the client itself; `client_kwargs` is the only
            # way through to it, and without this the shared budget is ignored.
            client_kwargs={"timeout": config.request_timeout_s},
            temperature=0.0,
        )
        self._agent = ToolCallingAgent(
            tools=_make_tools(_tool_names(arena.tools)),
            model=model,
            instructions=self.system_prompt,
            # Measured, not assumed: smolagents makes one model call *beyond*
            # `max_steps` (a final attempt once the budget is spent), so N - 1
            # steps yields the same N total LLM calls the other adapters get.
            max_steps=max(1, config.max_tool_iterations - 1),
            verbosity_level=0,
        )

    def run(self, item: EvalItem) -> AgentResult:
        output = self._agent.run(item.input, reset=True)

        tool_calls: list[dict[str, Any]] = []
        prompt_tokens = completion_tokens = llm_calls = 0
        error: str | None = None
        for step in getattr(self._agent.memory, "steps", []):
            usage = getattr(step, "token_usage", None)
            if usage is not None:
                # Per-step usage rather than `agent.monitor`: a step whose tool
                # call failed still cost a model call, and the monitor is reset
                # by `run(reset=True)` in a way that is easy to mis-subtract.
                prompt_tokens += int(getattr(usage, "input_tokens", 0) or 0)
                completion_tokens += int(getattr(usage, "output_tokens", 0) or 0)
                llm_calls += 1
            step_error = getattr(step, "error", None)
            if step_error is not None:
                error = f"{type(step_error).__name__}: {step_error}"
            for call in getattr(step, "tool_calls", None) or []:
                name = getattr(call, "name", "")
                # `final_answer` is how this framework returns, not a tool the
                # arena granted; logging it would break every max_tool_calls
                # check and inflate the comparison against other adapters.
                if name == arena_tools.FINAL_ANSWER_TOOL:
                    continue
                tool_calls.append({"name": name, "arguments": getattr(call, "arguments", {})})

        text = str(output or "")
        return AgentResult(
            output_text=text,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            llm_calls=llm_calls,
            # smolagents swallows a run that runs out of steps and returns an
            # empty string. Surfacing the last step error keeps that legible as a
            # failure instead of a silent blank answer.
            error=None if text else error,
        )


class Adapter:
    name = "smolagents"

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return f"smolagents {version('smolagents')}"
        except PackageNotFoundError:
            return "smolagents (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
