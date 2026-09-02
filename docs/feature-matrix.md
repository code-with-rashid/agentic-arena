# Feature matrix

Things that don't reduce to a scorecard number. Fill a cell only from first-hand
experience writing the adapter — link to the adapter code or an upstream doc.

Legend: ✅ built-in · 🟡 possible with work · ❌ not really · ❓ not yet assessed

| Capability | vanilla | LangGraph | CrewAI | OpenAI Agents SDK | Claude Agent SDK | Pydantic AI | MS Agent Framework | smolagents |
|---|---|---|---|---|---|---|---|---|
| Language | Python | Python | Python | Python | Python | Python | Python / .NET | Python |
| OpenAI-compatible base_url | ✅ | ✅ | ✅ (LiteLLM) | ✅ | ❓ | ✅ | ✅ (Chat Completions client) | ✅ (`OpenAIServerModel`, needs the `[openai]` extra) |
| Streaming tokens | ❌ | ✅ | 🟡 | ❓ | ❓ | ❓ | ❓ | ❓ |
| Recovers from malformed tool args | ✅ | ❌ | ✅ | ✅ | ❓ | ✅ | ✅ | ✅ |
| Recovers from an unknown tool name | ✅ | ✅ | ✅ | ❌ (raises) | ❓ | ✅ | ✅ | ❌ (not written back) |
| Native OpenAI tool calling | ✅ | ✅ | ❌ (text ReAct loop) | ✅ | ❓ | ✅ | ✅ | ✅ (plus a `final_answer` control tool) |
| Tool-call history exposed | ✅ | ✅ | 🟡 (via wrapper) | ✅ (`new_items`) | ❓ | ✅ (`all_messages()`) | ✅ (`messages` contents) | ✅ (`memory.steps`) |
| Token usage exposed | ✅ | ✅ (`usage_metadata`) | ✅ (`usage_metrics`) | ✅ (`context_wrapper.usage`) | ❓ | ✅ (`result.usage`) | ✅ (`usage_details`) | ✅ (per-step `token_usage`) |
| Built-in multi-agent | ❌ | ✅ (graph, measured) | ✅ (crew) | ✅ (`handoffs`, measured) | 🟡 (subagents) | 🟡 | ✅ | 🟡 (managed agents) |
| Human-in-the-loop / interrupts | 🟡 (emulated, measured) | ✅ (`interrupt`, measured) | ❓ | ✅ (`needs_approval`, measured) | ❓ | ✅ (deferred tools, measured) | 🟡 (tool-approval middleware) | ❌ (no interrupt primitive) |
| Durable state / checkpointing | 🟡 (stateless resume, measured) | ✅ (`SqliteSaver`, measured) | ❓ | ✅ (`RunState.to_json`, measured) | ❓ | 🟡 (stateless resume, measured) | ❓ | ❌ |
| Typed / schema-validated output | 🟡 | 🟡 | 🟡 | 🟡 (`output_type`) | ❓ | ✅ | 🟡 | 🟡 |
| Async API | ❌ | ✅ | 🟡 | ✅ (`run_sync` wraps it) | ❓ | ✅ | ✅ (async-only) | 🟡 (`arun`) |
| Observability hooks / tracing | ❌ | ✅ (LangSmith) | ✅ (events) | ✅ (built-in; disabled for the arena) | ❓ | 🟡 (Logfire) | ✅ (OpenTelemetry) | ✅ (OpenTelemetry) |
| Licence | — | MIT | MIT | MIT | ❓ | MIT | MIT | Apache-2.0 |

The two `Recovers from ...` rows are measured, not judged — see the `resilience`
arena and the comparison CI prints on every run.

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

The `Human-in-the-loop / interrupts` row is now **measured for four adapters**.
`human_in_the_loop` observes the pause in the harness rather than trusting the
agent's prose:

| adapter | result | mechanism |
|---|---|---|
| `langgraph` | 12/12 | native — `interrupt()` + `MemorySaver`, resumed with `Command(resume=...)` |
| `openai_agents` | 12/12 | native — the tool is `needs_approval=True`, the run stops with a `ToolApprovalItem`, `resume` calls `approve`/`reject` |
| `pydantic_ai` | 12/12 | native — the tool raises `CallDeferred`, the run returns `DeferredToolRequests`, `resume` passes `deferred_tool_results` |
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
| `vanilla` | 8/8 | stateless resume — the whole transcript is serialised into `resume_state`. Durable, but it is not a checkpointer, hence 🟡 |

An adapter patched to restart from scratch instead of resuming drops to **0/8**:
it reaches the right answer by redoing both lookups, and the `call_counts` check
catches the duplicated work.

`crewai`, `microsoft_af` and `smolagents` have no `resume` method and report
*unsupported* on both arenas. Read the first two cells as unmeasured claims from
upstream docs, not as results — Agent Framework ships `ToolApprovalMiddleware`,
but it requires an `AgentSession` and session state, a different shape again from
the four mechanisms wired up so far. `smolagents` is marked ❌ rather than ❓
because it ships no interrupt or approval primitive to adapt: emulating one by
hand, as `vanilla` does, would measure the adapter instead of the framework.

> The ❓ cells are the backlog. Each one gets resolved when its adapter is written
> or when an arena exercises that capability directly.
