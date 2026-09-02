# smolagents

[Adapter](../../frameworks/smolagents/adapter.py) · `smolagents[openai]==1.26.0` ·
runs 5 of 7 arenas

Hugging Face's minimal agent library. The arena uses `ToolCallingAgent` (the
native-tool-calling agent) rather than `CodeAgent`, because `CodeAgent` answers by
writing and executing Python, which is a different task shape and not comparable
with the other five adapters on tool calls.

## Wiring

```python
model = OpenAIServerModel(
    model_id=config.model,
    api_base=config.base_url,
    api_key=config.api_key,
    temperature=0.0,
)
agent = ToolCallingAgent(
    tools=_make_tools(_tool_names(arena.tools)),
    model=model,
    instructions=arena.system_prompt,
    max_steps=max(1, config.max_tool_iterations - 1),
    verbosity_level=0,
)
```

Four things cost real debugging time.

### The `[openai]` extra is not optional

`pip install smolagents` gives you a package where `OpenAIServerModel` raises at
construction. The `openai` extra is what supplies it. Pinned in
[requirements.txt](../../frameworks/smolagents/requirements.txt) with that note,
because the failure mode reads like a bad import, not a missing extra.

### `max_steps` is off by one

`smolagents` makes one model call *beyond* `max_steps` — a final attempt once the
budget is spent. On a budget of 6 it sent 7 requests. `max_steps = N - 1` yields
exactly the N LLM calls every other adapter gets, which the contract test in
`tests/test_adapters_contract.py` enforces against a mock that never stops asking
for tools.

### Token usage: sum the steps, do not diff the monitor

`agent.monitor` looks like the obvious source, but `run(reset=True)` calls
`monitor.reset()`, so a before/after subtraction silently produces garbage (it
gave 2639 / 0 / 4 on a run that really cost far less). Summing each step's
`step.token_usage` is both correct and strictly better: it also counts steps whose
tool call *failed*, which is exactly the cost `resilience` is trying to measure.

### An exhausted run returns `""`, not an exception

When the step budget runs out, `agent.run()` returns an empty string and the
error lives on the last memory step. Without surfacing it the arena records a
silent blank answer. The adapter promotes the last `step.error` to
`AgentResult.error` when the output is empty, which is how `res-02` below reads as
`AgentMaxStepsError: Reached max steps.` instead of as nothing at all.

## Two protocol differences the harness had to accommodate

Both are framework facts, not adapter choices, and both are handled the same way
the CrewAI text-ReAct accommodation was — by teaching the *mock* to speak the
client's protocol, never by giving the agent a capability the arena withheld.

