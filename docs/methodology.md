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

Which of them are available is per-arena: `arena.toml`'s `tools` list. An adapter
registers exactly those (`arena.tools.names_for` / `specs_for` resolve the list) —
handing an agent a tool the arena did not declare lets one framework solve a task
in a way another cannot, which is the same fairness break as swapping the model.

## 4. One task spec + eval set per arena

`arenas/<id>/arena.toml` defines the task and `dataset.jsonl` the graded items. An
item passes when **every** check passes. Checks are mechanical (`contains`,
`iregex`, `numeric_equals` with tolerance, `tool_used`, ...). Anything that needs an
LLM judge belongs in a separate arena that is clearly labelled as such, because
judge noise is not comparable across frameworks.

### System prompts

The task instruction comes from the arena, via `ArenaSpec.system_prompt` (derived
from `arena.toml`'s `system_prompt_intent`). An adapter **must not hard-code one**:
a hard-coded prompt asks for the wrong thing the moment the harness runs that
adapter on a different arena, and mock mode cannot catch it, because the mock
script replays correct turns no matter what the prompt said.

Adapters may add framework-idiomatic framing around that instruction (a role, a
backstory, a typed result model); that difference is part of what is being
compared. Prompts must not encode answers or item-specific hints.

`tests/test_adapters_contract.py` enforces both rules on the wire: it builds each
adapter against a sentinel arena and asserts, from the request body the mock
server actually received, that the arena's prompt reached the model and that only
the arena's declared tools were advertised.

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
