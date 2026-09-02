# OpenAI Agents SDK — deep dive

## At a glance

- Package / repo: [`openai-agents`](https://github.com/openai/openai-agents-python) —
  pinned `openai-agents==0.22.0`
- Licence: MIT
- Adapter: [`frameworks/openai_agents/adapter.py`](../../frameworks/openai_agents/adapter.py)
- Status: mock-green on all seven arenas; no live scorecard yet

## Wiring notes

- **LLM:** an `AsyncOpenAI` client with the shared `base_url` / `api_key`, wrapped
  in `OpenAIChatCompletionsModel`. The SDK is OpenAI-first but does not insist on
  `api.openai.com`.
- **Tracing must be disabled.** By default the SDK uploads traces to OpenAI. That
  would fail against the mock server and leak prompts against a third-party
  gateway, so the adapter calls `set_tracing_disabled(True)`. This is the single
  most important line in the file.
- **Tools:** `@function_tool` around the shared implementations, registered only
  for the tools the arena declares.
- **Metrics:** `result.context_wrapper.usage`; tool calls from `ToolCallItem`s in
  `result.new_items`.

## Approval interruptions: the native pause

Of the four mechanisms measured so far this is the most complete. A tool declared
`needs_approval=True` stops the run instead of executing:

```python
@function_tool(needs_approval=True)
def request_approval(summary: str) -> str:
    """Ask a human to approve a consequential action before taking it."""
    return f"Approved: {summary}"
```

The run comes back with `final_output is None` and a `ToolApprovalItem` in
`result.to_state().get_interruptions()`. Resuming is explicit:

```python
restored = await RunState.from_json(agent, blob)  # note: async
for item in restored.get_interruptions():
    restored.approve(item)  # or .reject(item)
Runner.run_sync(agent, restored)
```

`RunState.to_json()` returns a plain dict and serialises the **whole run**, not
just the message list, which is why the same code path also satisfies
`durable_state` — the harness discards the runner there and only JSON survives.
That puts it alongside LangGraph's checkpointer rather than in the
"replay the transcript" category.

## Gotchas

- **`usage` and `new_items` come back cumulative on a resumed run.** Leg two holds
  leg one's numbers too. The harness sums across legs, so the adapter subtracts a
  recorded baseline; without it every paused item reports roughly double its real
  cost *and still passes*. Verified against the other three adapters: 4 and 5 LLM
  calls on the two pause arenas, matching exactly.
- `RunState.from_json` is a coroutine — it needs an event loop even though the
  rest of the sync path does not.
- Loses one `resilience` item (`res-02`): it raises `ModelBehaviorError` when the
  model names a tool that does not exist, where the stdlib baseline recovers.
- The interrupt tool must not be logged as a tool call; asking for permission is
  the pause, not an action taken.

## Results

Mock mode only. Pass rates in mock mode are ~100% by construction and are **not**
a quality signal. The comparable columns are marked.

| Arena | Mode | Pass rate | Note |
|---|---|--:|---|
| `tool_use` | mock | 15/15 | 787 prompt tok/item, 1.04× baseline — heaviest of the five *(comparable)* |
| `structured_output` | mock | 15/15 | |
| `rag` | mock | 15/15 | |
| `multi_agent` | mock | 10/10 | single-agent role-play entry |
| `resilience` | mock | **7/8** | *(comparable)* — fails `res-02`, unknown tool name |
| `human_in_the_loop` | mock | 12/12 | native `needs_approval` |
| `durable_state` | mock | 8/8 | `RunState` serialised across the rebuild |
