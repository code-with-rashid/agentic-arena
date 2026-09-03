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

`smolagents_multi` is that pipeline, with the same three roles and the same role
wording as the other three entries:

    researcher --writer(task)--> writer --editor(task)--> editor

### It costs 3× the calls, where every other mechanism costs 2×

| entry | prompt tok | completion | LLM calls | pass |
|---|--:|--:|--:|--:|
| `smolagents` | 2584.1 | 115.5 | 2.00 | 10/10 |
| `smolagents_multi` | 10419.3 | 589.9 | 6.00 | 10/10 |

| kind | comparison | prompt | LLM calls |
|---|---|--:|--:|
| structural | `vanilla` → `vanilla_multi` | 2.50× | 2.00× |
| structural | `langgraph` → `langgraph_multi` | 2.62× | 2.00× |
| model-decided, speaker swap | `openai_agents` → `openai_agents_multi` | 2.76× | 2.00× |
| model-decided, sub-agent as tool | `smolagents` → `smolagents_multi` | **4.03×** | **3.00×** |
| model-decided, sub-agent as tool | `pydantic_ai` → `pydantic_ai_multi` | **3.57×** | **3.00×** |

Three roles cost two model calls in every mechanism above except this one, which
costs three. The reason is visible on the wire — six requests, down the chain and
back up it:

```
req1: researcher   searches
req2: researcher   delegates to writer
req3: writer       delegates to editor
req4: editor       answers
req5: writer       answers          <- pure mechanism
req6: researcher   answers          <- pure mechanism
```

**A sub-agent's reply is a tool result, not the end of the run.** A handoff hands
the conversation over and the receiving agent finishes it; a managed sub-agent
hands a *value* back to a manager that is still running and must now produce its
own final answer. So every level of nesting costs one extra call that a handoff
does not, and the cost grows with the depth of the chain rather than with the work.

That is the finding, and `tests/test_multi_agent_arena.py` asserts the six-stage
sequence directly — a pipeline that collapsed to two roles posts
`['researcher', 'researcher', 'writer', 'researcher']` and fails.

**One thing this measurement does not include.** The mock delegates by passing
the original task through verbatim, so the writer never receives the researcher's
findings. That is the *cheapest* delegation possible; a real manager composing a
task that carries its research would send more, not less. Read 4.03× as a floor.
It is also a property of the mechanism worth knowing on its own: with a speaker
swap the transcript comes along automatically, and with a sub-agent it does not —
context has to be passed by hand, and you pay for it again.

### And offering one costs 3.3× a handoff, before anyone delegates

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

### The same shape without a delegation feature: `pydantic_ai_multi`

`pydantic_ai_multi` is the same three roles again, with the same wording, wired
the same way — except that **Pydantic AI has nothing called delegation**. There
is no `managed_agents` list and no `AgentTool` wrapper. The delegate is an
ordinary async tool whose body happens to `await sub_agent.run(...)`, and the
library does not know a sub-agent is involved:

| entry | prompt tok | completion | LLM calls | pass |
|---|--:|--:|--:|--:|
| `pydantic_ai` | 696.7 | 86.2 | 2.00 | 10/10 |
| `pydantic_ai_multi` | 2486.7 | 269.0 | 6.00 | 10/10 |

**3.57× prompt, 3.00× LLM calls** — the same call multiplier as
`smolagents_multi`, because it is the same mechanism, hand-built. That is the
sharpest form of the claim below: the 2N cost is not a library's implementation
of delegation, it is what happens when a sub-agent's reply is a value rather than
the end of the conversation.

The two entries also make the *other* smolagents number legible. Same mechanism,
same roles, same task, same scripted turns: **2487 prompt tokens against 10578**.
Four times the bill for identical work, and none of it is the delegation — it is
the ~4 KB templated system prompt each smolagents sub-agent carries.

Nested runs share one `RunUsage`, which is how the reported cost stays honest;
without it a pipeline would bill like a single agent, which is exactly what
[`tests/test_usage_accounting.py`](../tests/test_usage_accounting.py) exists to
catch. One consequence worth naming: 2N at three roles is six LLM calls against a
default `max_tool_iterations` of six, so this mechanism spends the *whole*
per-item allowance where a handoff chain spends four of it.

### What the mock needed in order to drive a nested pipeline

The handoff accommodation is stateless because a transfer swaps the speaker
inside *one* conversation: the assistant-turn count keeps climbing and the last
agent, offering no transfer, answers. A managed sub-agent breaks both halves of
that — it gets a **fresh** conversation, and the manager goes on advertising it
forever. Three narrow changes, each of which is a small correctness improvement
on its own:

