# Agentic Arena

[![ci](https://github.com/code-with-rashid/agentic-arena/actions/workflows/ci.yml/badge.svg)](https://github.com/code-with-rashid/agentic-arena/actions/workflows/ci.yml)
[![docs](https://github.com/code-with-rashid/agentic-arena/actions/workflows/docs.yml/badge.svg)](https://github.com/code-with-rashid/agentic-arena/actions/workflows/docs.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![license](https://img.shields.io/github/license/code-with-rashid/agentic-arena)](LICENSE)

**Learn agentic systems, build a harness from first principles, and compare frameworks with evidence you can regenerate.**

[Open the interactive field guide →](https://code-with-rashid.github.io/agentic-arena/)

Agentic Arena has four separate spaces so you can focus on one job at a time:

| Space | Use it when you want to |
|---|---|
| [Learn](https://code-with-rashid.github.io/agentic-arena/learn/) | understand the concepts in a deliberate order |
| [Build](https://code-with-rashid.github.io/agentic-arena/build/) | create a framework-neutral harness and make it reliable |
| [Compare](https://code-with-rashid.github.io/agentic-arena/compare/) | inspect measured findings and choose components |
| [Reference](https://code-with-rashid.github.io/agentic-arena/reference/) | look up run modes, methods, controls, and commands |

## What is in the repository?

The project combines a concept-first field guide with a reproducible comparison
lab. Shared workloads run through framework adapters while the model, tools,
datasets, and scoring stay fixed. The differences that remain expose framework
overhead, retries, tool behavior, orchestration, pause/resume support, and
durability.

```text
arena/              comparison harness and scoring
arenas/             shared evaluation workloads
frameworks/         framework adapters
docs/               public field guide
examples/harness/   executable build-from-scratch lessons
knowledge/          Obsidian research and project memory
results/            published native live scorecards
```

## Try the lab in five minutes

Python 3.11 or newer is required. The core harness has no runtime dependencies.

```bash
git clone https://github.com/code-with-rashid/agentic-arena
cd agentic-arena
python -m pip install -e .

# Run the dependency-free baseline against a deterministic local model.
python -m arena run --arena tool_use --framework vanilla --mode mock

# See coverage and the evidence that is comparable offline.
python -m arena summary --print
```

Use `python -m arena validate` to check every arena specification and dataset.

## Know what a run proves

| Mode | What it is for | Credentials |
|---|---|---|
| `mock` | adapter wiring and controlled framework mechanics | none |
| `codex` | real-model functional checks through a Codex subscription | Codex sign-in |
| `live` | native provider benchmarks for latency, usage, cost, and quality | provider API key |

Mock pass rates are not answer-quality rankings. Codex mode is not a native API
cost or latency benchmark. Only repeated `live` runs belong in published
scorecards. The [run-mode guide](https://code-with-rashid.github.io/agentic-arena/reference/run-modes/)
explains the evidence boundary.

## What is covered?

The lab currently exercises:

- tool use and schema fidelity
- structured output
- recovery from malformed calls and provider failures
- multi-agent orchestration and delegation cost
- retrieval and grounded answers
- human approval and pause/resume
- durable state across process restarts
- behavior at authority and execution boundaries

Adapters cover a dependency-free baseline plus LangGraph, Pydantic AI, OpenAI
Agents SDK, Microsoft Agent Framework, smolagents, Google ADK, and CrewAI.
Claude Agent SDK is documented as a protocol mismatch with the shared
OpenAI-compatible gateway. See the [framework profiles](https://code-with-rashid.github.io/agentic-arena/frameworks/)
for current support and the [measured findings](https://code-with-rashid.github.io/agentic-arena/findings/)
for results.

## Run with a real model

For a native OpenAI-compatible endpoint, copy `.env.example` to `.env`, set the
provider URL, key, and model, then install the adapter you want to test:

```bash
python -m pip install -r frameworks/langgraph/requirements.txt
python -m arena run --arena tool_use --framework langgraph --mode live --repeat 3
```

If you have a ChatGPT/Codex subscription but no API key, sign in with the Codex
CLI and run a functional check:

```bash
python -m arena run --arena tool_use --framework vanilla --mode codex
```

Read the [Codex bridge guide](https://code-with-rashid.github.io/agentic-arena/codex-bridge/)
before interpreting those results.

## Contribute

Good contributions make one claim easier to understand or verify: improve a
lesson, add a workload, implement an adapter, reproduce a result, or challenge a
methodological assumption. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and the
[next phases](https://code-with-rashid.github.io/agentic-arena/next-phases/).

The research vault under [`knowledge/`](knowledge/README.md) records ecosystem
projects, decisions, experiments, and direction. Open that directory in Obsidian
when you need the project’s deeper working memory.

Apache-2.0 licensed.
