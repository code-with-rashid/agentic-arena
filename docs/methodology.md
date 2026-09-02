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

### Control tools are exempt

Some frameworks end their loop by *calling a tool* rather than by replying with
content — smolagents advertises a `final_answer` tool and treats a plain content
reply as "not finished yet". That tool carries no task capability: it is how the
framework returns a value, the way another framework returns from a function.

`arena.tools.CONTROL_TOOLS` names them (`final_answer` today). They are exempt
from the "only declared tools" rule, excluded from an adapter's reported
`tool_calls` so they cannot satisfy a `tool_used` check or inflate
`max_tool_calls`, and the mock server renders a scripted content turn as a
`final_answer` call for clients that advertise one. The exemption is deliberately
a fixed list, not a pattern: a framework cannot smuggle a capability past the
arena by naming a tool cleverly.

Handoff tools (`transfer_to_<agent>`) are exempt on the same grounds: delegating
grants no capability, because the receiving agent carries the same arena prompt
and only its own declared tools. They have to be matched by prefix rather than by
an exact name, since the target agent's name is part of the tool name, and
`arena/tools/__init__.py` records that weakening and what bounds it.

There is a third shape with no name pattern at all: smolagents' `managed_agents`
advertises a sub-agent as a tool **named after the sub-agent**, so `writer` is
indistinguishable from a task tool by inspection. An adapter that does this must
list those names on itself (`Adapter.delegates`) — a deliberately awkward,
reviewable declaration rather than a pattern, so a reader sees exactly which
extra names an adapter is claiming. The declaration is checked rather than
trusted: `check_declared_delegates` refuses one that covers a tool any arena
declares, so an adapter cannot exempt `search` by calling it a delegate.

They are **not** excluded from prompt-size accounting. A framework that must
advertise an extra tool on every request really does pay for it — for handoffs
that turns out to be *most* of what delegation costs, see
[multi-agent.md](multi-agent.md) — and [overhead.md](overhead.md) reports what it
costs elsewhere.

## 3b. One iteration budget

`ArenaConfig.max_tool_iterations` caps how many LLM calls an adapter may spend on
one item. It is a fairness control, not a safety valve: an adapter allowed to
grind for fifty calls while another stops at six will post better pass rates and
far worse latency, token and cost numbers, and none of the four are comparable.

Each framework spells its cap differently and the mapping is easy to get wrong —
Pydantic AI's `Agent(retries=...)` is a tool-validation budget, not a loop cap,
and Agent Framework's tool loop is uncapped unless you set
`max_iterations`. `tests/test_adapters_contract.py` measures the real number: it
points each adapter at a mock that never stops requesting tools and counts the
requests that reach the wire. Adapters that exceed the budget fail CI.

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

### One task, many shapes of implementation

Some arenas name an architecture in the task — `multi_agent` asks for a
researcher → writer → editor pipeline. The eval stays mechanical and
shape-based (does the brief carry the right year and measurement, in three to
five sentences), so a framework may satisfy it with a real multi-agent
mechanism *or* a single agent that role-plays the roles. Both are valid
entries: the task, the tool set and the checks are identical, and the
difference — token count, LLM calls, how the orchestration reads — is the
finding. A single-agent entry on such an arena is named `<fw>` as usual; a
real-orchestration entry is named `<fw>-multi` so the two can be compared
directly.

`tests/test_adapters_contract.py` enforces these rules on the wire: it builds each
adapter against a sentinel arena and asserts, from the request bodies the mock
server actually received, that

- the arena's prompt reached the model,
- only the arena's declared tools were advertised,
- the adapter stopped at `max_tool_iterations`,
- the tool result reached the model **byte-for-byte** (a framework that truncates
  or re-wraps tool output stays green in mock mode and scores near zero live),
- the tool ran on the arguments the model asked for,
- each request replays the whole transcript, not just the newest message.

