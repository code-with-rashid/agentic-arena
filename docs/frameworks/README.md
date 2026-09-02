# Framework deep dives

One page per adapter — wiring notes, the gotchas that cost real debugging time,
and results. Written and maintained by whoever owns the adapter.

| Framework | Status | The thing worth knowing |
|---|---|---|
| [LangGraph](langgraph.md) | runs all 7 arenas | Leanest on the wire (0.90× baseline); native `interrupt()` + on-disk checkpointer; loses `res-01` on malformed tool args |
| [OpenAI Agents SDK](openai-agents-sdk.md) | runs all 7 arenas | Heaviest on the wire (1.04×); `needs_approval` + a fully serialisable `RunState`; **tracing uploads to OpenAI unless disabled** |
| [Pydantic AI](pydantic-ai.md) | runs all 7, green on all 7 | `Agent(retries=...)` is **not** a loop cap — it ran 50 LLM calls on a budget of 6; deferred tools for the pause |
| [Microsoft Agent Framework](microsoft-agent-framework.md) | runs 5 of 7 | Tool loop **uncapped** by default (41 calls on a budget of 6); approval story is session-store-shaped, not yet adapted |
| [CrewAI](crewai.md) | not in CI | Drives a **text ReAct loop**, not native tool calling — answers correctly, records no tool calls |
| [Claude Agent SDK](claude-agent-sdk.md) | stub, on purpose | Spawns the `claude` CLI over the Anthropic Messages API; cannot sit behind the shared OpenAI-compatible gateway |

The dependency-free [`vanilla`](../../frameworks/vanilla/README.md) baseline is
documented next to its code. It is the control in the experiment, and it is
**not** the cheapest on the wire — see [overhead.md](../overhead.md).

`vanilla` and `pydantic_ai` are green on every arena they run. `langgraph` and
`openai_agents` each lose one `resilience` item — that is a measured finding, not
a broken adapter. `microsoft_af` reports *unsupported* on the two pause arenas
rather than failing them.

## Reading these pages

Pass rates in mock mode are ~100% by construction and prove only that an adapter
is wired correctly. The columns that compare frameworks honestly are marked
*(comparable)* on each page, and collected by `python -m arena summary`.
