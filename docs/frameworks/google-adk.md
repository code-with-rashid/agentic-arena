# Google ADK

[Adapter](../../frameworks/google_adk/adapter.py) · `google-adk==2.8.0` +
`litellm==1.99.0` · runs 5 of 7 arenas

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
| `human_in_the_loop` | unsupported — no `resume` method |
| `durable_state` | unsupported — no `resume` method |

### Prompt size: 1.05× baseline *(comparable)*

791 estimated prompt tokens per item against `vanilla`'s 754. That puts ADK
inside the 1.15× band the other five in-band frameworks occupy, at its heavy end —
marginally above the OpenAI Agents SDK. Nothing unusual on the wire; it
serialises the same two tool schemas slightly less compactly than most.

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

## Not yet done

- **No pause.** ADK ships `LongRunningFunctionTool` and the `LlmAgent` carries
  `rerun_on_resume` / `wait_for_output` fields, so a pause looks reachable — it is
  simply not adapted yet, which is why both pause arenas report *unsupported*
  rather than failing. That is the obvious next contribution here, and would be a
  sixth distinct mechanism.
- **Gemini itself is unmeasured.** Everything above is ADK driving an
  OpenAI-compatible endpoint through LiteLLM, which is the only way to hold the
  model constant across frameworks. ADK against Gemini would be a different
  measurement and is out of scope for this benchmark's fairness rules.
