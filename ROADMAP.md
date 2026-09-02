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
- ✅ `crewai` adapter (written; mock-verify still pending on Python 3.12)
- 🚧 First **live** scorecard (needs an API key; run `python -m arena run --mode live`
      and commit `results/`)

## Phase 2 — Breadth of frameworks ✅ / 🚧

- ✅ `openai_agents`, `pydantic_ai`, `microsoft_af` adapters — mock-green on both arenas
- 🚫 `claude_agent_sdk` — stays a stub; drives the `claude` CLI over the Anthropic
      Messages API, so it can't use the shared OpenAI-compatible gateway
      (see `frameworks/claude_agent_sdk/README.md`)
- ⬜ Google ADK adapter (stretch)
- 🚧 `docs/feature-matrix.md` — filled for every built adapter; `❓` cells remain for
      capabilities no arena exercises yet
- ✅ Per-framework deep dives in `docs/frameworks/` for the built adapters
- ⬜ `docs/decision-guide.md` "if you need X, pick Y" flowchart

## Phase 3 — Breadth of arenas 🚧

- ✅ Arena 2 `structured_output`: schema-checked JSON record over the shared corpus
- ✅ Arena 3 `resilience`: scripted model/tool faults; the first arena that produces
      differentiated results offline (see docs/methodology.md section 5)
- ✅ Arena 4 `multi_agent`: researcher → writer → editor pipeline produces a
      bounded factual brief; single-agent role-play is a valid contrast entry
- ✅ Arena 5 `rag`: agentic retrieval over the shared corpus — single-hop,
      multi-hop, and unanswerable items that trap parametric-memory answers
- ⬜ Implement arenas 6–7 (`human_in_the_loop`, `durable_state`) — both need a
      harness resume/checkpoint API first; `multi_agent` still needs real
      multi-agent adapter entries (`<fw>-multi`)
- ⬜ Reliability runs (`--repeat 10`) + variance reporting
- ⬜ Latency / token / cost charts generated into `results/charts/`

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