These only mean something against the real libraries, and the `dev` extra pulls
no framework — so they run in the `comparison` CI job, which installs every
adapter and sets `ARENA_EXPECT_FRAMEWORKS` so a broken install fails loudly
instead of silently shrinking the matrix back to `vanilla`.

### Testing grounding without a judge

"Did the agent answer from the corpus or from the model's memory?" sounds like
it needs an LLM judge. It does not. The `rag` arena's unanswerable items ask
about a fact the corpus genuinely lacks but the model almost certainly knows —
Gustave Eiffel's year of birth, the Statue of Liberty's sculptor — and pair a
refusal `iregex` with a `not_contains` on the **real-world answer**. An agent
that grounds itself refuses and passes; an agent that falls back on parametric
memory produces a factually correct answer and fails.

The trap has to be kept honest, because a check that nothing can fail is worse
than no check at all: `tests/test_rag_arena.py` scores a deliberately
hallucinated answer against each of those items and asserts it fails on the
`not_contains`, not merely on the refusal phrasing.

## 5. What mock mode does and does not tell you

Mock mode proves an adapter wires the model, the tools, and the loop together
correctly. It is **not** a quality signal:

- Pass rate in mock mode is ~100% by construction (the script feeds correct turns).
- Latency in mock mode is loopback plus framework startup, not model time.

Only `--mode live` runs produce quality numbers worth publishing. `results/`
should only ever contain live scorecards.

There are exactly two exceptions, and both work for the same reason: the thing
that varies between adapters is the framework, not the model.

### Exception 1: `resilience` pass rates

The `resilience` arena's mock script injects **scripted faults** — malformed tool
arguments, a tool that does not exist, a required argument omitted. The fault is
byte-identical for every framework and the mock is deterministic, so nothing
about the *model* varies. Any difference in outcome is the framework's own error
handling, which is exactly what is being measured.

So mock-mode `resilience` results *are* comparable, while mock-mode `tool_use`
and `structured_output` pass rates are not. Frameworks are expected to score
differently here, so CI reports the table rather than requiring a clean sweep —
it fails only if the stdlib baseline stops recovering, which would mean the arena
itself is broken.

### Exception 2: prompt size

Every adapter is handed the same arena prompt and the same tool definitions, and
the mock replays identical turns, so the size of the request each framework puts
on the wire is the framework's own serialisation cost. A provider bills for it.
Measured on `tool_use`, the spread is ~1.15× end to end, driven entirely by how
verbosely each library renders the same two tool schemas — see
[overhead.md](overhead.md) and the `comparison` CI job.

This only holds because the mock counts what a provider would bill: `messages`
**and** `tools`. Counting messages alone — which is what it did until
`arena/llm/mockserver.py` was fixed — understated every prompt by ~1.8× and
reported all five frameworks as identical, because the tool block was the only
thing that differed.

Completion tokens and LLM-call counts in mock mode are scripted, so they are
identical by construction and carry no signal at all.

### Cost numbers are checked, not trusted

Every comparison in this repo is built on adapters reporting their own token and
LLM-call usage. That is a claim by the framework, and an adapter that under-reports
posts better overhead and cost numbers than it earned **while every correctness
check still passes** — the scorecard stays green and the comparison quietly lies.

So the mock server records what it actually served, and
`tests/test_usage_accounting.py` holds each adapter's `AgentResult` against it.
The suspend/resume path is tested separately, because that is where this class of
bug lives: the harness sums cost across legs, so a leg counted twice doubles an
item and a leg sliced away vanishes from it.

Three real bugs of exactly this shape have been found here — `openai_agents`
reporting usage cumulatively after a resume, `smolagents` resetting its usage
monitor inside `run()`, and `langgraph` slicing counted messages by index, which
is correct for `human_in_the_loop` and dropped all of leg two on `durable_state`.
None of them affected a single pass/fail result.

## 6. Metrics

Per adapter, per arena:

