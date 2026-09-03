# The controls the arena owns, and who checks they arrive

## Why this page exists

Four fairness bugs of the same shape have been found in this repo, one at a
time, each after a published number had already been built on it:

| control | what was actually happening | found in |
|---|---|---|
| `max_tool_iterations` | three adapters' "loop caps" were not loop caps — a budget of 6 ran **50**, **41**, and one too many | [#29-ish](methodology.md#3b-one-iteration-budget) |
| `request_timeout_s` | **five of seven** never passed it to their client and inherited a ten-minute library default | [transport.md](transport.md#a-hung-provider-is-a-different-failure-and-five-adapters-were-deaf-to-it) |
| `arena.tools` (parameters) | two adapters declared a **narrower tool** than the arena did, dropping a parameter the model never saw | [tool-schemas.md](tool-schemas.md) |
| `arena.tools` (descriptions) | **all six** frameworks cut the sentence telling the model to pause — on the arena that grades pausing | [tool-schemas.md](tool-schemas.md#the-same-audit-on-the-pause-arenas-where-it-matters-more) |

Every one was invisible to mock mode, because the mock replays a script whatever
the adapter sent. Every one would have shown up live as a difference in the
framework's behaviour, and been attributed to the framework.

The pattern is not that adapters are careless. It is structural: a control the
arena owns has to be **carried** by each framework in its own idiom — a different
constructor argument, a different decorator, a different docstring convention —
and nothing was checking the carrying.

So this page enumerates the controls instead of waiting for the next one to
surface, and `tests/test_shared_controls.py` fails if a new one is added without
an answer.

## `ArenaConfig`

| field | does an adapter see it? | held to it by |
|---|---|---|
| `model` | **yes** | `tests/test_shared_controls.py` |
| `temperature` | **yes** | `tests/test_shared_controls.py` |
| `base_url` | **yes** | implicit — nothing reaches the mock otherwise |
| `api_key` | **yes** | not gated; a wrong key fails loudly live (401) rather than silently |
| `request_timeout_s` | **yes** | `tests/test_transport_faults.py` |
| `max_tool_iterations` | **yes** | `tests/test_adapters_contract.py` |
| `checkpoint_dir` | **yes**, durable arenas only | `tests/test_durable_across_a_restart.py` |
| `mode` | no — the harness starts the mock and rewrites `base_url` | — |
| `repeat` | no — the harness loops | — |
| `price_input_per_m`, `price_output_per_m` | no — the scorecard multiplies afterwards | — |

## `ArenaSpec`

| field | held to it by |
|---|---|
| `system_prompt` | `tests/test_adapters_contract.py` — the instruction must come from the arena, not the adapter |
| `tools` (which) | `tests/test_adapters_contract.py` — no adapter may advertise a tool the arena did not declare |
| `tools` (shape) | `tests/test_tool_schema_fidelity.py` — same parameters, same types, descriptions intact |
| `dataset` | the harness iterates it; adapters never see it |
| `durable` | `tests/test_durable_state.py` and `tests/test_durable_across_a_restart.py` |

## The gates on this page

**Every `ArenaConfig` and `ArenaSpec` field is accounted for.** Adding one now
fails until someone has said which test holds adapters to it, or recorded that
the harness consumes it and no adapter ever sees it. Cheap, and it is the half
that would have caught all four bugs above at the moment the control was
introduced rather than iterations later.

`tools` is worth noting: it is one field that went wrong **twice**, in different
ways — first the *set* of tools an adapter advertised, then their *shape*. So it
names both tests. "`tools` is checked" was true, and insufficient, the first
time.

**The configured model is the model on the wire.** This is
[methodology §1](methodology.md#1-one-model-for-everyone) — *one model for
everyone, and no adapter picks its own* — and it was the last fundamental rule
with nothing behind it.

An adapter that quietly defaulted to its library's favourite model would be
comparing **a different model**, which is the one difference that invalidates
every number at once. It is also the one mock mode is least able to notice: the
mock answers to any model name at all.

Measured across all seven: every adapter propagates it faithfully, including
`google_adk`, which has to reach an OpenAI-compatible gateway through LiteLLM and
so builds `openai/<model>` — LiteLLM strips the prefix and the name on the wire
is exactly what the arena configured. A negative result, pinned because of what
it would cost to be wrong about it later.

**The configured sampling temperature is the one on the wire.** [methodology
§3e](methodology.md#3e-one-sampling-temperature) — *"temperature is `0.0`
everywhere"* was the last item in that list held by convention rather than by a
field: ten hard-coded `temperature=0.0` literals, one per adapter, checked by
nothing. A framework left at its library default of `1.0` would sample
differently from the rest of the field in every live run, for a reason that has
nothing to do with the framework.

Measured across all thirteen buildable adapters: every one sends `0.0` today.
`ArenaConfig.temperature` is now the single source, and the gate builds each
adapter with a non-zero canary — a literal `0.0` left in an adapter sends the
wrong number and fails.

**No adapter puts a sampling parameter on the wire that the arena did not
choose.** Every request body is held to the envelope the hand-rolled baseline
sends — `model`, `messages`, `temperature`, `stream`, `tools`, `tool_choice` —
plus a per-adapter exception table. Measured: no adapter sets `top_p`, `seed`,
`max_tokens`, the penalties, `n`, `logprobs` or `response_format`; `smolagents`
alone adds `stop` (below). An adapter that started injecting `top_p=0.9` would be
comparing a different sampling distribution, and would fail here until the key
was removed or recorded with a reason.

## What is deliberately not gated

- **`api_key`.** It reaches the adapter, and a wrong one fails loudly live with a
  401 rather than silently skewing a comparison. There is no quiet failure to
  guard against.
- **`smolagents`' `stop` sequences.** It sends `stop: ["Observation:", "Calling
  tools:"]` on every request, in both its single- and multi-agent entries,
  because its text ReAct loop parses generation that halts at those markers. It
  is intrinsic to the mechanism, not a sampling choice, so it is an entry in the
  gate's exception table rather than a failure — the same treatment as
  `strict: true` and `title` on the tool schemas.
- **`tool_choice`.** Every adapter sends `"auto"` today. A framework that drove
  its loop with `"required"` or `"none"` would be a mechanism difference worth
  recording, not a fairness break — the arena does not dictate how a framework
  decides to call a tool, only which tools exist.
- **Adapter-side prompt framing.** Adapters may phrase the arena's instruction in
  whatever way is idiomatic — that difference *is* part of what is being
  compared. What they may not do is substitute their own task instruction, and
  that is gated.
- **Framework decoration of tool schemas.** `title`, `additionalProperties`,
  `strict: true` and OpenAI's strict-mode widening of `required` are framework
  properties. Reported in [tool-schemas.md](tool-schemas.md), not failures.

## Not measured

- **Mid-run drift, for the checks that only read the first request.** Worth
  stating precisely rather than sweepingly, because the checks differ:

  - `max_tool_iterations` is **aggregate** — the probe counts every request that
    reaches a mock which never stops asking for tools, so an adapter that raised
    its own budget halfway through still fails.
  - `model` is aggregate too: the assertion is over the set of model names across
    *every* request, not the first.
  - **tool schemas are read from the first request only.** An adapter that
    advertised the arena's tools correctly and then narrowed them later would not
    be caught. That is not purely hypothetical — the `_multi` handoff entries
    legitimately change the tool set mid-run when the speaker swaps, which is why
    the check is scoped to the opening request rather than extended naively.
  - `request_timeout_s` is measured on the first attempt's abandonment.
- **Live-mode-only controls.** `price_*` never leaves the harness, so nothing
  here says the cost column is right — only that the token counts feeding it are
  ([usage accounting](findings.md#5-can-the-numbers-themselves-be-trusted)).
