# Feature matrix

Things that don't reduce to a scorecard number. Fill a cell only from first-hand
experience writing the adapter — link to the adapter code or an upstream doc.

Legend: ✅ built-in · 🟡 possible with work · ❌ not really · ❓ not yet assessed

| Capability | vanilla | LangGraph | CrewAI | OpenAI Agents SDK | Claude Agent SDK | Pydantic AI | MS Agent Framework | smolagents | Google ADK |
|---|---|---|---|---|---|---|---|---|---|
| Language | Python | Python | Python | Python | Python | Python | Python / .NET | Python | Python |
| OpenAI-compatible base_url | ✅ | ✅ | ✅ (LiteLLM) | ✅ | ❓ | ✅ | ✅ (Chat Completions client) | ✅ (`OpenAIServerModel`, needs the `[openai]` extra) | ✅ (via LiteLLM only) |
| Streaming tokens | ❌ | ✅ | 🟡 | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ |
| Recovers from malformed tool args | ✅ | ❌ | ✅ | ✅ | ❓ | ✅ | ✅ | ✅ | ❌ (raises) |
| Runs every tool call in a batched turn | ✅ | 🟡 (drops a malformed sibling) | ❓ | ✅ | ❓ | ✅ | ✅ | 🟡 (drops the whole batch) | ✅ |
| Recovers from an unknown tool name | ✅ | ✅ | ✅ | ❌ (raises) | ❓ | ✅ | ✅ | ❌ (not written back) | ❌ (raises) |
| Native OpenAI tool calling | ✅ | ✅ | ❌ (text ReAct loop) | ✅ | ❓ | ✅ | ✅ | ✅ (plus a `final_answer` control tool) | ✅ (through LiteLLM) |
| Tool-call history exposed | ✅ | ✅ | 🟡 (via wrapper) | ✅ (`new_items`) | ❓ | ✅ (`all_messages()`) | ✅ (`messages` contents) | ✅ (`memory.steps`) | ✅ (event stream) |
| Token usage exposed | ✅ | ✅ (`usage_metadata`) | ✅ (`usage_metrics`) | ✅ (`context_wrapper.usage`) | ❓ | ✅ (`result.usage`) | ✅ (`usage_details`) | ✅ (per-step `token_usage`) | ✅ (per-event `usage_metadata`) |
| Built-in multi-agent | ❌ | ✅ (graph, measured) | ✅ (crew) | ✅ (`handoffs`, measured) | 🟡 (subagents) | 🟡 | ✅ | 🟡 (managed agents) | ✅ (sub-agents) |
| Human-in-the-loop / interrupts | 🟡 (emulated, measured) | ✅ (`interrupt`, measured) | ❓ | ✅ (`needs_approval`, measured) | ❓ | ✅ (deferred tools, measured) | ✅ (`approval_mode`, measured) | ❌ (no interrupt primitive) | 🟡 (reported, not enforced, measured) |
| Durable state / checkpointing | 🟡 (stateless resume, measured) | ✅ (`SqliteSaver`, measured) | ❓ | ✅ (`RunState.to_json`, measured) | ❓ | 🟡 (stateless resume, measured) | ❌ (session store does not round-trip, measured) | ❌ | ✅ (`DatabaseSessionService`, measured) |
| Typed / schema-validated output | 🟡 | 🟡 | 🟡 | 🟡 (`output_type`) | ❓ | ✅ | 🟡 | 🟡 | 🟡 (`output_schema`) |
| Async API | ❌ | ✅ | 🟡 | ✅ (`run_sync` wraps it) | ❓ | ✅ | ✅ (async-only) | 🟡 (`arun`) | ✅ (async-first) |
| Observability hooks / tracing | ❌ | ✅ (LangSmith) | ✅ (events) | ✅ (built-in; disabled for the arena) | ❓ | 🟡 (Logfire) | ✅ (OpenTelemetry) | ✅ (OpenTelemetry) | ✅ (OpenTelemetry) |
| Licence | — | MIT | MIT | MIT | ❓ | MIT | MIT | Apache-2.0 | Apache-2.0 |

The two `Recovers from ...` rows are measured, not judged — see the `resilience`
arena and the comparison CI prints on every run.

