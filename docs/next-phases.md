# Next phases — research notes and plan

_Written 2026-09-01. Companion to [ROADMAP.md](../ROADMAP.md); ROADMAP stays the
terse index, this file records the reasoning and the current batch of work._

## Where things stand

Phase 0 (scaffold) and the Phase 1 vertical slice are done: the `tool_use` arena
runs green in mock mode for `vanilla` and `langgraph`, CI is green, and the
harness core is stdlib-only. The gaps are breadth — only two of seven adapters are
real, and only one of six arenas exists.

## What the landscape says (Sept 2026)

The Python agent-framework field has settled into two groups:

- **Provider-native SDKs** — OpenAI Agents SDK, Claude Agent SDK, Google ADK.
  Optimised for one model family.
- **Provider-neutral frameworks** — LangGraph, CrewAI, Pydantic AI, Microsoft
  Agent Framework (the merged AutoGen + Semantic Kernel line), Smolagents.

Public comparisons still lean on prose and one-off token counts (e.g. "~18% token
overhead vs LangGraph", "$390 vs $1088 over 90 days"). Nobody publishes a
*regenerable* cross-framework scorecard on identical tasks — which is the gap this
project fills. The takeaway for us: keep the harness honest and reproducible, and
widen coverage.

## Installability check (this machine: Windows, CPython 3.14.7, no C compiler)

Ran `pip install` resolution for each stub package into a clean 3.14 venv:

| Package | 3.14 result | Notes |
|---|---|---|
| `pydantic-ai-slim[openai]` | ✅ installs + imports | 2.37.0; all cp314 wheels; native typed output |
| `openai-agents` | ✅ installs + imports | 0.22.0; needs tracing disabled offline |
| `agent-framework` (meta) | ⚠️ huge tree | pulls `agent-framework-core[all]` (azure, boto3, redis, qdrant, numpy…). Use the narrow `agent-framework-core` + `agent-framework-openai` instead |
| `claude-agent-sdk` | ✅ installs | but see below — wrong protocol shape |
| `crewai` | ❌ (unchanged) | chromadb/onnxruntime have no 3.14 wheels; 3.12-only, still unverified |

`claude-agent-sdk` installs but does not fit the harness as-is: it drives the
`claude` CLI (Node) as a subprocess and speaks the Anthropic Messages API, not an
OpenAI-compatible `/chat/completions`. It cannot point at the OpenAI-shaped mock
server without either an Anthropic-shaped mock or a translating proxy (LiteLLM) and
Node in CI. Left as a stub with that blocker written down.

## This batch of work

Branch: `next-phases`. One reviewable PR, small separate commits, no merge to
`main`. Every commit keeps `ruff` + `pytest` green; every new adapter is proven
15/15 against the mock before its commit lands.

### Track A — framework adapters (Phase 2)

1. **`pydantic_ai`** — `OpenAIChatModel` + `OpenAIProvider(base_url, api_key)`,
   shared tools via `@agent.tool_plain`, tool calls read from
   `result.all_messages()`, tokens from the run usage. Pin `pydantic-ai-slim`.
2. **`openai_agents`** — `AsyncOpenAI(base_url, api_key)` +
   `OpenAIChatCompletionsModel` + `Agent`/`Runner`, `set_tracing_disabled(True)`,
   `function_tool` wrappers, usage + tool calls from the `RunResult`. Pin
   `openai-agents`.
3. **`microsoft_af`** — attempt with the narrow `agent-framework-openai` install
   (`OpenAIChatClient` + `ChatAgent`). Ship only if it installs lean and runs
   15/15; otherwise leave an improved stub noting the dependency weight.
4. **`claude_agent_sdk`** — stays a stub; add a README with the protocol-mismatch
   blocker and the two ways a contributor could close it.

### Track B — second arena (Phase 3): `structured_output`

5. New mechanical scorer checks, stdlib-only, unit-tested: `not_contains`,
   `json_valid`, `json_path_equals` (tolerance-aware), and a tiny inline
   `json_schema` validator (object / required / properties / type / minItems /
   additionalProperties — enough for the design schema, no new dependency).
6. `arenas/structured_output/` — `arena.toml`, ~15-item `dataset.jsonl` over an
   expanded corpus, `mock_script.json` with valid JSON per item plus one
   bad-JSON-then-retry scenario.
7. Grow `arena/tools/corpus.json` from 10 to ~28 passages (also unblocks the
   future `rag` arena). `tool_use` dataset/mock untouched.

### Track C — wiring

8. `ci.yml`: add `mock-smoke` matrix rows for each newly verified adapter.
9. Exact version pins in `frameworks/<name>/requirements.txt`.
10. Fill the `❓` cells in `docs/feature-matrix.md` from first-hand adapter work;
    turn the `docs/frameworks/*.md` stubs into real notes for the ones now built.
11. Update `README.md` tables, `ROADMAP.md`, `STATUS.md`, `docs/arenas/README.md`.
12. `results/` is untouched — it only ever holds live numbers, and there is no key
    wired in. Producing the first live scorecard stays a separate, key-gated task.

### Out of scope for this batch

- `rag`, `human_in_the_loop`, `durable_state` arenas (HITL and durable_state need
  a harness resume/checkpoint API — a design step of their own).
- `crewai` verification (needs a 3.12 machine).
- Live scorecards (need `OPENAI_API_KEY` in the `full-run` workflow).
- MkDocs site (Phase 4).
