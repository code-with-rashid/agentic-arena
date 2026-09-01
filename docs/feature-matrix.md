# Feature matrix

Things that don't reduce to a scorecard number. Fill a cell only from first-hand
experience writing the adapter — link to the adapter code or an upstream doc.

Legend: ✅ built-in · 🟡 possible with work · ❌ not really · ❓ not yet assessed

| Capability | vanilla | LangGraph | CrewAI | OpenAI Agents SDK | Claude Agent SDK | Pydantic AI | MS Agent Framework |
|---|---|---|---|---|---|---|---|
| Language | Python | Python | Python | Python | Python | Python | Python / .NET |
| OpenAI-compatible base_url | ✅ | ✅ | ✅ (LiteLLM) | ❓ | ❓ | ❓ | ❓ |
| Streaming tokens | ❌ | ✅ | 🟡 | ❓ | ❓ | ❓ | ❓ |
| Tool-call history exposed | ✅ | ✅ | 🟡 (via wrapper) | ❓ | ❓ | ❓ | ❓ |
| Token usage exposed | ✅ | ✅ (`usage_metadata`) | ✅ (`usage_metrics`) | ❓ | ❓ | ❓ | ❓ |
| Built-in multi-agent | ❌ | ✅ (graph) | ✅ (crew) | 🟡 (handoffs) | 🟡 (subagents) | 🟡 | ✅ |
| Human-in-the-loop / interrupts | ❌ | ✅ (`interrupt`) | ❓ | ❓ | ❓ | ❓ | ❓ |
| Durable state / checkpointing | ❌ | ✅ (checkpointer) | ❓ | ❓ | ❓ | ❓ | ❓ |
| Typed / schema-validated output | 🟡 | 🟡 | 🟡 | ❓ | ❓ | ✅ | ❓ |
| Async API | ❌ | ✅ | 🟡 | ❓ | ❓ | ✅ | ✅ |
| Observability hooks / tracing | ❌ | ✅ (LangSmith) | ✅ (events) | ❓ | ❓ | 🟡 (Logfire) | ✅ |
| Licence | — | MIT | MIT | ❓ | ❓ | MIT | MIT |

> The ❓ cells are the backlog. Each one gets resolved when its adapter is written.
