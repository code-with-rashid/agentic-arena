# Arena designs

One markdown design per planned arena. When an arena is implemented it moves from
"design" here to a runnable `arenas/<id>/` directory (spec + dataset + mock script)
and this file becomes its reference notes.

| Arena | Design | Implemented |
|---|---|---|
| `tool_use` | (shipped) | ✅ `arenas/tool_use/` |
| `structured_output` | [structured_output.md](structured_output.md) | ✅ `arenas/structured_output/` |
| `resilience` | (built directly; see the arena.toml) | ✅ `arenas/resilience/` |
| `multi_agent` | [multi_agent.md](multi_agent.md) | ✅ `arenas/multi_agent/` — single-agent entries **and** five `*_multi` pipelines (structural, handoff, sub-agent-as-tool) |
| `rag` | [rag.md](rag.md) | ✅ `arenas/rag/` |
| `human_in_the_loop` | [human_in_the_loop.md](human_in_the_loop.md) | ✅ `arenas/human_in_the_loop/` — six adapters pause, six distinct mechanisms |
| `durable_state` | [durable_state.md](durable_state.md) | ✅ `arenas/durable_state/` — five adapters 8/8 across a real process restart |

See [../../CONTRIBUTING.md](../../CONTRIBUTING.md) → "Adding an arena".
