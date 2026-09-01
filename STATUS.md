# Build status / handoff

_Last updated: 2026-09-01. This file tracks what an automated scaffolding pass left
in place. Delete it once the project has its own rhythm._

## What works right now

- `pip install -e ".[dev]"` on Python 3.11–3.14, **zero runtime deps** for the core.
- `python -m arena run --arena tool_use --framework vanilla --mode mock` → 15/15.
- `python -m arena run --arena tool_use --framework langgraph --mode mock` → 15/15
  (real LangGraph 1.2.11 talking to the stdlib mock LLM over an OpenAI-compatible API).
- `python -m arena run --arena tool_use --framework all --mode mock` → vanilla +
  langgraph green, the other five report themselves unavailable cleanly.
- `pytest -q` → 25 passing, all offline.
- `ruff check .` + `ruff format --check .` clean.
- `python -m arena scorecard --arena tool_use` regenerates `results/tool_use/`.

## What is scaffolded but not yet real

| Item | State | Next step |
|---|---|---|
| `frameworks/crewai/adapter.py` | written, **not verified** — a first CI attempt on Python 3.12 installed CrewAI but the mock run scored 0/15 (interactive telemetry prompt + an internal `'list' object has no attribute 'rstrip'`). Telemetry/tracing env vars are now forced off in the adapter, but it still needs a hands-on debug on 3.12. The crewai job is therefore **not** in the required `mock-smoke` CI matrix yet. | debug on a 3.12 venv, pin the exact `crewai` version, re-add the CI job, refresh results |
| `frameworks/{openai_agents,claude_agent_sdk,pydantic_ai,microsoft_af}` | stubs that raise `NotImplementedError` | implement against the `Framework` protocol; each has an issue-template checklist |
| Arenas 2–6 | design docs only, in `docs/arenas/` | promote to runnable `arenas/<id>/` dirs |
| `results/tool_use/scorecard.*` | **mock** numbers, committed as a format sample | replace with a `--mode live` run once a key is wired into the `full-run` workflow |
| Docs site | plain markdown in `docs/` | MkDocs Material + GitHub Pages (Phase 4) |

## To produce the first real scorecard

1. Add repo secret `OPENAI_API_KEY` (and optionally vars `ARENA_MODEL`,
   `OPENAI_BASE_URL`).
2. Run the **full-run** GitHub Action (`workflow_dispatch`) with
   `frameworks = "vanilla langgraph"`, `repeat = 3`.
3. Download the artifact, sanity-check `results/tool_use/scorecard.md`, commit it.

Locally instead:

```bash
export ARENA_LLM_MODE=live OPENAI_API_KEY=sk-... ARENA_MODEL=gpt-4.1-mini
python -m arena run --arena tool_use --framework vanilla --framework langgraph --mode live --repeat 3
```

## Known rough edges

- Mock server picks a scenario by substring-matching the first user message and
  serves turn *N* after *N* assistant messages. Adapters that don't replay prior
  tool calls in each request would desync — none of the current ones do.
- `crewai` tool-call capture uses a wrapper sink because CrewAI doesn't expose a
  tool-call history; if that misses internal retries the `tool_used` checks are
  still fine but counts may undercount.
- Token/latency in mock mode are client-serialisation artifacts, not model usage —
  the scorecard header says so; don't let anyone quote them.

## Git

Scaffold lives in a single commit on `main` on top of the original "Initial
commit", pushed to `origin`
(`https://github.com/code-with-rashid/agentic-arena`).
