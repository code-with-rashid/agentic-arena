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
| `tool_use` | mock | 15/15 | 724 prompt tok/item, 0.96× baseline *(comparable)* |
| `structured_output` | mock | 15/15 | |
| `rag` | mock | 15/15 | |
| `multi_agent` | mock | 10/10 | single-agent role-play entry |
| `resilience` | mock | **8/8** | *(comparable)* — recovers from every scripted fault |
| `human_in_the_loop` | mock | 12/12 | native deferred tools |
| `durable_state` | mock | 8/8 | stateless resume across the rebuild |