**It ends the loop by calling a tool.** `smolagents` advertises its own
`final_answer` tool and reads a plain content reply as "not finished yet".
Un-accommodated, every item burned its whole step budget where 2 requests were
scripted. The mock now renders a scripted content turn as a `final_answer` call
for any client that advertises one
(`arena.llm.mockserver._wants_final_answer_tool`), and `arena.tools.CONTROL_TOOLS`
keeps that call out of the adapter's reported `tool_calls` so it cannot satisfy a
`tool_used` check or blow a `max_tool_calls` cap. See
[methodology.md §3](../methodology.md#control-tools-are-exempt).

**Tool results come back as `user` messages.** Not `role: "tool"`, and with list
content-parts rather than a string. The wire-level contract tests were keyed on
`role == "tool"`; they now locate the tool result by content and flatten
content-parts, so they still assert the same thing — that the tool's output
reaches the model unaltered — for every adapter.

## Results *(comparable columns marked)*

| arena | result |
|---|---|
| `tool_use` | 15/15 |
| `structured_output` | 15/15 |
| `rag` | 15/15 |
| `multi_agent` | 10/10 |
| `resilience` | **4/8** *(comparable)* |
| `human_in_the_loop` | unsupported — no `resume` method |
| `durable_state` | unsupported — no `resume` method |

Mock pass rates are ~100% by construction and prove only correct wiring. The two
columns that compare frameworks honestly are `resilience` and prompt size.

### Prompt size: 3.90× baseline *(comparable)*

The other six adapters sit within a 1.15× band. `smolagents` is at **3.90×**
(2936 estimated prompt tokens per item against `vanilla`'s 754), and the cause is
entirely its templated system prompt — 3932 characters where the arena asked for
384, resent on every request. The arena's instruction survives verbatim inside it,
but it is under 10% of what goes out; the rest is a framework preamble, two worked
examples, a trailing rules block, and a **prose restatement of the same tools that
are already in the OpenAI `tools` schema**. Full breakdown in
[overhead.md](../overhead.md#smolagents-390-and-it-is-all-system-prompt).

Its completion tokens are also higher (74.7 vs 45.1) for a related reason: the
final answer leaves as a JSON tool call rather than as plain content.

This is not waste in the abstract — that scaffolding is what drives weaker models
through a tool loop without native tool-calling support. It is waste if you pair
it with a model that already tool-calls well.

### `resilience`: 4/8, split exactly along one line

The four losses are not "the model gave up". They divide perfectly on a single
question: **does the failure reach the transcript?**

| item | fault | recorded? | result |
|---|---|---|---|
| `res-01` | malformed JSON arguments | yes | pass |
| `res-03` | tool ran, returned `ERROR` | yes | pass |
| `res-06` | tool ran, returned `No results.` | yes | pass |
| `res-07` | tool ran, evaluator refused | yes | pass |
| `res-02` | tool name does not exist | **no** | fail |
| `res-04` | required argument missing | **no** | fail |
| `res-05` | argument not in the schema | **no** | fail |
| `res-08` | arguments serialised as `null` | **no** | fail |

The dividing line is `smolagents`' own **tool-validation layer**. Anything that
gets as far as running the tool comes back as an observation and lands in the
conversation; anything the dispatcher rejects first — unknown name, missing
argument, unexpected argument, null arguments — raises and is dropped.

The evidence is on the wire. On all four failures every request after the first
sent exactly `['system', 'user']` — the prompt never changes, so the model emits
the identical bad call five times in a row, verbatim:

```
Argument expr is required
Argument expr is required
Argument expr is required
Argument expr is required
Argument expr is required
Reached max steps.
```

On all four passes the second request carried
`['system', 'user', 'assistant', 'user']`. The attempt was recorded, the model
could see what it had done, and it corrected on the next turn.

So this is not about error severity, and `res-01` proves it: malformed JSON is the
*least* structured failure of the eight and it recovers, because it is handled at
parse time and written back. Self-correction is impossible without the feedback,
and four of these eight faults never produce any.

### `managed_agents`: the same design decision, again

`managed_agents` advertises a sub-agent as an ordinary tool named after itself;
calling it runs a whole nested agent and returns its answer. Measured with no
delegation happening at all, characters of system prompt plus tool schema:

| sub-agents offered | system prompt | tool schemas | total | marginal |
|---:|---:|---:|---:|---:|
| 0 | 3311 | 518 | 3829 | — |
| 1 | 4102 | 982 | 5084 | +1255 |
| 2 | 4498 | 1455 | 5953 | +869 |
| 3 | 4900 | 1934 | 6834 | +881 |

**~875 characters per offered sub-agent, on every request, whether or not anyone
delegates.** (The larger first step is a ~385-char preamble that switches
delegation on and is paid once.)

The marginal cost splits into ~400 characters of prose and ~475 of JSON schema,
because each sub-agent is described **twice** — the same double transmission as
the tools above, in a second place. It is the single most consistent thing about
this framework's wire behaviour.

For scale: the OpenAI Agents SDK charges 262 characters to offer a handoff, so
this is 3.3× to hold open the same option.

**Taking the delegation costs more too — and here that is the framework's
architecture, not its prompting.** `smolagents_multi` runs the same three roles
as the other pipeline entries and spends **6 model calls where they spend 4**
(4.03× / 3.00× against the single-agent entry, where every other mechanism is
~2.5× / 2.00×). A sub-agent's reply is a *tool result*, not the end of the run,
so the manager is still going and has to produce its own final answer once the
sub-agent returns. Every level of nesting costs one extra call. See
[multi-agent.md](../multi-agent.md#a-third-shape-the-sub-agent-invoked-as-a-tool).

Context does not travel either: a managed sub-agent starts a fresh conversation
and receives only the task string, where a speaker-swapping handoff inherits the
whole transcript. Passing findings down the chain is something you do by hand,
and pay for again.

### Two retry layers, and the outer one does not listen

`OpenAIServerModel` wraps the OpenAI client in `smolagents.models.Retrying`, so a
rate-limited call is retried at two levels:

| layer | attempts | first backoff | honours `Retry-After`? |
|---|---|---|---|
| the OpenAI client | 2 retries | ~0.5 s | **yes** |
| `Retrying` | `RETRY_MAX_ATTEMPTS = 3` | `RETRY_WAIT(60) x 2 x (1 + random())` = **120-240 s** | **no** |

The effect is that `smolagents` is the only adapter here that survives three
consecutive 429s - and it does so by blocking for **two to four minutes** on a
single item. Measured five times at 139 s, 160 s, 213 s, 220 s and 225 s, all
inside the bracket the constants predict.

Setting `Retry-After: 2` shortens the first two gaps to exactly 2.0 s and leaves
the third at 213 s, which is what pins the delay on the outer layer rather than
the client. Nothing the provider says can shorten it; only passing
`retry=False`, or a smaller `RETRY_WAIT`, would.

For a batch job that is a throughput collapse the scorecard cannot see, because
the item passes. For an interactive script it is arguably the right default. See
[transport.md](../transport.md).

**It applies to rate limits and nothing else.** `Retrying` is constructed with
`retry_predicate=is_rate_limit_error`, which lowercases the exception text and
looks for `429`, `rate limit`, `too many requests` or `rate_limit`. A hung
provider produces none of those, so the outer layer never engages: against a
20-second hang this adapter gives up in 8.5 s across 3 attempts, which is the
OpenAI client's own two retries and nothing more. "smolagents retries for
minutes" is true of exactly one status code.

One consequence worth noting: because the predicate matches on the *string*, a
provider whose 500 body happens to mention rate limiting would trigger the
minutes-long path too.

**Timeouts reach it only through `client_kwargs`.** `OpenAIServerModel` builds
its own client and takes no `timeout` of its own, so the adapter passes
`client_kwargs={"timeout": config.request_timeout_s}`. Without that line the
shared budget is silently ignored and the OpenAI client's ten-minute default
applies - which is what it was doing until
[the parity fix](../transport.md#a-hung-provider-is-a-different-failure-and-five-adapters-were-deaf-to-it).

## Not yet done

- **No pause support.** `smolagents` has no interrupt/approval primitive
  equivalent to LangGraph's `interrupt()` or the OpenAI SDK's `needs_approval`, so
  the adapter implements no `resume` and the two pause arenas report *unsupported*
  rather than failed. Emulating one by hand (as `vanilla` does) would measure the
  adapter, not the framework.
- **`CodeAgent` is unmeasured.** It is the library's headline agent and a
  genuinely different execution model. It needs its own arena entry, not a swap
  inside this one.
