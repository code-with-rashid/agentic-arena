# Build status / handoff

_Last updated: 2026-09-02. This file tracks what the automated scaffolding +
follow-up passes left in place. Delete it once the project has its own rhythm._

## What works right now

- `pip install -e ".[dev]"` on Python 3.11–3.14, **zero runtime deps** for the core.
- Five arenas run offline against the stdlib mock LLM:
  - `tool_use` — 15 items, search + calculator
  - `structured_output` — 15 items, search + a schema-checked JSON record
  - `resilience` — 8 scripted model/tool faults; the agent must recover
  - `multi_agent` — 10 items, a researcher → writer → editor brief (single-agent
    role-play for now; real multi-agent entries pending)
  - `rag` — 15 items over the shared corpus: single-hop, multi-hop, and
    unanswerable questions that trap answers taken from parametric memory
- Five adapters run green in mock mode on every arena:
  `vanilla`, `langgraph` (LangGraph 1.2.11), `pydantic_ai` (pydantic-ai-slim 2.37),
  `openai_agents` (openai-agents 0.22), `microsoft_af` (agent-framework 1.16).
- `python -m arena run --arena <id> --framework all --mode mock` → the five above
  green, the rest report themselves unavailable cleanly.
- `pytest -q` → all offline; `ruff check .` + `ruff format --check .` clean.
- `python -m arena scorecard --arena <id>` regenerates the scorecard (live →
  `results/<id>/`, mock → `runs/scorecards/<id>/`).
- CI: `lint-and-test` (3.11–3.13, runs `arena validate` + pytest), `resilience`
  (reports the recovery table; fails only if the stdlib baseline breaks), and
  `mock-smoke` (a framework × arena matrix).

## What is scaffolded but not yet real

| Item | State | Next step |
|---|---|---|
| First **live** scorecard | none — no API key wired in; `results/` holds only a mock `tool_use` sample | add repo secret `OPENAI_API_KEY`, run the `full-run` workflow, commit `results/` |
| `frameworks/crewai/adapter.py` | written, **not mock-verified** — CrewAI's transitive tree (chromadb/onnxruntime) has no Python 3.14 wheels, and a first 3.12 CI attempt scored 0/15 (telemetry prompt + an internal `'list' object has no attribute 'rstrip'`). Kept out of the required matrix. | debug on a 3.12 venv, pin the exact version, add its CI cell, refresh results |
| `frameworks/claude_agent_sdk` | deliberate stub — drives the `claude` CLI (Node) over the Anthropic Messages API, not one OpenAI-compatible endpoint | see `frameworks/claude_agent_sdk/README.md` for the three ways to close it |
| Arenas `human_in_the_loop`, `durable_state` | design docs only, in `docs/arenas/` | promote to `arenas/<id>/`; both need a harness resume/checkpoint API first |
| `multi_agent` real orchestration | only the single-agent role-play entry exists | add `<fw>-multi` adapter entries that use each framework's own graph/crew/handoff mechanism; compare tokens + LLM calls against the single-agent run |
| `results/` | **empty** — no live scorecard exists yet. Mock runs now write to `runs/scorecards/` instead, so `results/` stays live-only by construction. A format sample lives in `docs/scorecard-example.md`. | wire a key into `full-run`, then commit its output |
| Docs site | plain markdown in `docs/` | MkDocs Material + GitHub Pages (Phase 4) |

## To produce the first real scorecard

1. Add repo secret `OPENAI_API_KEY` (and optionally vars `ARENA_MODEL`,
   `OPENAI_BASE_URL`).
2. Run the **full-run** GitHub Action (`workflow_dispatch`) with
   `frameworks = "vanilla langgraph pydantic_ai openai_agents microsoft_af"`,
   `repeat = 3`.
3. Download the artifact, sanity-check `results/<arena>/scorecard.md`, commit it.

Locally instead:

```bash
export ARENA_LLM_MODE=live OPENAI_API_KEY=sk-... ARENA_MODEL=gpt-4.1-mini
python -m arena run --arena tool_use \
  --framework vanilla --framework langgraph --framework pydantic_ai \
  --mode live --repeat 3
```

## Known rough edges

- Mock server picks a scenario by substring-matching the first user message and
  serves turn *N* after *N* assistant messages. Adapters that don't replay prior
  tool calls in each request would desync — none of the current ones do.
- `microsoft_af` is async-only; the adapter builds a fresh client + event loop per
  item so the httpx client never outlives its loop. `openai_agents` needs its
  built-in tracing disabled or it POSTs to `api.openai.com`.
- `crewai` tool-call capture uses a wrapper sink because CrewAI doesn't expose a
  tool-call history; retries could undercount (the `tool_used` checks still pass).
- Token/latency in mock mode are client-serialisation artifacts, not model usage —
  the scorecard header says so; don't let anyone quote them.

## Git

`main` holds the scaffold commit. Phase 2/3 work (this file's "what works" list)
lands via the `next-phases` branch / its PR.