- **An agent holding none of the arena's tools skips scripted tool-call turns.**
  Otherwise a sub-agent is served turn 1, the researcher's `search` call, for a
  tool the writer role deliberately does not have. Deliberately *not* the more
  obvious "skip any turn whose tool this client did not advertise" — that rule
  deletes `res-02`, which scripts a call to a tool that does not exist on
  purpose. The narrow version leaves every normal adapter and every scripted
  fault exactly as they were.
- **Delegate at most once per tool per conversation**, read off the transcript so
  the server stays stateless. This is what terminates the chain. It has to check
  both encodings: smolagents replays its own calls as assistant *content*
  (`Calling tools: [{'function': {'name': 'editor', …}}]`), so looking only at
  the structured `tool_calls` field finds nothing and the manager delegates on
  every turn until its budget is gone — which is exactly what happened first.
- **The delegation call carries the task.** `transfer_to_*` takes no arguments,
  but a sub-agent about to start a fresh conversation has to be told something.
  Passing the original user message is what a manager would send, and it keeps
  the sub-agent on the same scenario so the pipeline stays on the same item.

Recognising a delegate at all needs the arena's declared tool list, because
`writer` is indistinguishable from a task tool by name — so the harness now hands
`MockServer` the arena's tools. A bare `MockServer` in a test still recognises
only the explicit `transfer_to_*` shape, which is the narrower behaviour on
purpose. Verified behaviour-preserving: the handoff chain's numbers are unchanged
to the decimal (2.76×, 2.00×).

## How this scales: three laws, five implementations

Three roles was one point, and this page previously said plainly that two points
do not establish a curve. Measured from one role to five, across **five**
delegation implementations in four libraries, every one follows an exact law:

| roles | | 1 | 2 | 3 | 4 | 5 | |
|---|---|--:|--:|--:|--:|--:|---|
| `handoffs` (openai_agents) | speaker swap | 2 | 3 | 4 | 5 | 6 | **N + 1** |
| `sub_agents` (google_adk) | transfer, returns to parent | 2 | 4 | 5 | 6 | 7 | **N + 2** |
| `managed_agents` (smolagents) | sub-agent as a tool | 2 | 4 | 6 | 8 | 10 | **2N** |
| `AgentTool` (google_adk) | sub-agent as a tool | 2 | 4 | 6 | 8 | 10 | **2N** |
| agent delegation (pydantic_ai) | sub-agent as a tool | 2 | 4 | 6 | 8 | 10 | **2N** |

### The 2N law is the mechanism, not the library

smolagents, Google ADK and Pydantic AI share no code, and their sub-agent-as-tool
implementations agree at **every** depth. A sub-agent's reply is a tool result
rather than the end of the run, so each intermediate level costs 2 (delegate,
then answer), the top costs 3 (tool call, delegate, answer), the leaf costs 1 —
2N.

The third one is what settles it, because **Pydantic AI has no delegation
feature**. There is no `managed_agents` list and no `AgentTool` wrapper: the
delegate is an ordinary async tool whose body happens to `await sub.run(...)`, and
nothing in the library knows a sub-agent is involved. It still costs exactly 2N.
Two implementations were a pattern; three, one of which is not a feature at all,
means the cost is in the *shape* — a nested run returns a value instead of ending
the conversation — and no library choice avoids it.

### "Handoff" is not one thing

Both the OpenAI Agents SDK and ADK describe theirs as transferring to another
agent. They do not cost the same, because **ADK returns control to the parent**
when the sub-agent finishes and the parent then speaks again — one extra call,
constant with depth, and the whole difference between N+1 and N+2. Same word,
different control flow.

### You pay in calls or in prompt, and the call law points the wrong way

Prompt tokens for the same five chains, one role to four:

| | 1 | 2 | 3 | 4 | call growth | prompt growth |
|---|--:|--:|--:|--:|--:|--:|
| `handoffs` — swap | 452 | 907 | 1362 | 1883 | 2.50× | 4.17× |
| `sub_agents` — transfer | 479 | 3168 | 5229 | 7375 | 3.00× | **15.40×** |
| `managed_agents` — as tool | 2367 | 5859 | 9311 | 13441 | 4.00× | 5.68× |
| `AgentTool` — as tool | 479 | 1126 | 1423 | 1722 | 4.00× | **3.59×** |
| agent delegation — as tool | 430 | 1056 | 1318 | 1581 | 4.00× | **3.68×** |

Inside ADK — same library, same model, same task, so nothing else explains it —
four roles cost **6 calls and 7375 prompt tokens** with `sub_agents`, and **8
calls and 1722** with `AgentTool`. A transfer keeps *one* conversation that every
agent sees all of, so the prompt compounds. A sub-agent starts a *fresh* one, so
the prompt stays nearly flat and the calls compound instead — the only mechanism
here where prompt grows **slower** than call count.

Cheaper in calls is dearer in prompt, and prompt is usually the larger bill. A
reader who took only the call-count law from this page would pick the wrong one.

