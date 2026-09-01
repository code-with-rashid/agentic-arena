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
| Human-in-the-loop / interrupts | ❌ | ✅ (`interrupt`) | ❓ | ❓ | ❓ | 🟡 (deferred tools) | 🟡 (tool-approval middleware) |
| Durable state / checkpointing | ❌ | ✅ (checkpointer) | ❓ | ❓ | ❓ | ❓ | ❓ |
| Typed / schema-validated output | 🟡 | 🟡 | 🟡 | 🟡 (`output_type`) | ❓ | ✅ | 🟡 |
| Async API | ❌ | ✅ | 🟡 | ✅ (`run_sync` wraps it) | ❓ | ✅ | ✅ (async-only) |
| Observability hooks / tracing | ❌ | ✅ (LangSmith) | ✅ (events) | ✅ (built-in; disabled for the arena) | ❓ | 🟡 (Logfire) | ✅ (OpenTelemetry) |
| Licence | — | MIT | MIT | MIT | ❓ | MIT | MIT |

The two `Recovers from ...` rows are measured, not judged — see the `resilience`
arena and the comparison CI prints on every run.

> The ❓ cells are the backlog. Each one gets resolved when its adapter is written
> or when an arena exercises that capability directly.
