"""Pydantic AI wired as a delegation pipeline. A *fourth* library, a third shape.

`multi_agent` now carries three delegation mechanisms across four libraries:

  * **Structural** (`vanilla_multi`, `langgraph_multi`) — the wiring always
    visits researcher, writer and editor. Delegation is a property of the graph.
  * **Model-decided, speaker swap** (`openai_agents_multi`) — each agent holds a
    `transfer_to_<agent>` tool. A handoff hands the *same* conversation to the
    next agent, which continues it under its own instructions.
  * **Model-decided, sub-agent as tool** (`smolagents_multi` and this entry) — a
    sub-agent is advertised as an ordinary tool named after itself. Calling it
    runs a whole nested agent with its **own fresh conversation**, and its answer
    comes back as the tool's return value. The speaker never changes.

        researcher --writer(task)--> writer --editor(task)--> editor

What makes this entry worth having next to `smolagents_multi`, which shares its
mechanism, is that **Pydantic AI has no delegation feature**. There is no
`managed_agents` list and no `AgentTool` wrapper: the delegate is an ordinary
async tool whose body happens to `await sub_agent.run(...)`. The library does not
know a sub-agent is involved.

It costs exactly the same anyway — 2N LLM calls for N roles, agreeing with
smolagents and Google ADK at every depth from one to five
(`tests/test_delegation_depth.py`). That is the strongest available evidence that
the 2N law is the *mechanism* rather than any library's implementation of it: a
sub-agent's reply is a tool result, not the end of the run, so every delegator
spends a second call producing its own final answer once the sub-agent returns.

It also settles a claim the depth table could only gesture at before. smolagents
restarts each sub-agent's conversation exactly as this does, yet its prompt grows
5.68x from one role to four where ADK's grows 3.59x. This entry grows **3.68x** —
ADK's number, not smolagents'. So the outlier is smolagents' own ~4 KB templated
system prompt being re-sent by every fresh sub-agent, and not anything about
starting fresh. Two independent implementations agreeing is what turns that from
a plausible explanation into a measurement.

Fairness notes, same as the other pipeline entries:

  * `arena.system_prompt` goes to every agent verbatim with one role line
    appended; the arena owns the task, this file owns only the division of labour.
  * Only the researcher gets tools. Giving them to the writer and editor would
    make this three researchers rather than a pipeline.
  * The iteration budget is per *item*: one `UsageLimits(request_limit=...)` over
    a `RunUsage` shared by every nested run, so the three roles draw on one pot
    rather than getting one each. Worth naming what that means here — 2N at three
    roles is six calls against a default budget of six, so this mechanism spends
    the whole per-item allowance where a handoff chain spends four of it. That is
    the cost of the mechanism, not a shortage of headroom.
  * The same shared `RunUsage` is what makes the reported cost honest. A nested
    run bills the same gateway; leaving it out would report a pipeline as costing
    what a single agent costs, which is the class of under-reporting
    `tests/test_usage_accounting.py` exists to catch.
"""

from __future__ import annotations

from typing import Annotated, Any

# Guarded: CI's lint job installs no framework, and `available_frameworks()` has
# to import every adapter module against a bare interpreter. The annotations
# below are only evaluated when a runner is built.
try:
    from pydantic import Field
except ImportError:  # pragma: no cover - adapter is unbuildable without it anyway
    Field = None  # type: ignore[assignment]

from arena.config import ArenaConfig
from arena.tools import names_for as _tool_names
from arena.tools import search as _search
from arena.types import AgentResult, ArenaSpec, EvalItem

# Deliberately the same role wording as frameworks/{vanilla,langgraph,
# openai_agents,smolagents}_multi, so the only thing separating the five pipeline
# entries is the mechanism.
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

# These become the delegate tools' schema descriptions, so they are what the
# delegating agent's model reads when deciding to hand work on.
DESCRIPTIONS = {
    "writer": "Writes the brief from the facts the researcher has gathered.",
    "editor": "Revises a draft brief and returns the final version.",
}

