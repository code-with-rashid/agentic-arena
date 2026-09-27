# Choose a framework or SDK

A framework supplies building blocks inside an application you design. Use this
route when you are choosing orchestration, tool, state, approval, or delegation
primitives. If you want a complete environment that already owns prompts,
execution, permissions, persistence, and interaction, use the
[coding-harness route](../harnesses/README.md).

Coverage counts below refer to the original seven arenas. The eighth,
[boundary response](../arenas/boundary_response.md), currently covers only
vanilla, LangGraph and OpenAI Agents SDK.

One page per adapter — wiring notes, the gotchas that cost real debugging time,
and results. Written and maintained by whoever owns the adapter.

| Framework | Status | The thing worth knowing |
|---|---|---|
| [LangGraph](langgraph.md) | runs all 7 arenas | Ties the hand-rolled baseline on the wire, byte for byte; native `interrupt()` + on-disk checkpointer; loses `res-01` on malformed tool args |
| [OpenAI Agents SDK](openai-agents-sdk.md) | runs all 7 arenas | Heaviest of the in-band six on the wire (1.14×); `needs_approval` + a fully serialisable `RunState`; **tracing uploads to OpenAI unless disabled** |
| [Pydantic AI](pydantic-ai.md) | runs all 7, green on all 7 | `Agent(retries=...)` is **not** a loop cap — it ran 50 LLM calls on a budget of 6; deferred tools for the pause; its hand-built delegation chain costs 2N without the library having a delegation feature |
| [Microsoft Agent Framework](microsoft-agent-framework.md) | runs 6 of 7 | Tool loop **uncapped** by default (41 calls on a budget of 6); pauses natively via `approval_mode`, but the pause dies with the process |
| [Google ADK](google-adk.md) | runs all 7 | The only **real** loop cap out of the box (N means N); needs `litellm` to leave Google, the heaviest dep tree here; loses both `res-01` and `res-02` to uncaught exceptions |
| [smolagents](smolagents.md) | runs 5 of 7 | **3.90× baseline on the wire** — a 4.2 KB templated system prompt resent every request; recovers 8/8 scripted faults, with 3× cost on four validation failures |
| [CrewAI](crewai.md) | not in CI | Drives a **text ReAct loop**, not native tool calling — answers correctly, records no tool calls |
| [Claude Agent SDK](claude-agent-sdk.md) | stub, on purpose | Spawns the `claude` CLI over the Anthropic Messages API; cannot sit behind the shared OpenAI-compatible gateway |

The dependency-free [`vanilla`](../../frameworks/vanilla/README.md) baseline is
documented next to its code. It is the control in the experiment, and it is
**not** the cheapest on the wire — see [overhead.md](../overhead.md).

`vanilla`, `pydantic_ai`, and `smolagents` are green on every arena they run.
`langgraph` and `openai_agents` each lose one `resilience` item, while
`google_adk` loses two. Those are measured findings, not broken adapters.
`microsoft_af` pauses 12/12 but is *unsupported* on `durable_state`; `smolagents`
is *unsupported* on both. Reported as unsupported rather than failed.

## Reading these pages

Every profile starts with the same decision and evidence summary: best fit,
owned responsibilities, important limitation, evidence status, pinned version,
and review deadline. Read the [profile evidence guide](../reference/profile-evidence.md)
before treating a source review or mock result as a product ranking.

Pass rates in mock mode are ~100% by construction and prove only that an adapter
is wired correctly. The columns that compare frameworks honestly are marked
*(comparable)* on each page, and collected by `python -m arena summary`.