| Metric | Source |
|---|---|
| Pass rate | scorer, over `dataset x repeat` |
| Errors | items where the adapter raised or timed out |
| Mean latency | wall-clock per item, measured by the harness |
| Mean tokens | prompt + completion, from gateway `usage` (summed across LLM calls). Prompt covers `messages` **and** the `tools` schemas, because both are billed |
| Mean LLM calls | number of chat completions per item |
| Est. cost | `mean_tokens` split by `ARENA_PRICE_*` per-1M rates |

Run with `--repeat 10` for reliability/variance work; single-repeat numbers are
directional only.

### Reporting repeats

Repeats are not averaged away silently. When `--repeat > 1` the scorecard also
carries:

| Metric | Meaning |
|---|---|
| `pass_rate_stddev` | population standard deviation of the per-repeat pass rate, shown as `±` next to the pass rate |
| `pass_rate_by_repeat` | the individual per-repeat rates (json/csv) |
| `unstable_items` | items that passed on some repeats and failed on others, listed by id |

The distinction that matters: an item failing *every* repeat is reproducible and
merely wrong; an item that flips between repeats makes its contribution to the
headline pass rate irreproducible. Only the second kind is reported as unstable,
and a scorecard with a non-zero count should be read as provisional.

## 7. Pausing for a human

Some capabilities cannot be read off a final answer. "Did the agent stop and ask
before doing something consequential?" is one: an agent can *write* "I would need
approval for this" and book the room anyway, and a text check cannot tell that
apart from a real pause.

So the pause is **observed by the harness, not claimed by the agent**. An adapter
that supports it implements the optional `arena.types.ResumableRunner`: `run()`
may come back with `suspended=True` and an opaque `resume_state`, and the harness
then calls `resume(item, state, decision)`. Three rules make that comparable:

- **The decision is part of the frozen eval set.** `EvalItem.resume_with` is
  `"approve"` or `"deny"`, fixed per item. The agent cannot influence it and it
  is not derivable from the prompt, so skipping the pause cannot be guessed past.
- **Cost is summed across legs.** A framework that pauses and resumes re-sends
  the transcript and pays for it. Charging only the final leg would make an
  interrupting framework look cheaper than one that runs straight through.
- **Not implementing it is reported as unsupported, not as failure.** If an arena
  declares the `request_approval` tool and an adapter has no `resume`, the
  framework is marked unavailable for that arena with a reason. "No interrupt
  mechanism wired up" and "tried to pause and got it wrong" are different
  findings and must not be averaged into one number.

Adapters may satisfy the contract natively (a framework with real interrupts and
a checkpointer) or by **emulation** (carrying the transcript back in, which is
what the `vanilla` baseline does). Both are valid entries; which one an adapter
uses is a feature-matrix fact.

### Durable arenas: the runner is thrown away

`arena.toml` can set `durable = true`. At the pause the harness then

1. **JSON round-trips `resume_state`**, exactly as a crash would. An adapter that
   tried to hand back a live object gets a clear error instead of a pass, because
   no restarted process could ever hold that reference.
2. **Discards the runner and builds a new one** from the same adapter and config.

So only two things cross the gap: what the adapter wrote to
`config.checkpoint_dir` (a store the harness owns and hands identically to every
framework), and what it serialised into `resume_state`. Stateless resume — putting
the whole transcript in the state — is a legitimate way to be durable and the
baseline does exactly that; a framework checkpointer is a different mechanism
reaching the same bar, and the feature matrix records which is which.

The check that makes this real is `call_counts`: exact tool-call counts across the
merged legs. An adapter that starts over after the crash reaches the right answer
by redoing both lookups, and fails on the counts. Measured: an adapter patched to
restart instead of resume goes from 8/8 to **0/8**.

## 8. Reproducing a published scorecard

Every `results/<arena>/scorecard.md` records the model, harness version, Python
version, date, dataset size, and repeat count. Re-running `full-run` with the same
inputs and the pinned `requirements.txt` should reproduce it within model
nondeterminism (which `--repeat` quantifies).
