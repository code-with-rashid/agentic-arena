# What multi-agent costs

## The question

"Built-in multi-agent" sat in [feature-matrix.md](feature-matrix.md) as a judged
cell for a long time — ✅ or 🟡 read off upstream docs. Every framework has a
delegation mechanism and every framework's documentation says it is good. None of
that says what it *costs*.

The `multi_agent` arena asks 10 items that a three-role pipeline — researcher,
writer, editor — should be a natural fit for. Its adapters may express that
pipeline as a real multi-agent structure or as one agent role-playing all three,
and both are valid entries. That is what makes the comparison possible.

## The design

Four entries on the same 10 items, so three separate questions come apart:

| comparison | isolates |
|---|---|
| `vanilla` → `vanilla_multi` | what three stages cost, framework-free |
| `langgraph` → `langgraph_multi` | the same, inside a framework |
| `vanilla_multi` → `langgraph_multi` | what the graph machinery itself adds |

`vanilla_multi` is a hand-rolled pipeline in the standard library — a `while`
loop and some list appends. `langgraph_multi` is a real `StateGraph`:

```
START -> researcher <-> tools -> writer -> editor -> END
```

Both use the **same role wording** (checked in next to each adapter) over one
shared transcript, so the orchestration machinery is the only variable between
them. Only the researcher gets tools; giving the writer and editor tools would
make the pipeline three researchers.

## The numbers

Mean per item, mock mode, 10 items:

| entry | prompt tok | completion | LLM calls | tool calls | pass |
|---|--:|--:|--:|--:|--:|
| `vanilla` | 681.3 | 86.2 | 2.00 | 1.00 | 10/10 |
| `vanilla_multi` | 1705.3 | 198.0 | 4.00 | 1.00 | 10/10 |
| `langgraph` | 632.7 | 86.2 | 2.00 | 1.00 | 10/10 |
| `langgraph_multi` | 1656.7 | 198.0 | 4.00 | 1.00 | 10/10 |

| comparison | prompt | LLM calls |
|---|--:|--:|
| cost of 3 stages, framework-free | 2.50× | 2.00× |
| cost of 3 stages, inside a framework | 2.62× | 2.00× |
| **what the graph machinery itself adds** | **0.97×** | **1.00×** |

## What this says

**The cost of multi-agent is the structure, not the framework.** Splitting one
agent into three roles doubles the LLM calls and roughly 2.5×'s the prompt
tokens, and it costs that whether you build it with a graph library or with a
`for` loop. LangGraph's orchestration is, to the byte, free.

The 0.97× is worth being precise about, because "the framework is *cheaper*" would
be the wrong reading. The gap between `vanilla_multi` and `langgraph_multi` is
48.6 prompt tokens per item. The gap between `vanilla` and `langgraph` is also
**48.6**. It is the same tool-schema serialisation difference already reported in
[overhead.md](overhead.md) — LangGraph renders the `search` schema more compactly —
carried through unchanged. The graph adds nothing on top of it.

Why 2× the calls: one agent answers in 2 (search, then write). The pipeline
spends 4 — researcher searches, researcher reports, writer drafts, editor
finalises. Why 2.5× the prompt rather than 2×: each stage re-sends the
accumulated transcript *and* its own role instruction, so later stages carry more
context than earlier ones. That compounding is the real cost of delegation and it
gets worse with more roles, not better.

## What this does not say

**Nothing about whether the brief got better.** In mock mode the turns are
scripted and byte-identical for all four entries, so all four produce the *same
answer* — `test_pipeline_entry_is_really_three_roles_and_costs_more` asserts
exactly that. The pipeline cannot win on quality here, by construction.

So this is a cost measurement with the benefit held at zero. Read it as: *this is
the bill delegation puts on the table before it has done anything for you.*
Whether three roles produce a better brief than one needs a live run and a judge,
and is [not yet measured](methodology.md#5-what-mock-mode-does-and-does-not-tell-you).

That framing is the same discipline [overhead.md](overhead.md) uses, and it is
the reason these numbers are worth anything: everything that could vary is held
identical, so the one thing that differs is the thing being measured.

## Keeping the entries honest

A pipeline that silently collapsed into one agent called four times would still
post 10/10 and still look expensive — the scorecard cannot tell the difference.
So the structure is asserted directly in `tests/test_multi_agent_arena.py`:
three role prompts in order, only the researcher holding tools, the arena's task
prompt present at every stage, and the same output text as the single-agent entry
at twice the LLM calls. Degrading the writer and editor back into researchers
fails it with `['researcher', 'researcher', 'researcher', 'researcher']`.

`vanilla_multi` and `langgraph_multi` declare `arenas = ("multi_agent",)`, so
`--framework all` runs them only here. A pipeline sitting in the `tool_use`
overhead table at 2.5× would read as a framework being wasteful, when it is a
different structure being measured.

## Still open

- **Model-decided delegation.** These two pipelines are *structural* — the graph
  always visits all three roles. Handoff-style mechanisms (OpenAI Agents SDK
  `handoffs`, smolagents `managed_agents`, CrewAI crews) let the *model* choose to
  delegate, which a scripted mock will never spontaneously do. Measuring those
  needs the mock to render a scripted step as a delegation call for clients that
  advertise one, the same accommodation already made for text-ReAct and
  `final_answer` clients. That is the next step for this row.
- **More than three roles.** The compounding above predicts the prompt cost grows
  faster than the call count. Two data points do not establish a curve.
