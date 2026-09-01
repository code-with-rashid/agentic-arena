# Choosing a framework

> This guide is a **skeleton**. It gets filled in with evidence as arenas and live
> scorecards land — every claim here should eventually point at a `results/` number
> or a documented feature-matrix cell. Until then, treat it as hypotheses.

## Start here

1. **Do you actually need a framework?** Run the `vanilla` baseline numbers next to
   your candidate. If the task is a single agent with a handful of tools, the
   hand-rolled loop is ~90 lines and has the lowest token and latency overhead. A
   framework earns its keep when you need orchestration, durability, HITL, or a
   large tool surface you don't want to hand-manage.

2. **What is the shape of the work?**

   | If the core need is... | Look first at... | Arena that tests it |
   |---|---|---|
   | Deterministic, auditable, resumable workflows | LangGraph | `durable_state`, `human_in_the_loop` |
   | Fastest path to a multi-agent prototype | CrewAI | `multi_agent` |
   | Conversational multi-agent / event-driven | Microsoft Agent Framework | `multi_agent` |
   | Minimal wrapper around one provider's models | OpenAI Agents SDK / Claude Agent SDK | `tool_use` |
   | Type-safe outputs, model-agnostic | Pydantic AI | `structured_output` |

3. **Constraints that override the above:** language (Python vs TS), self-host vs
   SaaS, licence, provider lock-in, existing infra (e.g. already on Semantic Kernel).

## How to read the scorecards

- **Pass rate** first — can the framework reliably complete the task at all.
- **Mean LLM calls** and **mean tokens** — orchestration overhead; multiply by your
  traffic and price.
- **Mean latency** — framework overhead on top of model time; compare to `vanilla`.
- **Errors** — robustness of the framework's own loop (recursion limits, tool-call
  parsing, retries).
- Always check **`--repeat`**: a 100% at repeat 1 is not the same as 100% at repeat 10.

## Flowchart

_TODO: add a Mermaid decision flowchart once `multi_agent` and `rag` have live
numbers for at least four adapters._
