# Roadmap

Status legend: ✅ done · 🚧 in progress · ⬜ not started

## Phase 0 — Scaffold ✅

- ✅ License (Apache-2.0), README, CONTRIBUTING, CODE_OF_CONDUCT
- ✅ `.gitignore`, `.gitattributes`, `.editorconfig`, `pyproject.toml` (ruff + pytest)
- ✅ Harness package skeleton (`arena/`): config, types, registry, runner, metrics, scorecard
- ✅ OpenAI-compatible LLM client + stdlib mock server
- ✅ Shared tools: deterministic search (over a fixture corpus) + safe calculator
- ✅ `Framework` / `AgentRunner` protocol and the scoring contract
- ✅ CI: lint + mocked smoke run; separate manual "full run" workflow
- ✅ Issue templates (add framework / add arena / refresh results) + PR template

## Phase 1 — Vertical slice ✅ / 🚧

- ✅ Arena 1 `tool_use`: `arena.toml` spec, `dataset.jsonl` (15 items), `mock_script.json`
- ✅ Scorer: `contains`, `icontains`, `not_contains`, `iregex`, `numeric_equals`
      (with tolerance), `tool_used`, `no_tool`, `min/max_tool_calls`, `json_valid`,
      `json_schema`, `json_path_equals`, `sentence_count`
- ✅ `vanilla` baseline adapter (stdlib agent loop) — runs green in mock mode
- ✅ `langgraph` adapter
- 🚧 `crewai` adapter — on Python 3.12 it installs, builds and answers correctly;
      tool-call capture through a `step_callback` added, awaiting a debug-workflow
      run to confirm 15/15 (see `frameworks/crewai/README.md`)
- 🚧 First **live** scorecard (needs an API key; run `python -m arena run --mode live`
      and commit `results/`)

## Phase 2 — Breadth of frameworks ✅ / 🚧

- ✅ `openai_agents`, `pydantic_ai`, `microsoft_af`, `smolagents` adapters —
      mock-green across the arenas each runs
- 🚫 `claude_agent_sdk` — stays a stub; drives the `claude` CLI over the Anthropic
      Messages API, so it can't use the shared OpenAI-compatible gateway
      (see `frameworks/claude_agent_sdk/README.md`)
- ✅ Google ADK adapter — via LiteLLM to the shared gateway; runs every arena it
      is registered for, including both delegation shapes (`sub_agents` and
      `AgentTool`)
- ✅ `smolagents_code` — a `CodeAgent` contrast entry (the model writes and
      executes Python) beside the `ToolCallingAgent` `smolagents` entry. Scoped to
      the three single-agent tool arenas (`tool_use`, `rag`, `structured_output`),
      15/15 in mock, 6.95× baseline wire cost against `ToolCallingAgent`'s 3.90×.
      Needed a new `arena.llm.mockserver` accommodation to render a scripted turn
      as a `<code>` blob; see `docs/frameworks/smolagents.md`
- 🚧 `docs/feature-matrix.md` — filled for every built adapter; `❓` cells remain for
      capabilities no arena exercises yet
- ✅ Per-framework deep dives in `docs/frameworks/` for the built adapters
- ✅ `docs/decision-guide.md` — filled in from measured offline evidence, every
      claim tagged [measured] or [claimed]; revisit once a live scorecard exists
- ✅ `docs/fairness-controls.md` + `tests/test_shared_controls.py` — every
      `ArenaConfig`/`ArenaSpec` control enumerated with the test that holds each
      adapter to it (`model`, `temperature`, `max_tool_iterations`,
      `request_timeout_s`, tool schema fidelity, …)

## Phase 3 — Breadth of arenas 🚧

- ✅ Arena 2 `structured_output`: schema-checked JSON record over the shared corpus
- ✅ Arena 3 `resilience`: scripted model/tool faults; the first arena that produces
      differentiated results offline (see docs/methodology.md section 5)
- ✅ Arena 4 `multi_agent`: researcher → writer → editor pipeline produces a
      bounded factual brief; single-agent role-play is a valid contrast entry
- ✅ Arena 5 `rag`: agentic retrieval over the shared corpus — single-hop,
      multi-hop, and unanswerable items that trap parametric-memory answers
- ✅ Harness suspend/resume API (`arena.types.ResumableRunner`,
      `EvalItem.resume_with`, leg merging in the runner) — methodology §7
- ✅ Arena 6 `human_in_the_loop`: the pause is observed by the harness, not
      claimed by the agent. `vanilla` 12/12 (emulated); other adapters report
      unsupported until they implement `resume`
- ✅ Native interrupts for `langgraph` (`interrupt` + `MemorySaver`, resumed with
      `Command`) — the HITL feature-matrix row is now measured, not judged
- ✅ Native deferred tools for `pydantic_ai` (`CallDeferred` +
      `deferred_tool_results`), passing both pause arenas
- ✅ Native approval interruptions for `openai_agents` (`needs_approval` +
      `RunState.to_json`), passing both pause arenas
- ✅ Pause support for `microsoft_af` (`approval_mode="always_require"` +
      `ToolApprovalMiddleware`) — 12/12 pause; does **not** survive a crash (its
      `AgentSession` store does not round-trip JSON), which is a measured finding
- ✅ Pause + durability for `google_adk` (`LongRunningFunctionTool` +
      `DatabaseSessionService` on `sqlite+aiosqlite`) — reports the pause but
      does not enforce it (🟡), survives a crash
- ✅ Arena 7 `durable_state` — the harness discards the runner at the pause and
      JSON round-trips the resume state, so only a real checkpoint or a
      serialised transcript survives. Six adapters 8/8 by six mechanisms;
      `test_durable_across_a_restart.py` runs the two legs in two interpreters
- ✅ Real multi-agent adapter entries — `vanilla_multi`, `langgraph_multi`
      (structural), `openai_agents_multi` (handoff chain), `smolagents_multi` +
      `pydantic_ai_multi` (sub-agent as a tool). Delegation cost measured to an
      exact law (N+1 / N+2 / 2N calls) across five implementations; see
      `docs/multi-agent.md`
- ⬜ Reliability runs (`--repeat 10`) + variance reporting
- ✅ Cross-arena summary (`python -m arena summary`) — coverage grid plus the
      three comparisons that hold offline; CI publishes it as an artifact
- ✅ Latency / token / cost charts — `python -m arena chart --arena <id>` renders
      pass-rate / mean-tokens / mean-LLM-calls / est-cost bar charts as
      hand-written SVG (no plotting dependency) into `<scorecard dir>/charts/`;
      live runs land in `results/<arena>/charts/`, mock runs stay under `runs/`

## Phase 4 — Polish + community ⬜

- ⬜ Docs site (MkDocs Material) published to GitHub Pages
- ✅ Version pinning per adapter + Dependabot for controlled refreshes
      (`.github/dependabot.yml`, one grouped monthly PR per adapter;
      policy + deprecation register in `docs/dependencies.md`)
- ⬜ "Results last refreshed on <date> with <versions>" automation
- ⬜ Seed `good first issue`s for every empty framework × arena cell
- ⬜ Launch write-up

## Explicitly out of scope (for now)

- TypeScript adapters (Mastra, LangGraph.js, VoltAgent) — revisit after the Python
  set is complete; would live under `frameworks-ts/`.
- Hosted/SaaS agent platforms that can't run locally from source.
- Leaderboard web app — the generated Markdown scorecards are the product until
  there's demand for more.