CHAIN = ("researcher", "writer", "editor")


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        from openai import AsyncOpenAI
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
        from pydantic_ai.providers.openai import OpenAIProvider

        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        model = OpenAIChatModel(
            config.model,
            # `OpenAIProvider(base_url=...)` builds its own client with the
            # library default timeout, so the shared `request_timeout_s` would be
            # ignored. Handing it a client is the only way to set it here — same
            # reason as the single-agent entry.
            provider=OpenAIProvider(
                openai_client=AsyncOpenAI(
                    base_url=config.base_url,
                    api_key=config.api_key,
                    timeout=config.request_timeout_s,
                )
            ),
        )
        settings = OpenAIChatModelSettings(temperature=config.temperature)

        def agent(role: str) -> Any:
            return Agent(
                model,
                system_prompt=f"{self.system_prompt}\n\n{ROLES[role]}",
                model_settings=settings,
                output_type=str,
            )

        agents = {role: agent(role) for role in CHAIN}
        self._head = agents[CHAIN[0]]

        if "search" in _tool_names(arena.tools):
            # Signature, wording and parameter descriptions track
            # `arena.tools.specs_for`; Pydantic AI reads a parameter description
            # from `Field`, not the docstring. See docs/tool-schemas.md.
            @self._head.tool_plain
            def search(
                query: Annotated[str, Field(description="What to look up.")],
                k: Annotated[int, Field(description="How many snippets.")] = 3,
            ) -> str:
                """Search a knowledge base of general facts. Returns up to k text snippets."""
                return _search(query, k)

        # The usage every nested run accumulates into. Rebuilt per item in `run`;
        # this attribute only exists so the closures below can reach the current
        # one without threading it through the tool signature.
        self._usage: Any = None

        for parent, child in zip(CHAIN, CHAIN[1:], strict=False):
            child_agent = agents[child]

            def make(child_agent: Any = child_agent) -> Any:
                async def delegate(
                    task: Annotated[str, Field(description="The task to carry out.")],
                ) -> str:
                    result = await child_agent.run(task, usage=self._usage)
                    return str(result.output)

                return delegate

            agents[parent].tool_plain(name=child, description=DESCRIPTIONS[child])(make())

    def run(self, item: EvalItem) -> AgentResult:
        from pydantic_ai.messages import ToolCallPart
        from pydantic_ai.usage import RunUsage, UsageLimits

        self._usage = RunUsage()
        try:
            result = self._head.run_sync(
                item.input,
                usage=self._usage,
                usage_limits=UsageLimits(request_limit=self.config.max_tool_iterations),
            )
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            return AgentResult(error=f"{type(exc).__name__}: {exc}")

        # Only the researcher holds an arena tool, so every graded tool call is in
        # the head agent's own conversation. The delegate calls are in there too
        # and are skipped: a sub-agent is not a tool the arena granted, so it may
        # not satisfy a `tool_used` check. It stays fully counted in the token
        # accounting below.
        tool_calls: list[dict[str, Any]] = []
        for message in result.all_messages():
            for part in getattr(message, "parts", []):
                if isinstance(part, ToolCallPart) and part.tool_name not in DESCRIPTIONS:
                    tool_calls.append({"name": part.tool_name, "arguments": part.args})

        usage = self._usage
        return AgentResult(
            output_text=str(result.output or ""),
            tool_calls=tool_calls,
            prompt_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            llm_calls=int(getattr(usage, "requests", 0) or 0),
        )


class Adapter:
    name = "pydantic_ai_multi"
    # The sub-agents are advertised as tools named after themselves, so there is
    # no prefix to match the way `transfer_to_*` is matched. Declaring the names
    # is what exempts them from the "only the arena's tools" rule - see
    # arena.tools.is_control_tool for why that exemption is sound and what bounds
    # it. They stay fully counted in prompt-size accounting.
    delegates = tuple(DESCRIPTIONS)
    # A pipeline, not a general-purpose entry: scoped so `--framework all` keeps
    # it out of the single-agent overhead table, where 3x the calls would read as
    # this library being wasteful rather than as a different structure being
    # measured.
    arenas = ("multi_agent",)

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        for dist in ("pydantic-ai", "pydantic-ai-slim"):
            try:
                return f"{dist} {version(dist)} (agent delegation)"
            except PackageNotFoundError:
                continue
        return "pydantic-ai (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