### Batched tool calls, and a quieter failure mode

A model may return several tool calls in one turn. With two *valid* calls all
seven adapters do the right thing — both run, both results reach the model. The
interesting case is when one call in the batch is broken. For each fault, batched
with one good call, two questions of the next request: did the **successful**
call's result reach the model, and was the broken call **reported** at all?

| | unknown tool | malformed args | missing required arg |
|---|---|---|---|
| `vanilla` | both | both | both |
| `pydantic_ai` | both | both | both |
| `microsoft_af` | both | both | both |
| `langgraph` | both | **good only** | both |
| `smolagents` | **error only** | **good only** | **error only** |
| `openai_agents` | **raises** | both | both |
| `google_adk` | **raises** | **raises** | both |

Three distinct ways to mishandle a batch, and they are not equally bad:

- **Silent partial** (`langgraph`, and `smolagents` on malformed args). The
  broken call vanishes with no message of any kind. The run continues, answers
  from partial evidence, and the model is never told a call went missing. This is
  the quietest failure here and the one worth watching for.
- **The successful sibling is discarded** (`smolagents`, two faults). The error
  *is* surfaced — but as a rewritten task (`New task: … Error: … Now let's
  retry`) rather than as a turn in the transcript, and the good call's
  observation is dropped along with the history. The model then re-emits the
  identical batch, because from its point of view it never ran anything. This is
  the same mechanism as its `resilience` losses, seen from a different angle.
- **Raises** (`openai_agents`, `google_adk`). Loud, and the same root cause as
  those frameworks' `resilience` losses. Nothing is silently wrong, which makes
  it the best of the three.

That is a different question from the one `resilience` asks: not "does it
recover?" but "does it tell the truth about what happened on the way?" A
framework that drops a lookup without saying so produces a confident answer built
on half the evidence.

It also refines the `res-01` row. `langgraph` losing malformed tool arguments is
**conditional**: alone, the malformed call produces no tool message and the graph
halts (so the item fails, visibly); batched with a call that succeeds, the graph
carries on and the drop becomes invisible. The visible failure is the better of
the two outcomes.

Measured in `tests/test_parallel_tool_calls.py`, which gates the invariants
(valid batches work, the baseline surfaces every result, batching never makes a
framework worse than it is serially) and leaves the per-framework differences as
findings, the same way `resilience` does.

> An earlier version of this table read *"missing required arg — smolagents 0 of
> 2, the whole batch is dropped"*. That was measured with a helper that counted
> the word "observation" in the returned messages — and a corpus entry describes
> Tokyo Tower as a "communications and observation tower", so it read 3 for a
> batch of 2. The direction was right and the zero was real, but "the model is
> never told" was wrong for `smolagents`: it *is* told, in a rewritten task, and
> what it loses is the successful sibling. The probe now matches each outcome's
> own text, and a test pins that none of those markers appear in the corpus.

Those two rows do not fully capture `smolagents`, which loses **four** of the
eight faults. The unknown-tool-name row is the visible one, but the real boundary
is its tool-validation layer: any failure raised *before* the tool body runs
(unknown name, missing argument, unexpected argument, `null` arguments) is never
written back into the conversation, so the model cannot see it and repeats the
identical call until the step budget is gone. Faults that get as far as running
the tool come back as observations and it recovers from all of them. See
[smolagents.md](frameworks/smolagents.md#resilience-48-split-exactly-along-one-line).

The `Built-in multi-agent` row is now **partly measured**. `multi_agent` carries
two real three-role pipelines alongside the single-agent entries:

| comparison | prompt | LLM calls |
|---|--:|--:|
| `vanilla` -> `vanilla_multi` (hand-rolled pipeline) | 2.50x | 2.00x |
| `langgraph` -> `langgraph_multi` (`StateGraph`) | 2.62x | 2.00x |
| `vanilla_multi` -> `langgraph_multi` (graph machinery alone) | **0.97x** | **1.00x** |
| `openai_agents` -> `openai_agents_multi` (native `handoffs`) | 2.76x | 2.00x |

The cost of multi-agent is the structure, not the framework: three roles double
the LLM calls and ~2.5x the prompt tokens whether you build them with a graph
library or a `for` loop, and LangGraph's orchestration adds nothing on top (the
0.97x is the tool-schema difference from [overhead.md](overhead.md), unchanged).

