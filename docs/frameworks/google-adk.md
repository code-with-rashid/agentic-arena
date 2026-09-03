# Google ADK

[Adapter](../../frameworks/google_adk/adapter.py) · `google-adk==2.8.0` +
`litellm==1.99.0` + `sqlalchemy` · runs all 7 arenas

Google's Agent Development Kit. An `LlmAgent` driven by `InMemoryRunner`.

## Wiring

ADK is Gemini-first. Reaching the shared OpenAI-compatible gateway goes through
its LiteLLM backend:

```python
model = LiteLlm(model=f"openai/{config.model}", api_base=..., api_key=..., temperature=0.0)
agent = LlmAgent(name="arena_agent", model=model, instruction=arena.system_prompt, tools=[...])
runner = InMemoryRunner(agent=agent, app_name="arena")
```

**`litellm` is therefore a hard requirement of this adapter, not an optional
extra** — and it is the heaviest dependency of any adapter here, pulling
`boto3`, `tokenizers`, `huggingface-hub` and `tiktoken`. That is a real cost of
adopting ADK against a non-Google provider, so it is pinned and documented rather
than hidden. Against Gemini you would not pay it.

Tool schemas are built from the function signature **and the Google-style
docstring**, so the `Args:` blocks in the adapter are load-bearing rather than
decoration.

## Two things it gets right

**`RunConfig(max_llm_calls=N)` is a real loop cap.** Measured against a mock that
never stops asking for tools, a budget of N produces exactly N requests on the
wire — no off-by-one, no uncapped default. Compare Pydantic AI (`retries` is not
a loop cap: 50 calls on a budget of 6), Agent Framework (uncapped by default: 41),
and smolagents (one call beyond `max_steps`). ADK needed no correction at all.

It also raises `LlmCallsLimitExceededError` when the budget is spent rather than
returning a blank answer, which is the behaviour that makes an exhausted run
legible instead of looking like a bad reply.

**Usage reporting is exact.** Per-event `usage_metadata` sums precisely to what
the gateway served, so `AgentResult` needs no reconstruction — verified by
`tests/test_usage_accounting.py`, which holds every adapter's self-report against
the wire.

## Results *(comparable columns marked)*

| arena | result |
|---|---|
| `tool_use` | 15/15 |
| `structured_output` | 15/15 |
| `rag` | 15/15 |
| `multi_agent` | 10/10 |
| `resilience` | **6/8** *(comparable)* |
| `human_in_the_loop` | 12/12 |
| `durable_state` | 8/8 |

### Prompt size: 1.11× baseline *(comparable)*

836 estimated prompt tokens per item against `vanilla`'s 754. That puts ADK
inside the 1.15× band the other five in-band frameworks occupy, at its heavy end.
Nothing unusual on the wire; it serialises the same two tool schemas slightly less
compactly than most.

> **Correction.** This said *1.05×, marginally above the OpenAI Agents SDK*, and
> both halves were wrong. ADK was declaring `search(query)` where the arena
> declares `search(query, k=3)` — a parameter the model was never offered — so it
> was cheaper because it was **sending less**. With the schemas equalised it is
> 1.11× and the OpenAI Agents SDK is above it at 1.14×. See
> [tool-schemas.md](../tool-schemas.md).

### `resilience` 6/8 — the only framework that loses both

| item | fault | result |
|---|---|---|
| `res-01` | malformed JSON arguments | **fail** — `JSONDecodeError` |
| `res-02` | tool that does not exist | **fail** — `ValueError: Tool 'teleport' not found.` |
| `res-03`–`res-08` | everything else | pass |

Both losses are **uncaught exceptions**, not the model giving up: ADK parses tool
arguments and resolves tool names strictly, and neither failure is turned into
something the model can read and correct from. It is the only adapter that loses
*both* of these — LangGraph loses only `res-01`, the OpenAI Agents SDK only
`res-02`.

The good news is that it recovers from all six faults where the tool actually
ran, including the missing-argument and unexpected-argument cases that
`smolagents` loses. The boundary here is narrower than smolagents': ADK fails at
*parse and dispatch*, not at every validation step.

Both are the kind of thing a retry wrapper handles, but they surface as a crash
rather than a degraded answer, which is at least loud.

## Also worth knowing

**Tool results come back wrapped.** ADK hands output to the model as
`{"result": "<the text>"}`, so the payload is JSON-escaped. The wire-level
contract test now decodes a JSON-object message before comparing, because that is
an encoding difference rather than an alteration — the same category as
smolagents' `Observation:` prefix. Truncation and summarisation still fail the
check.

