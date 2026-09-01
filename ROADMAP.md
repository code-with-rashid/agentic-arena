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

- ✅ Arena 1 `tool_use`: `arena.yaml` spec, `dataset.jsonl` (15 items), `mock_script.json`
- ✅ Scorer: `contains`, `iregex`, `numeric_equals` (with tolerance), `tool_used`, `no_tool`
- ✅ `vanilla` baseline adapter (stdlib agent loop) — runs green in mock mode
- ✅ `langgraph` adapter
- ✅ `crewai` adapter
- 🚧 First **live** scorecard for `tool_use` across vanilla + langgraph + crewai
      (needs an API key; run `python -m arena run --mode live` and commit `results/`)

## Phase 2 — Breadth of frameworks ⬜

- ⬜ Fill adapters: OpenAI Agents SDK, Claude Agent SDK, Pydantic AI, Microsoft Agent Framework
- ⬜ Google ADK adapter (stretch)
- ⬜ Complete `docs/feature-matrix.md` for all adapters
- ⬜ Per-framework deep dives in `docs/frameworks/` (drafts already stubbed)
- ⬜ `docs/decision-guide.md` "if you need X, pick Y" flowchart

## Phase 3 — Breadth of arenas ⬜

- ⬜ Implement arenas 2–6 (`multi_agent`, `rag`, `structured_output`,
      `human_in_the_loop`, `durable_state`) across the adapter set
- ⬜ Reliability runs (`--repeat 10`) + variance reporting
- ⬜ Latency / token / cost charts generated into `results/charts/`

## Phase 4 — Polish + community ⬜

- ⬜ Docs site (MkDocs Material) published to GitHub Pages
- ⬜ Version pinning per adapter + Renovate/Dependabot for controlled refreshes
- ⬜ "Results last refreshed on <date> with <versions>" automation
- ⬜ Seed `good first issue`s for every empty framework × arena cell
- ⬜ Launch write-up

## Explicitly out of scope (for now)

- TypeScript adapters (Mastra, LangGraph.js, VoltAgent) — revisit after the Python
  set is complete; would live under `frameworks-ts/`.
- Hosted/SaaS agent platforms that can't run locally from source.
- Leaderboard web app — the generated Markdown scorecards are the product until
  there's demand for more.
