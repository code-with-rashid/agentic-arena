# Pydantic AI — deep dive

## At a glance

- Package / repo: [`pydantic-ai`](https://github.com/pydantic/pydantic-ai) —
  pinned `pydantic-ai-slim[openai]==2.37.0`
- Licence: MIT
- Adapter: [`frameworks/pydantic_ai/adapter.py`](../../frameworks/pydantic_ai/adapter.py)
- Status: mock-green on all seven arenas; no live scorecard yet

The `-slim` distribution plus the `openai` extra is deliberate. The full
`pydantic-ai` meta-package pulls provider SDKs (anthropic, google, bedrock, ...)
that no arena uses, which would misrepresent what the framework costs to adopt
for this task.

## Wiring notes

- **LLM:** `OpenAIChatModel(model, provider=OpenAIProvider(base_url=..., api_key=...))`.
  Points at the shared gateway with no special handling.
- **Tools:** `@agent.tool_plain` around the shared implementations, registered only
  for the tools the arena declares.
- **Metrics:** `result.usage` (`input_tokens`, `output_tokens`, `requests`); tool
  calls read from `ToolCallPart`s in `result.all_messages()`.

## The iteration budget trap

`Agent(retries=...)` reads like a loop cap. It is not — it is a
**tool/output-validation retry budget**. Setting it from `max_tool_iterations`
left this adapter effectively uncapped: measured against a mock that never stops
requesting tools, a budget of 6 produced **50** LLM calls, the library's default
`request_limit`.

The actual loop cap is a per-run usage limit:

```python
UsageLimits(request_limit=config.max_tool_iterations)
```

`tests/test_adapters_contract.py` measures the real number on the wire, so this
cannot regress silently.

## Deferred tools: the native pause

Pydantic AI's interrupt mechanism is **deferred tools**, and it is a different
shape from LangGraph's `interrupt`:

```python
@agent.tool_plain
def request_approval(summary: str) -> str:
    raise CallDeferred  # the run stops here
```

The run then finishes with a `DeferredToolRequests` output instead of a string —
which is why the adapter only widens `output_type` to
`[str, DeferredToolRequests]` for arenas that declare an interrupt tool. Resuming
passes the decision back:

```python
agent.run_sync(
    message_history=history,
    deferred_tool_results=DeferredToolResults(calls={call_id: "Decision: approve."}),
)
```

There is no checkpointer. Pydantic AI hands you the conversation and leaves
persistence to you, so the adapter serialises it with `ModelMessagesTypeAdapter`
and replays it as `message_history`. That is enough to pass `durable_state` — the
harness discards the runner there and only JSON survives — but it is **stateless
resume**, not checkpointing, and the feature matrix records it as 🟡 rather than ✅.

The trade-off is real and worth stating: this is simpler than a checkpointer and
leaves the storage decision to you, and it stops being comfortable once the state
outgrows a message list.

Two details the adapter has to get right, both asserted in
`tests/test_durable_state.py` and `tests/test_suspend_resume.py`:

- **A resumed run returns the whole conversation.** The harness sums cost across
  legs, so the second leg reports only messages added since the pause (`seen`
  slicing) or every tool call on a paused item is counted twice.
- **The interrupt tool is not logged as a tool call.** Asking for permission is
  the pause, not an action taken; the other adapters do not log it either, and
  `no_tool_before_suspend` compares them directly.

## Results

Mock mode only. Pass rates in mock mode are ~100% by construction and are **not**
a quality signal. The comparable columns are marked.

| Arena | Mode | Pass rate | Note |
|---|---|--:|---|
| `tool_use` | mock | 15/15 | 794 prompt tok/item, 1.05× baseline *(comparable)* |
| `structured_output` | mock | 15/15 | |
| `rag` | mock | 15/15 | |
| `multi_agent` | mock | 10/10 | single-agent role-play entry |
| `multi_agent` (`pydantic_ai_multi`) | mock | 10/10 | delegation pipeline — 3.57× / 3.00× *(comparable)* |
| `resilience` | mock | **8/8** | *(comparable)* — recovers from every scripted fault |
| `human_in_the_loop` | mock | 12/12 | native deferred tools |
| `durable_state` | mock | 8/8 | stateless resume across the rebuild |

> **Correction.** The `tool_use` row read *724 prompt tok/item, 0.96× baseline* —
> i.e. cheaper than the hand-rolled loop. It was cheaper because it was **sending
> less**: Pydantic AI reads a parameter description from `Field`, not from the
> docstring, so this adapter was shipping bare types where the arena had described
> every argument. With the schemas equalised it is 1.05×, and no framework is
> leaner than the baseline. See [tool-schemas.md](../tool-schemas.md).

### A second entry: `pydantic_ai_multi`

The same three roles as every other pipeline entry, wired as a delegation chain —
except that **Pydantic AI has no delegation feature**. There is no
`managed_agents` list and no `AgentTool` wrapper: the delegate is an ordinary
async tool whose body happens to `await sub_agent.run(...)`, and the library does
not know a sub-agent is involved.

It costs **3.57× the prompt and 3.00× the LLM calls** of the single-agent entry —
the same call multiplier as smolagents' `managed_agents`, and 2N at every depth
from one role to five. That agreement between three libraries that share no code,
one of which is not implementing a delegation feature at all, is what makes 2N a
property of the *shape* rather than of anyone's implementation: a sub-agent's
reply is a tool result, not the end of the run, so every delegator spends a second
call answering for itself afterwards.

It is also the cheapest chain measured in prompt terms — 1581 tokens at four roles
against smolagents' 13441 for the identical mechanism, which is what isolates that
gap as smolagents' templated system prompt rather than as the cost of starting a
sub-agent fresh. See
[multi-agent.md](../multi-agent.md#the-same-shape-without-a-delegation-feature-pydantic_ai_multi).

Nested runs share one `RunUsage`, which is what keeps the reported cost honest;
without it the pipeline would bill like a single agent while making six calls.
One consequence worth knowing: 2N at three roles is six LLM calls against a
default `max_tool_iterations` of six, so this mechanism spends the whole per-item
allowance where a handoff chain spends four of it.
