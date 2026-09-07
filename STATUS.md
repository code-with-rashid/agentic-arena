# Build status / handoff

_Last updated: 2026-09-07. This file tracks what the automated scaffolding +
follow-up passes left in place. Delete it once the project has its own rhythm._

## What works right now

- `pip install -e ".[dev]"` on Python 3.11–3.14, **zero runtime deps** for the core.
- Seven arenas run offline against the stdlib mock LLM:
  - `tool_use` — 15 items, search + calculator
  - `structured_output` — 15 items, search + a schema-checked JSON record
  - `resilience` — 8 scripted model/tool faults; the agent must recover
  - `multi_agent` — 10 items, a researcher → writer → editor brief (single-agent
    role-play for now; real multi-agent entries pending)
  - `rag` — 15 items over the shared corpus: single-hop, multi-hop, and
    unanswerable questions that trap answers taken from parametric memory
  - `human_in_the_loop` — 12 items, the agent must pause for approval before
    booking. `langgraph` (native interrupt), `openai_agents` (`needs_approval`),
    `pydantic_ai` (deferred tools), `microsoft_af` (`approval_mode` +
    `ToolApprovalMiddleware`), `google_adk` (`LongRunningFunctionTool`) and
    `vanilla` (emulated) all 12/12 — six distinct mechanisms; `smolagents`
    reports unsupported because it has no `resume` method
  - `multi_agent` — 10 items; carries five real three-role pipelines beside the
    single-agent entries: `vanilla_multi` (hand-rolled) and `langgraph_multi`
    (a `StateGraph`) for structural delegation, `openai_agents_multi` for a
    model-decided handoff chain, and `smolagents_multi` + `pydantic_ai_multi`
    for a sub-agent invoked as a tool. Measures what delegation costs: 2x LLM
    calls, ~2.5x prompt tokens, the graph machinery itself adds nothing, and a
    handoff costs ~10% more again — 94% of it the `transfer_to_*` schemas on
    every request rather than the transfers. Sub-agent-as-a-tool costs 3x the
    calls instead of 2x, and does so identically in three libraries that share
    no code — including Pydantic AI, which has no delegation feature at all
  - `durable_state` — 8 items; the harness throws the runner away at the
    checkpoint and rebuilds it. All four resumable adapters 8/8, by four
    different mechanisms — see docs/feature-matrix.md
- Seven adapters run in mock mode:
  `vanilla`, `langgraph` (LangGraph 1.2.11), `pydantic_ai` (pydantic-ai-slim 2.37),
  `openai_agents` (openai-agents 0.22), `microsoft_af` (agent-framework 1.16),
  `smolagents` (smolagents 1.26), `google_adk` (google-adk 2.8 + litellm).
  `vanilla`, `pydantic_ai` and `microsoft_af` are green on every arena they run;
  the others' misses are measured findings, not wiring bugs — `langgraph` 7/8 and
  `openai_agents` 7/8 and `google_adk` 6/8 on `resilience` (`smolagents` recovers
  8/8 but at 3× the cost on the faults its validator rejects), and pause support
  reported as *unsupported* where a framework has no `resume`.
- `python -m arena run --arena <id> --framework all --mode mock` → the six above
  run, the rest report themselves unavailable cleanly.
- `pytest -q` → all offline; `ruff check .` + `ruff format --check .` clean.
- Usage accounting is a CI gate: each adapter's reported tokens/LLM calls are
  held against what the mock actually served, on the plain and the resumed
  path. Caught langgraph dropping a whole leg on `durable_state`.
- `python -m arena scorecard --arena <id>` regenerates the scorecard (live →
  `results/<id>/`, mock → `runs/scorecards/<id>/`).
- `python -m arena summary --print` renders every arena in one view — coverage,
  fault recovery, prompt size, pause support. CI uploads it as an artifact.
- CI: `lint-and-test` (3.11–3.13, runs `arena validate` + pytest), `resilience`
  (reports the recovery table; fails only if the stdlib baseline breaks), and
  `mock-smoke` (a framework × arena matrix).

## What is scaffolded but not yet real

