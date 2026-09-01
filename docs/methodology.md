# Methodology

The value of `agentic-arena` is that the comparison is *fair* and *reproducible*.
These are the rules that make it so. A change that breaks one of them is a bug.

## 1. One model for everyone

`ArenaConfig.model` is passed to every adapter in a run. No adapter selects its own
model, temperature schedule, or provider. Temperature is `0.0` everywhere. If a
framework cannot be pinned to a single model, that is a finding — note it in the
adapter README and the feature matrix.

## 2. One gateway

Every adapter talks to an OpenAI-compatible endpoint at `ArenaConfig.base_url`:

- **mock mode** — the harness starts `arena.llm.mockserver` and points `base_url` at
  it. No network, no key, deterministic.
- **live mode** — `base_url` is a real provider (or a proxy like LiteLLM in front of
  several). The same model id must be valid there.

Routing every framework through one gateway is what lets the mock stand in for a
real model and what keeps provider-side variables out of the comparison.

## 3. One set of tools

`arena.tools.search` and `arena.tools.calculator` are the only tools. `search` runs
over a fixed local corpus (`arena/tools/corpus.json`); `calculator` is a tiny safe
arithmetic evaluator. Adapters register these with their framework's own tool
mechanism but **must not** change what they compute or add tools. Measuring
framework overhead means holding the tools constant.

## 4. One task spec + eval set per arena

`arenas/<id>/arena.toml` defines the task and `dataset.jsonl` the graded items. An
item passes when **every** check passes. Checks are mechanical (`contains`,
`iregex`, `numeric_equals` with tolerance, `tool_used`, ...). Anything that needs an
LLM judge belongs in a separate arena that is clearly labelled as such, because
judge noise is not comparable across frameworks.

### System prompts

Each adapter writes its own system prompt, in whatever style is idiomatic for the
framework, guided by `arena.toml`'s `system_prompt_intent`. That difference is part
of what is being compared, so every adapter's prompt is checked in next to its
`adapter.py` for inspection. Prompts must not encode answers or item-specific hints.

## 5. What mock mode does and does not tell you

Mock mode proves an adapter wires the model, the tools, and the loop together
correctly. It is **not** a quality signal:

- Pass rate in mock mode is ~100% by construction (the script feeds correct turns).
- Token and latency numbers in mock mode reflect how the framework's client
  serialises requests and its own overhead — not real model usage.

Only `--mode live` runs produce numbers worth publishing. `results/` should only
ever contain live scorecards.

## 6. Metrics

Per adapter, per arena:

| Metric | Source |
|---|---|
| Pass rate | scorer, over `dataset x repeat` |
| Errors | items where the adapter raised or timed out |
| Mean latency | wall-clock per item, measured by the harness |
| Mean tokens | prompt + completion, from gateway `usage` (summed across LLM calls) |
| Mean LLM calls | number of chat completions per item |
| Est. cost | `mean_tokens` split by `ARENA_PRICE_*` per-1M rates |

Run with `--repeat 10` for reliability/variance work; single-repeat numbers are
directional only.

## 7. Reproducing a published scorecard

Every `results/<arena>/scorecard.md` records the model, harness version, Python
version, date, dataset size, and repeat count. Re-running `full-run` with the same
inputs and the pinned `requirements.txt` should reproduce it within model
nondeterminism (which `--repeat` quantifies).