And restarting the conversation only helps if there is little to re-send.
smolagents also starts each sub-agent fresh, and its prompt still grows faster
than its calls (5.68×). The obvious explanation is its own ~4 KB templated system
prompt, re-sent by every fresh sub-agent — the scaffolding behind its 3.90×
single-agent overhead in [overhead.md](overhead.md) — but with one comparison
that was an explanation, not a measurement.

**Pydantic AI's chain is what turns it into one.** It restarts each sub-agent's
conversation exactly as smolagents does, and it lands on ADK's numbers rather
than smolagents': **1581 prompt tokens at four roles against ADK's 1722 and
smolagents' 13441**, growing 3.68× against 3.59× and 5.68×. Two independent
implementations of the same mechanism agreeing, and a third an order of magnitude
away, isolates the difference in the library — not in starting fresh.

Note also which implementation is cheapest in prompt at four roles: the one that
costs the **most** calls. `pydantic_ai` delegation spends 8 calls to `handoffs`'
5, and 1581 prompt tokens to its 1883.

> **Correction.** An earlier version of this section said prompt cost grows
> faster than call count, full stop. That was measured on two mechanisms and
> broke on the first new one: `AgentTool` grows 3.59× in prompt against 4.00× in
> calls. The claim now holds only where the conversation keeps growing, and the
> test that gates it excludes the mechanisms it does not cover explicitly rather
> than quietly — `AgentTool` then, and `pydantic_ai` delegation now.

All of this is gated in `tests/test_delegation_depth.py` rather than described,
because a library change could break a law while every depth-3 number on this
page still looked right. Verified non-vacuous: with the mock's "delegate once per
tool" rule disabled, three roles cost 72 calls instead of 6.

## Does forwarding context change the ranking? No — it widens the gap

Every number on this page is measured with the delegate told **only the original
task**, the cheapest thing a manager could possibly forward. That is the obvious
objection to the whole comparison: the design favours whichever mechanisms carry
the transcript for free, so the ranking might be an artifact of the harness rather
than a fact about delegation.

Measured, with the **same payload handed to every framework** so that who pays is
the mechanism and not whatever transcript a particular library happens to keep.
Extra prompt tokens per item against forwarding nothing:

| forwarded characters | 0 | 277 | 553 | 1105 |
|---|--:|--:|--:|--:|
| `vanilla_multi` — structural | 0 | **0** | **0** | **0** |
| `langgraph_multi` — structural | 0 | **0** | **0** | **0** |
| `openai_agents_multi` — speaker swap | 0 | **0** | **0** | **0** |
| `smolagents_multi` — sub-agent as tool | 0 | 509 | 978 | 1916 |
| `pydantic_ai_multi` — sub-agent as tool | 0 | 508 | 977 | 1915 |

**Three of the four mechanisms forward for free; one pays.** A structural pipeline
shares one transcript by construction. A speaker swap hands the *same*
conversation on, and its `transfer_to_<agent>` tool declares no parameters at all
— there is nowhere to put a payload and nothing that needs one. Only a sub-agent
invoked as a tool starts a **fresh** conversation, so it has to be told, and it
pays.

**The two sub-agent implementations agree to within one token at every size** —
509/978/1916 against 508/977/1915, in libraries that share no code. The same
signature as the 2N call law, now in a second dimension.

**And forwarding is priced like a system prompt, not like a message.** About
**1.77 tokens per forwarded character**, not the 0.25 you would get from one copy:
the payload becomes the sub-agent's opening user message and is then re-sent on
every request of that sub-agent's conversation.

So the published 4.03× and 3.57× really were floors, and this says how far above
them a realistic pipeline sits. Forwarding a modest 553-character findings block
takes `pydantic_ai_multi` from 3.57× to about 4.9× against its single-agent
entry, while `openai_agents_multi` stays exactly where it was at 2.76×. The
ranking does not invert; the gap roughly doubles.

What this deliberately does not say is whether forwarding **helps**. The mock
replays the same script either way, so the benefit stays held at zero by
construction — the same caveat as everywhere else on this page, and the reason
[`tests/test_delegation_forwarding.py`](../tests/test_delegation_forwarding.py)
pins that the answer is byte-identical with and without the payload. A cost
comparison that quietly became a quality comparison would be worthless.

## Still open

- **CrewAI crews**, the same sub-agent-as-tool shape again, and still blocked on
  an adapter that has never been mock-verified.
- **Whether the laws survive a real model.** They are structural, so they should,
  but a real model may delegate more than once or answer without delegating at
  all. That needs a live run.
- **More than three roles.** The compounding above predicts prompt cost grows
  faster than call count, and the handoff finding predicts it grows with the
  number of *offered* transfers too. Two points do not establish a curve.