| Item | State | Next step |
|---|---|---|
| First **live** scorecard | none — no API key wired in; `results/` holds only a mock `tool_use` sample | add repo secret `OPENAI_API_KEY`, run the `full-run` workflow, commit `results/` |
| `frameworks/crewai/adapter.py` | written, **not mock-verified** — CrewAI's transitive tree (chromadb/onnxruntime) has no Python 3.14 wheels. On 3.12 (crewai 0.203.2) it installs, builds and answers correctly. A first CI run scored **0/15** because the wrapper tool-call sink stayed empty; the adapter now also captures tool steps through a `step_callback`, and sets every spelling of the trace-prompt opt-out env var. Needs a `crewai-debug.yml` run to confirm the `tool_used` checks now pass before it goes back in the matrix. | run the debug workflow; if green, pin the version, add its CI cell, refresh results |
| `frameworks/claude_agent_sdk` | deliberate stub — drives the `claude` CLI (Node) over the Anthropic Messages API, not one OpenAI-compatible endpoint | see `frameworks/claude_agent_sdk/README.md` for the three ways to close it |
| Real multi-agent entries for `multi_agent` | only single-agent role-play entries exist | add `<fw>-multi` adapters using each framework's own graph/crew/handoff mechanism, compared on token and LLM-call cost |
| Durable pause for `microsoft_af` | its `AgentSession` message store does not survive a JSON round trip, and restoring approval state re-queues the request | needs a real session store (`FileSessionStore`) wired to the harness checkpoint dir |
| `smolagents` `CodeAgent` | only `ToolCallingAgent` is measured. `CodeAgent` expects the model to reply with a Python **code blob** (` ```py … ``` ` / `<code>…</code>`) that calls the tools, and the mock serves a text-ReAct `content` turn instead — `CodeAgent`'s parser rejects it (`regex pattern <code>(.*?)</code> was not found`) and the run burns every step. | needs a new `arena.llm.mockserver` accommodation that renders a scripted turn as valid tool-calling Python for whichever tools the client advertises — its own change, not a one-file adapter |
| `multi_agent` real orchestration | only the single-agent role-play entry exists | add `<fw>-multi` adapter entries that use each framework's own graph/crew/handoff mechanism; compare tokens + LLM calls against the single-agent run |
| `results/` | **empty** — no live scorecard exists yet. Mock runs now write to `runs/scorecards/` instead, so `results/` stays live-only by construction. A format sample lives in `docs/scorecard-example.md`. | wire a key into `full-run`, then commit its output |
| Docs site | plain markdown in `docs/` | MkDocs Material + GitHub Pages (Phase 4) |

## To produce the first real scorecard

1. Add repo secret `OPENAI_API_KEY` (and optionally vars `ARENA_MODEL`,
   `OPENAI_BASE_URL`).
2. Run the **full-run** GitHub Action (`workflow_dispatch`) with
   `frameworks = "vanilla langgraph pydantic_ai openai_agents microsoft_af smolagents"`,
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
  serves turn *N* after *N* assistant messages, so an adapter that sent only the
  latest delta would desync. This used to be an untested assumption; it is now
  asserted on the wire for every adapter by
  `test_adapter_replays_the_whole_transcript`, alongside checks that the tool
  result reaches the model byte-for-byte and that the tool ran on the arguments
  the model actually asked for.
- `microsoft_af` is async-only; the adapter builds a fresh client + event loop per
  item so the httpx client never outlives its loop. `openai_agents` needs its
  built-in tracing disabled or it POSTs to `api.openai.com`.
- `crewai` (3.12 only) drives a text ReAct loop and does not fire the wrapper
  tool `_run` in this adapter's process, so tool-call capture now goes through a
  `step_callback` with the sink as fallback. Unverified until a `crewai-debug.yml`
  run confirms the `tool_used` checks pass — see `frameworks/crewai/README.md`.
- Token/latency in mock mode are client-serialisation artifacts, not model usage —
  the scorecard header says so; don't let anyone quote them.

## Git

`main` holds the scaffold commit. Phase 2/3 work (this file's "what works" list)
lands via the `next-phases` branch / its PR.
