"""OpenAI Agents SDK adapter wired as a *handoff chain*. The model-decided contrast.

The `multi_agent` arena now carries two kinds of pipeline, and they are not the
same experiment:

  * **Structural** (`vanilla_multi`, `langgraph_multi`) — the graph always visits
    researcher, writer and editor. Delegation is a property of the wiring.
  * **Model-decided** (this entry) — each agent is handed a `transfer_to_<agent>`
    tool and *chooses* to delegate. Delegation is a decision the model makes.

Three agents chained by the SDK's native `handoffs`:

    researcher --transfer_to_writer--> writer --transfer_to_editor--> editor

A handoff is not a subroutine call: the SDK swaps which agent is talking and the
conversation carries on, so the next agent sees the whole transcript under its
own instructions and its own tool set. That is visible on the wire - after the
transfer the system prompt changes and the researcher's tools disappear.

Because delegation is model-decided, it cannot be measured against a mock that
only ever replays a scripted answer: the model would simply never choose to
transfer, and this entry would silently report the single-agent numbers. The mock
therefore renders the scripted "research is done, write it up" step as a transfer
for clients that offer one - see `arena.llm.mockserver._delegation_tool`, and
docs/multi-agent.md for why that is a restatement of the scripted decision rather
than a new one.

Fairness notes, same as the other pipeline entries:

  * `arena.system_prompt` goes to every agent verbatim with one role line
    appended; the arena owns the task, this file owns only the division of labour.
  * The iteration budget is per *item*. Three agents divide one
    `max_tool_iterations` between them rather than getting one each.
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

from arena.config import ArenaConfig
from arena.tools import calculator as _calculator
from arena.tools import names_for as _tool_names
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem

# Deliberately the same role wording as frameworks/{vanilla,langgraph}_multi so
# the only thing separating the three pipeline entries is the mechanism.
ROLES = {
    "researcher": (
        "You are the researcher on this pipeline. Use the `search` tool to gather "
        "the facts the brief needs. Do not write the brief yourself."
    ),
    "writer": (
        "You are the writer on this pipeline. Using only the facts already "
        "gathered above, write the brief. Reply with the brief and nothing else."
    ),
    "editor": (
        "You are the editor on this pipeline. Check the draft above against the "
        "task and reply with the final brief, revised if needed and unchanged if "
        "not. Reply with the brief and nothing else."
    ),
}


def _make_tools(names: list[str]) -> list[Any]:
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

    available = {"search": search, "calculator": calculator}
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
        model = OpenAIChatCompletionsModel(model=config.model, openai_client=client)
        settings = ModelSettings(temperature=0.0)

        def agent(role: str, **kw: Any) -> Any:
            return Agent(
                name=role,
                instructions=f"{self.system_prompt}\n\n{ROLES[role]}",
                model=model,
                model_settings=settings,
                **kw,
            )

        # Built back to front: an agent must exist before it can be handed to.
        # The editor offers no handoff, which is what ends the chain - the mock
        # serves it the brief because it is the first agent not asking to
        # delegate.
        editor = agent("editor")
        writer = agent("writer", handoffs=[editor])
        # Only the researcher gets tools. Handing them to the writer and editor
        # would make this three researchers rather than a pipeline.
        self._agent = agent(
            "researcher", tools=_make_tools(_tool_names(arena.tools)), handoffs=[writer]
        )

    def run(self, item: EvalItem) -> AgentResult:
        from agents import Runner

        try:
            result = Runner.run_sync(
                self._agent, item.input, max_turns=self.config.max_tool_iterations
            )
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            return AgentResult(error=f"{type(exc).__name__}: {exc}")

        tool_calls: list[dict[str, Any]] = []
        for run_item in result.new_items:
            # HandoffCallItem is the delegation itself, not an action taken on the
            # task. Logging it would make this entry look like it used tools the
            # arena never declared, and break its max_tool_calls checks.
            if type(run_item).__name__ != "ToolCallItem":
                continue
            raw = run_item.raw_item
            tool_calls.append(
                {
                    "name": getattr(raw, "name", ""),
                    "arguments": getattr(raw, "arguments", ""),
                }
            )

        usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
        return AgentResult(
            output_text=str(result.final_output or ""),
            tool_calls=tool_calls,
            prompt_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            llm_calls=int(getattr(usage, "requests", 0) or 0),
        )


class Adapter:
    name = "openai_agents_multi"
    # A contrast entry, not a general-purpose adapter: `--framework all` runs it
    # only on the arena it was built to contrast on. Naming it explicitly still
    # works anywhere. See arena.registry.frameworks_for_arena.
    arenas = ("multi_agent",)

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return f"openai-agents {version('openai-agents')} (handoff chain)"
        except PackageNotFoundError:
            return "openai-agents (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
