# Do all seven frameworks describe the same tool?

## The question nobody had asked

[`overhead.md`](overhead.md) measured what each framework's `tools` block
**costs** — 501 to 701 characters for the same two tools, a 1.4× spread — and read
that spread as serialisation. Nothing had compared what those bytes actually
**say**.

They were not saying the same thing.

## What was diverging

`arena/tools/__init__.py` holds the canonical spec. `vanilla` sends it verbatim,
because it is the only adapter that uses `specs_for()` directly; every framework
adapter re-declares the tool in its own idiom. Comparing the wire against the
canonical spec:

| what the arena declared | what was reaching the model |
|---|---|
| `search(query, k=3)` | **`google_adk`, `smolagents`: `search(query)`** — the `k` parameter simply absent |
| `query: "What to look up."`<br>`k: "How many snippets."` | **`langgraph`, `pydantic_ai`, `openai_agents`, `microsoft_af`: bare types**, no parameter description at all |
| `"Search a knowledge base of general facts. Returns up to k text snippets."` | all six: a shortened description that no longer mentions `k` |

**Mock mode cannot see any of this.** The mock replays scripted tool calls
whatever the schema said, so every arena stayed green while two frameworks were
being offered a strictly narrower tool and four a less-described one. Live, it
would have surfaced as a quality difference and been attributed to the framework.

Same class of unfairness as an unwired
[iteration budget](methodology.md#3b-one-iteration-budget) or an unwired
[request timeout](methodology.md#3c-one-request-timeout) — a control the arena
owns, silently not reaching one adapter.

## Why each one dropped it

Not carelessness in the same way twice. **No framework here reads a parameter
description from the docstring**, and each wants it somewhere different:

| framework | where a parameter description must go |
|---|---|
| `langgraph` | `Annotated[str, "..."]` — a bare string in the annotation |
| `pydantic_ai`, `openai_agents`, `microsoft_af` | `Annotated[str, Field(description="...")]` |
| `google_adk`, `smolagents` | a Google-style `Args:` block in the docstring |

The two that dropped `k` are the two that build the schema from the **docstring**:
ADK's known gotcha is that a missing `Args:` entry silently changes the schema,
and it turns out the adapter had a missing signature parameter rather than a
missing `Args:` line — with the same result.

One more trap, specific to `Annotated`: with `from __future__ import annotations`
in force, an `Annotated` imported inside the function body is invisible to the
decorator, because `get_type_hints` resolves against module globals. It fails at
build time with a bare `NameError` rather than by quietly dropping the
description, which is the better failure of the two.

## What it did to the published numbers

This is the part worth reading. Re-running `tool_use` with every framework
describing the same tool:

| framework | prompt tokens / item | **was** | vs baseline | was |
|---|---:|---:|---:|---:|
| `vanilla` (stdlib baseline) | 753.5 | 754 | **1.00×** | 1.00× |
| `langgraph` | **753.5** | 683 | **1.00×** | *0.91×* |
| `pydantic_ai` | 794.0 | 724 | 1.05× | *0.96×* |
| `microsoft_af` | 802.0 | 732 | 1.06× | *0.97×* |
| `google_adk` | 836.1 | 791 | 1.11× | 1.05× |
| `openai_agents` | 856.9 | 787 | 1.14× | 1.04× |
| `smolagents` | 2935.5 | 2845 | 3.90× | 3.77× |

### The old headline was an artifact

`overhead.md` and the decision guide both said, prominently, that **the
hand-rolled baseline is not the leanest** — that three of four frameworks
serialise the same tools more compactly than the by-hand version. That claim had
already survived one correction, having replaced an earlier hypothesis that the
baseline *would* be cheapest.

It was wrong for a second time, and for a reason neither version considered: the
frameworks were cheaper because they were **sending less**.

With the tools equalised, **`langgraph` ties the baseline exactly** — 753.5
prompt tokens against 753.5, and a `tools` block of 637 characters against 637,
byte for byte. Its entire 0.91× advantage was four missing parameter
descriptions.

### The corrected version

**No framework is leaner on the wire than the hand-rolled loop.** The baseline is
the floor, and the band above it is now 1.00× to 1.14× rather than 0.91× to
1.05×. The spread is about the same size; the sign is not.

That is a smaller claim than the one it replaces, and a duller one. It is also
the one the measurement supports.

## What is a framework property, and stays a finding

Not everything that differs is fixable, and some of it is interesting:

- **`openai_agents` emits `strict: true`**, and OpenAI's strict mode requires
  *every* property to appear in `required` — so `k` is marked required even
  though the arena gave it a default. The model must supply it on every call.
  That is a real behavioural difference, not an adapter choice, and it is part of
  why this adapter now has the largest `tools` block of the in-band six.
- **`pydantic_ai` and `openai_agents` add `additionalProperties: false`**;
  `openai_agents`, `microsoft_af` and `google_adk` add `title` on every property
  and on the object. Billable, and nobody's fault.
- **`google_adk` folds the `Args:` block into the tool description** rather than
  emitting per-parameter `description` keys. The information reaches the model;
  the shape differs.

## What is gated

[`tests/test_tool_schema_fidelity.py`](../tests/test_tool_schema_fidelity.py)
holds every adapter to the tool the arena declared:

- **every declared parameter reaches the model** — a framework offered a narrower
  tool is being handed a different task;
- **every parameter keeps its declared type**;
- **every parameter the arena described is described on the wire** — text, not
  wording, since a framework may legitimately reformat it, and ADK's fold into
  the tool description counts;
- **the tool itself is described**;
- **the baseline still sends the canonical spec unmodified**, because `vanilla`
  is what "the arena declared" means in practice, and a drifting reference would
  move every comparison above.

Not gated: `strict`, `title`, `additionalProperties`, and strict mode's widening
of `required`. Those are framework properties, reported here.

## Not measured

- **Whether any of this changes answers.** It plainly could — a model that cannot
  see `k` cannot vary it, and a model shown a bare `query: string` has less to go
  on — but mock mode replays scripted calls, so the size of the effect needs a
  live run.
- **The other arenas' tools.** `search_rooms`, `book_room`, `request_approval`
  and `save_progress` are declared per-adapter the same way and were not audited
  here; the gate covers whichever tools the arena under test declares, so running
  it against another arena would extend the check.
