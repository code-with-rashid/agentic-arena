# LangGraph — deep dive

## At a glance

- Package / repo: [`langgraph`](https://github.com/langchain-ai/langgraph) —
  pinned `langgraph==1.2.11`, `langchain-core==1.6.1`, `langchain-openai==1.6.0`
- Licence: MIT
- Adapter: [`frameworks/langgraph/adapter.py`](../../frameworks/langgraph/adapter.py)
- Status: mock-green on all six arenas; no live scorecard yet (no API key wired in)

## Wiring notes

- **LLM:** `ChatOpenAI(model=..., base_url=config.base_url, api_key=config.api_key,
  temperature=0.0)`. Points cleanly at the shared gateway — no special handling
  needed for mock vs live.
- **Tools:** the shared implementations wrapped with `@tool` from
  `langchain_core.tools`. The wrapper only forwards; it never changes what a tool
  computes. Only the tools the arena declares are registered
  (`arena.tools.names_for`).
- **Iteration budget:** `config={"recursion_limit": 2 * max_tool_iterations}`.
  One tool round is *two* graph steps (model node + tool node), so the limit has
  to be doubled to line up with the other adapters' LLM-call budgets. It was
  briefly `2N + 2`, which quietly bought LangGraph one extra model call.
- **Metrics:** summed from `msg.usage_metadata` across the returned messages;
  tool calls read from `msg.tool_calls`.
- **Human-in-the-loop:** implemented **natively** — see below.

## Native interrupts

The `request_approval` tool calls `langgraph.types.interrupt(...)`. LangGraph
checkpoints the graph at that point and `invoke` returns with `__interrupt__`
set; `resume` continues the same thread with `Command(resume=decision)`, and the
`interrupt(...)` call inside the tool returns that decision so the graph carries
on from exactly where it stopped.

Nothing about the transcript is reconstructed by hand. That is the real
distinction from the `vanilla` baseline, which emulates the pause by carrying the
message list back in — an emulation that would not survive a process restart.

Two details the adapter has to get right, both of which are asserted in
`tests/test_suspend_resume.py`:

- **A resumed `invoke` returns the whole thread.** The harness sums cost across
  legs, so the second leg must report only the messages added since the pause
  (`seen` slicing) or every token on a paused item is counted twice.
- **`request_approval` is not logged as a tool call.** Asking permission is the
  pause, not an action taken. The baseline does not log it either, and the
  arena's `no_tool_before_suspend` check compares the two adapters directly.

## Gotchas

- `create_react_agent` is deprecated in LangGraph 1.0 (moves to
  `langchain.agents.create_agent` in 2.0). Deliberately not migrated yet — the
  replacement lives in the `langchain` package, which this adapter does not
  install, on a different version track from the pinned `langchain-core`. See the
  deprecation register in [../dependencies.md](../dependencies.md).
- `interrupt` needs a checkpointer *and* a `thread_id`, so the adapter only
  attaches `MemorySaver` for arenas that declare `request_approval`. Attaching it
  everywhere would change behaviour on arenas that never pause.
- Loses one `resilience` item (`res-01`): it gives up on malformed tool arguments
  where the stdlib baseline recovers. See the `comparison` CI job.

## Results

Mock mode only so far. Pass rates in mock mode are ~100% by construction and are
**not** a quality signal — they prove the adapter is wired correctly. The two
columns that do compare honestly are marked.

| Arena | Mode | Pass rate | Note |
|---|---|--:|---|
| `tool_use` | mock | 15/15 | 683 prompt tok/item — leanest of the five, see [overhead.md](../overhead.md) *(comparable)* |
| `structured_output` | mock | 15/15 | |
| `rag` | mock | 15/15 | |
| `multi_agent` | mock | 10/10 | single-agent role-play entry |
| `resilience` | mock | **7/8** | *(comparable)* — fails `res-01`, malformed tool args |
| `human_in_the_loop` | mock | 12/12 | native `interrupt` + checkpointer |
