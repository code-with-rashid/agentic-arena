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

## Two kinds of delegation, and they do not cost the same

The pipelines above are **structural**: the graph always visits all three roles,
so delegation is a property of the wiring. The other kind is **model-decided** —
each agent is handed a `transfer_to_<agent>` tool and *chooses* to delegate.
`openai_agents_multi` is that: a native `handoffs` chain,
`researcher -> writer -> editor`.

| entry | prompt tok | completion | LLM calls | pass |
|---|--:|--:|--:|--:|
| `openai_agents` | 686.7 | 86.2 | 2.00 | 10/10 |
| `openai_agents_multi` | 1894.8 | 140.2 | 4.00 | 10/10 |

| kind | comparison | prompt | LLM calls |
|---|---|--:|--:|
| structural | `vanilla` → `vanilla_multi` | 2.50× | 2.00× |
| model-decided | `openai_agents` → `openai_agents_multi` | **2.76×** | 2.00× |

Same number of LLM calls, ~10% more prompt. Where that goes is the interesting
part — decomposing one item's four requests:

| | messages | tool schemas |
|---|--:|--:|
| `vanilla_multi` | 6767 | 722 |
| `openai_agents_multi` | 6818 | 1495 |
| difference | **+51** | **+773** |

**You pay for a handoff mostly by advertising it, not by taking it.** The
transfer call and its result add 51 characters to the whole conversation. The
`transfer_to_*` schemas add 773 — `transfer_to_writer` rides on every one of the
researcher's requests (262 chars × 2) and `transfer_to_editor` on the writer's
(249), whether or not anyone ever delegates. That is 94% of the difference, and
it accounts for the gap exactly.

The practical consequence: a supervisor with N possible handoffs pays for N tool
schemas on *every* request in the run. The option costs more than the act, and it
scales with how many options you offer rather than with how many you use.

One more difference worth not misreading: `openai_agents_multi` has *lower*
completion tokens (140.2 vs 198.0). That is not efficiency. In the structural
pipeline the writer and the editor each emit a full brief; in the handoff chain
the researcher emits a short transfer call instead of a draft, so only the last
agent writes a brief. Different work, not cheaper work.

### How a scripted mock delegates at all

Model-decided delegation cannot be measured against a mock that only replays a
scripted answer: the model never *chooses* anything, so the adapter would simply
never hand off and would silently report the single-agent numbers.

So the mock renders the scripted "the research is done, now write it up" step as
a transfer, for clients that advertise one — the same accommodation already made
for text-ReAct clients and for `final_answer`. The scripted *decision* is
identical for everyone; only its wire format follows the client.

It needs no state to terminate: after a transfer the receiving agent is the one
talking, and it advertises its own handoffs or none. The last agent in the chain
offers no transfer, so it answers. On the wire:

```
req1: stage=researcher  tools=['search','transfer_to_writer']
req2: stage=researcher  tools=['search','transfer_to_writer']
req3: stage=writer      tools=['transfer_to_editor']
req4: stage=editor      tools=[]                      <- answers
```

A single-agent adapter never advertises a transfer tool and is unaffected.

`transfer_to_` is exempt from the "only declared tools" rule for the same reason
`final_answer` is: delegating grants no arena capability, because the receiving
agent carries the same arena prompt and only its own declared tools. Unlike
`final_answer` it has to be a *prefix*, since the target agent's name is in the
tool name — `arena/tools/__init__.py` names that weakening and what bounds it.

## A third shape: the sub-agent invoked as a tool

smolagents' `managed_agents` is model-decided like a handoff, but structurally
different: the sub-agent is advertised as an ordinary tool named after itself, and
calling it runs a whole nested agent whose result comes back as the tool's return
value. The speaker never changes.

"You pay to advertise, not to take" **generalises to it — and costs 3.3× more.**
Measured with no delegation happening at all, characters of system prompt plus
tool schema on the *first* request:

| sub-agents offered | system prompt | tool schemas | total | marginal |
|---:|---:|---:|---:|---:|
| 0 | 3311 | 518 | 3829 | — |
| 1 | 4102 | 982 | 5084 | +1255 |
| 2 | 4498 | 1455 | 5953 | +869 |
| 3 | 4900 | 1934 | 6834 | +881 |

Linear after the first, at **~875 characters per offered sub-agent, on every
request**. The step down after the first is a ~385-character preamble ("You can
also give tasks to team members…") that switches delegation on and is paid once.

The marginal ~875 splits into ~400 characters of prose in the system prompt and
~475 of JSON tool schema, because **each sub-agent is described twice** — exactly
as smolagents describes its tools twice, which is most of its 3.77× prompt
overhead in [overhead.md](overhead.md). The same design decision shows up in both
places.

Against the OpenAI Agents SDK's 262-character `transfer_to_writer` schema, that
is 3.3× to hold open the same option. Both frameworks charge you for options
rather than actions; they do not charge the same amount.

The invariants are gated in `tests/test_delegation_advertising.py` — the cost is
paid on every request rather than only the delegating one, it scales with how
many delegates are offered, and each sub-agent really is described twice. The
byte counts stay findings.

## Still open

- **An end-to-end pipeline number for `managed_agents`.** The advertising cost
  above is measured; the full three-role cost is not, and the blocker is the
  mock rather than the adapter. The handoff accommodation terminates without any
  state because a transfer swaps the speaker inside *one* conversation, so the
  assistant-turn count keeps climbing and the last agent — offering no
  transfer — answers. A managed sub-agent instead gets a **fresh** conversation,
  so the mock would replay the script from turn 1 and serve it a `search` call it
  has no tool for, and the manager goes on advertising the sub-agent forever, so
  nothing terminates. Making this work needs the mock to skip scripted tool calls
  a client never advertised, and to delegate at most once per tool per
  conversation. Both look reasonable and neither is written.
- **CrewAI crews**, the same shape again, and still blocked on an adapter that
  has never been mock-verified.
- **More than three roles.** The compounding above predicts prompt cost grows
  faster than call count, and the handoff finding predicts it grows with the
  number of *offered* transfers too. Two points do not establish a curve.