This measures cost with benefit held at zero — the mock scripts identical turns,
so all four entries return the same brief. Whether delegation improves the answer
needs a live run. See [multi-agent.md](multi-agent.md).

Model-decided delegation (a native `handoffs` chain) costs ~10% more prompt than
the structural pipelines at the same call count, and **94% of that difference is
the `transfer_to_*` schemas riding on every request** rather than the transfers
themselves — you pay for a handoff by advertising it, not by taking it. A
supervisor offering N handoffs pays for N schemas on every request in the run.

Still judged for the rest: smolagents `managed_agents` and CrewAI crews are also
model-decided but express delegation as a sub-agent invoked like a tool rather
than a transfer that swaps the speaker, which the current mock accommodation does
not pick up.

The `Human-in-the-loop / interrupts` row is now **measured for six adapters**.
`human_in_the_loop` observes the pause in the harness rather than trusting the
agent's prose:

| adapter | result | mechanism |
|---|---|---|
| `langgraph` | 12/12 | native — `interrupt()` + `MemorySaver`, resumed with `Command(resume=...)` |
| `openai_agents` | 12/12 | native — the tool is `needs_approval=True`, the run stops with a `ToolApprovalItem`, `resume` calls `approve`/`reject` |
| `pydantic_ai` | 12/12 | native — the tool raises `CallDeferred`, the run returns `DeferredToolRequests`, `resume` passes `deferred_tool_results` |
| `microsoft_af` | 12/12 | native — `@tool(approval_mode="always_require")` + `ToolApprovalMiddleware`; `resume` answers with `to_function_approval_response` |
| `google_adk` | 12/12 | `LongRunningFunctionTool` — the call is *reported* in `long_running_tool_ids`, but the run does not stop on its own (hence 🟡); resumed with a `FunctionResponse` against the same call id |
| `vanilla` | 12/12 | emulated — transcript carried back in, no checkpoint (hence 🟡, not ✅) |

Both produce an identical trace to the scorer: one pause per item, `book_room`
never called before it, and called on exactly the six approved items.

`Durable state / checkpointing` is measured by `durable_state`, which discards the
runner at the pause and rebuilds it, so only a real checkpoint or a serialised
transcript can get across:

| adapter | result | mechanism |
|---|---|---|
| `langgraph` | 8/8 | `SqliteSaver` writing to the harness-owned checkpoint dir; a fresh runner reopens the same thread |
| `openai_agents` | 8/8 | `RunState.to_json()` / `from_json()` — the SDK serialises the whole run, not just the messages |
| `pydantic_ai` | 8/8 | stateless resume — the conversation is serialised with `ModelMessagesTypeAdapter` and replayed as `message_history` |
| `google_adk` | 8/8 | `DatabaseSessionService` on `sqlite+aiosqlite`, writing to the harness-owned checkpoint dir; needs `sqlalchemy` on top of an already heavy tree |
| `vanilla` | 8/8 | stateless resume — the whole transcript is serialised into `resume_state`. Durable, but it is not a checkpointer, hence 🟡 |

An adapter patched to restart from scratch instead of resuming drops to **0/8**:
it reaches the right answer by redoing both lookups, and the `call_counts` check
catches the duplicated work.

`microsoft_af` pauses (12/12) but is **unsupported on `durable_state`**, and that
was measured rather than assumed: its approval state serialises cleanly, but the
conversation lives in the `AgentSession`'s in-memory store, which comes back from
a JSON round trip as raw strings — and restoring the approval state into a
rebuilt agent re-queues the request instead of consuming the answer. The adapter
therefore does not expose `resume` on a durable arena at all, because keeping one
it cannot honour would post 0/8 and read as a broken framework.

`crewai` and `smolagents` have no `resume` method and report *unsupported* on both
arenas. `smolagents` is marked ❌ rather than ❓ because it ships no interrupt or
approval primitive to adapt: emulating one by hand, as `vanilla` does, would
measure the adapter instead of the framework.

> The ❓ cells are the backlog. Each one gets resolved when its adapter is written
> or when an arena exercises that capability directly.
