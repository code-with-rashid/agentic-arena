# agentic-arena

> Compare, explore, and choose the right agentic framework — with numbers you can regenerate.

There are plenty of blog-post comparisons of agent frameworks. Almost none of them
are **reproducible**. `agentic-arena` implements the *same* reference agent tasks
("arenas") across every major framework, runs them through one shared harness, and
produces scorecards you can regenerate yourself with one command.

- **Same fight for everyone.** Every framework gets the same model, the same tools,
  the same task spec, and the same eval set. You measure framework overhead, not
  tool quality or prompt luck.
- **Runs offline.** A built-in mock LLM (OpenAI-compatible) lets the whole harness
  run in CI with zero API spend. Point it at a real provider for real numbers.
- **Honest scorecards.** Pass rate vs. a graded eval set, latency, token usage,
  estimated cost, retries, and crashes — plus a feature matrix for the things that
  don't reduce to a number.

> **Status:** early but moving. Phase 0 (scaffold) is done; Phase 1 (harness +
> `tool_use`) and Phase 2 (framework breadth) are largely there — five adapters run
> green against the mock, and a second arena (`structured_output`) has landed. No
> live scorecard yet (needs an API key). See [ROADMAP.md](ROADMAP.md) and
> [docs/next-phases.md](docs/next-phases.md). Contributions for empty framework ×
> arena cells are very welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Quickstart

```bash
# 1. Clone and install the harness (Python 3.11+; no framework deps needed for the mock run)
git clone https://github.com/code-with-rashid/agentic-arena
cd agentic-arena
python -m pip install -e .

# 2. Run the tool-use arena for the dependency-free baseline adapter, against the mock LLM
python -m arena run --arena tool_use --framework vanilla --mode mock

# 3. Regenerate the scorecard from the last run
python -m arena scorecard --arena tool_use

# 4. Statically check every arena spec, dataset, and mock script (no LLM, no network)
python -m arena validate

# 5. One cross-arena view: coverage, plus the measurements that actually compare
python -m arena summary --print
```

To run a real framework against a real model:

```bash
python -m pip install -r frameworks/langgraph/requirements.txt
export ARENA_LLM_MODE=live
export OPENAI_BASE_URL=https://api.openai.com/v1      # or any OpenAI-compatible gateway
export OPENAI_API_KEY=sk-...
export ARENA_MODEL=gpt-4.1-mini                       # one model, same for every framework
python -m arena run --arena tool_use --framework langgraph --mode live --repeat 3
```

## The arenas

Each arena is a frozen spec plus a graded eval dataset. An adapter "passes" an item
when its output satisfies every check for that item.

| # | Arena | Exercises | Status |
|---|-------|-----------|--------|
| 1 | `tool_use` — single agent with web-search + calculator tools | tool-calling loop, baseline DX | ✅ spec + dataset + scorer |
| 2 | `structured_output` — look up a landmark, return a schema-checked JSON record | output validation, typing | ✅ spec + dataset + scorer |
| 3 | `resilience` — the model misbehaves on purpose; the agent must recover | error handling, graceful degradation | ✅ spec + dataset + scorer |
| 4 | `multi_agent` — researcher → writer → editor pipeline | orchestration, handoffs | ✅ spec + dataset + scorer (single-agent baseline) |
| 5 | `rag` — agent over a fixed local corpus; single-hop, multi-hop, and unanswerable | retrieval integration, grounding | ✅ spec + dataset + scorer |
| 6 | `human_in_the_loop` — approval gate, pause + resume | interrupts, HITL | ✅ spec + dataset + scorer (`langgraph` native, `vanilla` emulated) |
| 7 | `durable_state` — resume after a crash | checkpointing, durability | ✅ spec + dataset + scorer (`langgraph` + `vanilla`) |

## The frameworks

| Framework | Adapter | Language | Notes |
|-----------|---------|----------|-------|
| _baseline_ `vanilla` | ✅ | Python (stdlib) | hand-rolled agent loop; the "what does the framework buy you?" control |
| LangGraph | ✅ | Python | graph/state-machine orchestration |
| CrewAI | ⚠️ written | Python | role-based crews; adapter written, not yet mock-verified (needs Python 3.12) |
| OpenAI Agents SDK | ✅ | Python | `openai-agents`; tracing disabled for the arena |
| Pydantic AI | ✅ | Python | `pydantic-ai-slim`; typed, model-agnostic |
| Microsoft Agent Framework | ✅ | Python | `agent-framework-openai` (merged AutoGen + Semantic Kernel) |
| smolagents | ✅ | Python | `smolagents[openai]`; `ToolCallingAgent` — ends its loop by calling `final_answer` |
| Google ADK | ✅ | Python | `google-adk` + `litellm` (required to leave Gemini); the only real loop cap out of the box |
| Claude Agent SDK | 🚫 stub | Python | drives the `claude` CLI over the Anthropic Messages API — doesn't fit the shared OpenAI-compatible gateway ([why](frameworks/claude_agent_sdk/README.md)) |

