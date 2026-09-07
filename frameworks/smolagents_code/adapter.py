"""smolagents `CodeAgent` adapter — the contrast with `ToolCallingAgent`.

`frameworks/smolagents` runs a `ToolCallingAgent`: the model replies with native
OpenAI `tool_calls` and smolagents dispatches them. `CodeAgent` is a different
execution model — the model replies with a **Python code blob** that *calls* the
tool functions, and smolagents executes it in a sandbox. Same library, same
tools, same task; only the loop differs, which is exactly what makes the pair a
useful comparison.

Two adapter facts follow from that:

  * The arena tools are `@tool` functions the executed code calls directly, so
    the tool-call log is captured through a wrapper sink rather than off
    `step.tool_calls` — that field reports `python_interpreter`, the executor,
    not `search` / `calculator`.
  * The mock renders a scripted turn as a `<code>` block for this client (see
    `arena.llm.mockserver._looks_like_code_agent`), so `CodeAgent` faces the
    identical sequence of scripted decisions as every other adapter.

Scoped to the three single-agent tool arenas — `tool_use`, `rag`,
`structured_output`. It is a contrast entry, run where a tool loop is what is
being compared: `tool_use` is where the overhead number lives, `rag` is the same
`search` loop with a second hop (see `tests/test_rag_arena.py`), and
`structured_output` is `tool_use` with a JSON-shaped answer — a `CodeAgent` is
prompt-only there like every other adapter (see docs/structured-output.md). The
pause, durable and multi-agent arenas are out of scope for the same reasons they
are for the `smolagents` entry.
"""

from __future__ import annotations

from typing import Any

from arena.config import ArenaConfig
from arena.tools import calculator as _calculator
from arena.tools import names_for as _tool_names
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem


def _make_tools(sink: list[dict[str, Any]], names: list[str]) -> list[Any]:
    """`@tool` wrappers whose bodies record the call, then delegate unchanged.

    Signatures and wording track `arena.tools.specs_for` exactly — the arena
    declares the tools, and a framework offered a narrower one is being handed a
    different task. See docs/tool-schemas.md.
    """
    from smolagents import tool

    @tool
    def search(query: str, k: int = 3) -> str:
        """Search a knowledge base of general facts. Returns up to k text snippets.

        Args:
            query: What to look up.
            k: How many snippets.
        """
        sink.append({"name": "search", "arguments": {"query": query, "k": k}})
        return _search(query, k)

    @tool
    def calculator(expr: str) -> str:
        """Evaluate a basic arithmetic expression, e.g. '330 / 0.3048'.

        Args:
            expr: Arithmetic expression.
        """
        sink.append({"name": "calculator", "arguments": {"expr": expr}})
        return _calculator(expr)

    available = {"search": search, "calculator": calculator}
    return [available[name] for name in names if name in available]


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        from smolagents import OpenAIServerModel

        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        self.tool_names = _tool_names(arena.tools)
        model = OpenAIServerModel(
            model_id=config.model,
            api_base=config.base_url,
            api_key=config.api_key,
            # smolagents builds the client itself; `client_kwargs` is the only
            # way through, and without this the shared budget is ignored.
            client_kwargs={"timeout": config.request_timeout_s},
            temperature=config.temperature,
        )
        self._model = model
        self._agent_kwargs = {
            "instructions": self.system_prompt,
            # Same off-by-one as the ToolCallingAgent entry: smolagents makes one
            # model call *beyond* `max_steps`, so N - 1 yields N total calls.
            "max_steps": max(1, config.max_tool_iterations - 1),
            "verbosity_level": 0,
        }

    def run(self, item: EvalItem) -> AgentResult:
        from smolagents import CodeAgent

        calls: list[dict[str, Any]] = []
        tools = _make_tools(calls, self.tool_names)
        agent = CodeAgent(tools=tools, model=self._model, **self._agent_kwargs)

        try:
            output = agent.run(item.input, reset=True)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            return AgentResult(error=f"{type(exc).__name__}: {exc}")

        prompt_tokens = completion_tokens = llm_calls = 0
        error: str | None = None
        for step in getattr(agent.memory, "steps", []):
            usage = getattr(step, "token_usage", None)
            if usage is not None:
                prompt_tokens += int(getattr(usage, "input_tokens", 0) or 0)
                completion_tokens += int(getattr(usage, "output_tokens", 0) or 0)
                llm_calls += 1
            step_error = getattr(step, "error", None)
            if step_error is not None:
                error = f"{type(step_error).__name__}: {step_error}"

        text = str(output or "")
        return AgentResult(
            output_text=text,
            tool_calls=calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            llm_calls=llm_calls,
            # An exhausted CodeAgent run returns "" rather than raising; surface
            # the last step error so a blank answer reads as a failure.
            error=None if text else error,
        )


class Adapter:
    name = "smolagents_code"
    # A contrast entry, like the `_multi` pipelines: `--framework all` runs it
    # only where it is meant to be compared. Naming it explicitly works anywhere.
    # `tool_use` carries the overhead number; `rag` and `structured_output` are
    # the same tool loop (a second hop / a JSON answer), and CodeAgent clears
    # both 15/15 like everyone else.
    arenas = ("tool_use", "rag", "structured_output")

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return f"smolagents {version('smolagents')} (CodeAgent)"
        except PackageNotFoundError:
            return "smolagents (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
