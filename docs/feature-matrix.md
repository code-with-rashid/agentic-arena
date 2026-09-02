# Feature matrix

Things that don't reduce to a scorecard number. Fill a cell only from first-hand
experience writing the adapter — link to the adapter code or an upstream doc.

Legend: ✅ built-in · 🟡 possible with work · ❌ not really · ❓ not yet assessed

| Capability | vanilla | LangGraph | CrewAI | OpenAI Agents SDK | Claude Agent SDK | Pydantic AI | MS Agent Framework |
|---|---|---|---|---|---|---|---|
| Language | Python | Python | Python | Python | Python | Python | Python / .NET |
| OpenAI-compatible base_url | ✅ | ✅ | ✅ (LiteLLM) | ✅ | ❓ | ✅ | ✅ (Chat Completions client) |
| Streaming tokens | ❌ | ✅ | 🟡 | ❓ | ❓ | ❓ | ❓ |
| Recovers from malformed tool args | ✅ | ❌ | ✅ | ✅ | ❓ | ✅ | ✅ |
| Recovers from an unknown tool name | ✅ | ✅ | ✅ | ❌ (raises) | ❓ | ✅ | ✅ |
| Native OpenAI tool calling | ✅ | ✅ | ❌ (text ReAct loop) | ✅ | ❓ | ✅ | ✅ |
| Tool-call history exposed | ✅ | ✅ | 🟡 (via wrapper) | ✅ (`new_items`) | ❓ | ✅ (`all_messages()`) | ✅ (`messages` contents) |
| Token usage exposed | ✅ | ✅ (`usage_metadata`) | ✅ (`usage_metrics`) | ✅ (`context_wrapper.usage`) | ❓ | ✅ (`result.usage`) | ✅ (`usage_details`) |
| Built-in multi-agent | ❌ | ✅ (graph) | ✅ (crew) | 🟡 (handoffs) | 🟡 (subagents) | 🟡 | ✅ |
| Human-in-the-loop / interrupts | 🟡 (emulated, measured) | ✅ (`interrupt`) | ❓ | ❓ | ❓ | 🟡 (deferred tools) | 🟡 (tool-approval middleware) |
| Durable state / checkpointing | 🟡 (stateless resume, measured) | ✅ (`SqliteSaver`, measured) | ❓ | ❓ | ❓ | ❓ | ❓ |
| Typed / schema-validated output | 🟡 | 🟡 | 🟡 | 🟡 (`output_type`) | ❓ | ✅ | 🟡 |
| Async API | ❌ | ✅ | 🟡 | ✅ (`run_sync` wraps it) | ❓ | ✅ | ✅ (async-only) |
| Observability hooks / tracing | ❌ | ✅ (LangSmith) | ✅ (events) | ✅ (built-in; disabled for the arena) | ❓ | 🟡 (Logfire) | ✅ (OpenTelemetry) |
| Licence | — | MIT | MIT | MIT | ❓ | MIT | MIT |

The two `Recovers from ...` rows are measured, not judged — see the `resilience`
arena and the comparison CI prints on every run.

The `Built-in multi-agent` row is still judged, not measured: the `multi_agent`
arena runs today with single-agent role-play entries only. It starts measuring
this row once `<fw>-multi` entries land that use each framework's real
graph/crew/handoff mechanism, compared on token and LLM-call cost.

The `Human-in-the-loop / interrupts` row is now **measured for two adapters**.
`human_in_the_loop` observes the pause in the harness rather than trusting the
agent's prose:

| adapter | result | mechanism |
|---|---|---|
| `langgraph` | 12/12 | native — `interrupt()` + `MemorySaver`, resumed with `Command(resume=...)` |
| `vanilla` | 12/12 | emulated — transcript carried back in, no checkpoint (hence 🟡, not ✅) |

Both produce an identical trace to the scorer: one pause per item, `book_room`
never called before it, and called on exactly the six approved items.

`Durable state / checkpointing` is measured by `durable_state`, which discards the
runner at the pause and rebuilds it, so only a real checkpoint or a serialised
transcript can get across:

| adapter | result | mechanism |
|---|---|---|
| `langgraph` | 8/8 | `SqliteSaver` writing to the harness-owned checkpoint dir; a fresh runner reopens the same thread |
| `vanilla` | 8/8 | stateless resume — the whole transcript is serialised into `resume_state`. Durable, but it is not a checkpointer, hence 🟡 |

An adapter patched to restart from scratch instead of resuming drops to **0/8**:
it reaches the right answer by redoing both lookups, and the `call_counts` check
catches the duplicated work.

`crewai`, `openai_agents`, `pydantic_ai` and `microsoft_af` have no `resume`
method yet and report *unsupported* on both arenas. Read their cells as unmeasured
claims from upstream docs, not as results — Agent Framework in particular ships
tool-approval middleware that nobody has wired up here.

> The ❓ cells are the backlog. Each one gets resolved when its adapter is written
> or when an arena exercises that capability directly.