## The pause: a long-running tool, and one thing it does not do

ADK's pause is `LongRunningFunctionTool` — the tool returns a `{"status":
"pending"}` marker, the run reports the call in `long_running_tool_ids`, and the
real answer is supplied later against the same `function_call_id`. That is a
sixth distinct mechanism; no two of the six look alike.

**But it does not stop the run.** Left to itself, ADK hands the model the
`pending` marker as the tool result and the model carries on — measured, it went
straight on to call `book_room` without any human decision, which is exactly what
the arena's `no_tool_before_suspend` check exists to catch. Breaking out of the
event stream when `long_running_tool_ids` appears is what makes the pause real:

```python
async for event in stream:
    if call.id in (event.long_running_tool_ids or set()):
        pending = (call.id, call.name, summary)
        break  # <- the pause
await stream.aclose()  # or ADK's contextvars unwind noisily
```

So this is a *reported* interrupt rather than an *enforced* one. Worth knowing
before you rely on it for anything consequential: the signal is there, but
nothing stops the agent if you do not act on it.

Resuming is fully native — a `types.FunctionResponse` carrying the decision
against the same call id. Nothing about the transcript is reconstructed by hand.

### Durable, at the cost of one more dependency

`durable_state` throws the runner away at the pause, so the session has to be on
disk. `DatabaseSessionService` does exactly that, and the adapter points it at the
harness-owned checkpoint dir — the same shape as LangGraph's `SqliteSaver`:

```python
DatabaseSessionService(db_url=f"sqlite+aiosqlite:///{checkpoint_dir}/adk_sessions.sqlite")
```

Two traps: a Windows path needs forward slashes, and plain `sqlite://` fails with
*"the asyncio extension requires an async driver"* — it must be `sqlite+aiosqlite`
(which ships with google-adk).

That costs `sqlalchemy`, on top of an already heavy tree. Without it ADK still
pauses, but only for as long as the process lives.

`resume_state` is three strings (session id, call id, call name), so it crosses
the JSON gap trivially — everything else lives in the store. 8/8, and the arena's
`call_counts` check confirms it resumed rather than restarted: exactly
`{'search': 2, 'calculator': 1}`, with no repeated lookups.

One gotcha worth naming: on a non-durable arena `resume` builds a fresh `Runner`,
and a fresh `InMemorySessionService` with it arrives **empty** — the conversation
lives in the session service, not in the `Runner`. Caching it is what took
`human_in_the_loop` from 0/12 to 12/12. On a durable arena the bug is invisible,
because the store is on disk.

## Two delegation mechanisms, and they cost in different currencies

ADK is the only framework here that ships **both** shapes of model-decided
delegation, which makes it the cleanest place to compare them — same library,
same model, same task, so nothing else can explain the difference.

| | delegates by | 4-role chain |
|---|---|---|
| `sub_agents` | `transfer_to_agent(agent_name=…)` | 6 calls, 7375 prompt tokens |
| `AgentTool(agent=…)` | the sub-agent advertised as a tool | 8 calls, 1722 prompt tokens |

**`AgentTool` costs a third more calls and a quarter of the prompt.** A transfer
keeps one conversation that every agent sees all of, so the prompt compounds
(15.4x from one role to four, against 3x the calls). An `AgentTool` sub-agent
starts a *fresh* conversation, so the prompt stays nearly flat and the calls
compound instead — the only mechanism measured here where prompt grows *slower*
than call count.

Since prompt tokens are usually the larger bill, the call count alone points the
wrong way. Worth deciding on purpose rather than by which appeared first in the
docs.

Two more things worth knowing about `sub_agents`:

- **It is not a clean speaker swap.** Control comes *back* to the parent when the
  sub-agent finishes, and the parent then speaks again. That is one extra call
  the OpenAI Agents SDK never makes (N+2 rather than N+1), constant with depth.
- **The transfer tool is parameterised by target**, not one tool per target:
  a single `transfer_to_agent` whose `agent_name` parameter carries an `enum` of
  the agents that stage may hand to. Both shapes are described in
  [multi-agent.md](../multi-agent.md#how-this-scales-three-laws-five-implementations).

## Not yet done

- **Gemini itself is unmeasured.** Everything above is ADK driving an
  OpenAI-compatible endpoint through LiteLLM, which is the only way to hold the
  model constant across frameworks. ADK against Gemini would be a different
  measurement and is out of scope for this benchmark's fairness rules.