Seven adapters run against the mock across seven arenas. `vanilla` and
`pydantic_ai` are green on all seven; `langgraph` and `openai_agents` are green on
all but one `resilience` item each; `microsoft_af` pauses (12/12) but is *unsupported* on `durable_state`;
`smolagents` and `google_adk` are *unsupported* on both pause arenas rather than
failing them.
The next contribution step is a live scorecard (needs an API key).

## How comparison stays fair

See [docs/methodology.md](docs/methodology.md) for the full rules. In short:

1. **One model.** `ARENA_MODEL` is passed to every adapter. No adapter picks its own.
2. **One set of tools.** `arena.tools` provides the search and calculator
   implementations. Adapters wire them into their framework but do not change what
   they do.
3. **One task spec + eval set per arena.** Adapters may phrase the system prompt in
   whatever way is idiomatic for the framework; that difference *is* part of what's
   being compared, and prompts are checked into each adapter for inspection.
4. **Mock mode tests plumbing, live mode tests behavior.** Mock-mode pass rates are
   not a quality signal — they only prove the adapter wires everything together.
   Only `--mode live` numbers go in published scorecards.
5. **Cost numbers are checked, not trusted.** The mock records what it served, and
   CI holds every adapter's self-reported usage against it — including across a
   suspend/resume, where the harness sums legs. An adapter that under-reports would
   otherwise post better numbers than it earned with a fully green scorecard.

Three things mock mode *can* compare honestly, because the model is held identical
and only the framework varies: the `resilience` arena's recovery rates,
[how much each framework puts on the wire](docs/overhead.md) for the same task
(a ~1.15× spread among five, and **3.77×** for smolagents), and whether an adapter
can genuinely pause for a human. CI prints all three on every run, and
`python -m arena summary` collects them.

## What has been measured so far

No live scorecard exists yet, so **nothing here is about answer quality**. What
*is* measured, offline and reproducibly:

- The hand-rolled baseline is **not** the cheapest on the wire — three of five
  frameworks serialise the same tool schemas more compactly.
- Prompt overhead is a 1.15× band for five frameworks, and **3.77×** for
  smolagents, whose templated system prompt is resent on every request and
  re-describes the tools it has already sent as a schema.
- Under eight scripted faults, LangGraph and the OpenAI Agents SDK each lose one
  item and smolagents loses four — exactly the four its tool validator rejects
  before the tool body runs, which it never writes back into the conversation.
- Five frameworks pause for a human, by five genuinely different mechanisms, all
  producing an identical trace to the scorer. Four of the five also survive the
  process being killed; Agent Framework's pause does not.
- Splitting one agent into a three-role pipeline costs **2× the LLM calls and
  ~2.5× the prompt tokens** — and costs that whether you build it with a graph
  library or a `for` loop. LangGraph's orchestration machinery itself adds
  nothing measurable.
- A native handoff chain costs ~10% more again, and **94% of that is the
  `transfer_to_*` schemas riding on every request** rather than the transfers
  themselves: you pay for a handoff by advertising it, not by taking it
  ([multi-agent.md](docs/multi-agent.md)).

[**docs/decision-guide.md**](docs/decision-guide.md) has the tables, the adoption
gotchas found while writing each adapter, and a clear split between what is
measured and what is merely claimed upstream.

## Repo layout

```
arena/            the shared harness (installable package)
  llm/            OpenAI-compatible client + stdlib mock server
  tools/          deterministic search + calculator handed to every adapter
arenas/<name>/    arena.toml spec + dataset.jsonl + mock_script.json
frameworks/<name>/ one adapter.py per framework implementing the Framework protocol
results/          generated scorecards (json + markdown + csv)
docs/             methodology, decision guide, feature matrix, per-framework deep dives
```

## License

[Apache-2.0](LICENSE).
