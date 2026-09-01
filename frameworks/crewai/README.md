# `crewai` adapter

A single-agent sequential `Crew` with the shared search / calculator tools.

- **Deps:** see [requirements.txt](requirements.txt). **Python 3.11 / 3.12 only** —
  CrewAI's transitive tree (chromadb, onnxruntime, numpy) has no wheels for 3.14.
- **LLM:** `crewai.LLM(model=f"openai/{config.model}", base_url=..., api_key=...)` —
  CrewAI routes through LiteLLM, so the shared gateway is an OpenAI-compatible
  provider.
- **Tools:** `crewai.tools.BaseTool` subclasses that record each call into a sink
  list (CrewAI does not expose tool-call history directly) and then delegate to
  the unmodified `arena.tools` functions.
- **Metrics:** `crew.usage_metrics` for tokens and request count.

## Status: partially working, not yet in CI

Debugged on Python 3.12 in GitHub Actions (`.github/workflows/crewai-debug.yml`,
`workflow_dispatch`). Current state on crewai 0.203.2 / litellm 1.74.9:

| | |
|---|---|
| adapter builds | ✅ |
| runs without crashing | ✅ (was `AttributeError: 'list' object has no attribute 'rstrip'`) |
| produces the correct final answer | ✅ e.g. `'17 * 23 + 4 = 395.'` |
| records tool calls | ❌ the sink stays empty, so every `tool_used` check fails |
| **mock score** | **0/15** — answers right, tool evidence missing |

### The big finding: CrewAI does not use native tool calling

Measured from the request bodies the mock server received:

```
advertised tools  : []
stop param        : ['\nObservation:']
```

CrewAI's agent executor advertises **no** OpenAI functions. It drives a **text
ReAct loop** — the prompt ends on a dangling `Thought:` and it expects the
completion to continue with `Action:` / `Action Input:`, stopping at
`Observation:`. `llm.supports_function_calling()` returns `True`; the executor
simply does not use it.

That is a genuine comparative fact about the framework, and it is why the
original adapter scored 0/15: the arena's mock replayed native `tool_calls` with
`content: None`, CrewAI's parser received a list where it wanted a string, and
`format_message_for_llm` blew up on `prompt.rstrip()`.

`arena.llm.mockserver` now renders each scripted turn in whichever protocol the
client asked for (see `_looks_like_react`), so CrewAI faces the *same* scripted
decisions as everyone else rather than being excluded on protocol grounds. That
fixed the crash and the final answers.

### What is still open

The tool-call sink stays empty even though the answers come out right, which
means CrewAI reaches the second scripted turn without `BaseTool._run` ever
firing — it appears to write an `Observation:` back into the transcript by some
path that bypasses the wrapper. Someone with a local 3.12 environment should:

1. Log inside `SearchTool._run` / `CalculatorTool._run` to confirm they never run.
2. Dump the full transcript CrewAI builds (the `Observation:` text will say
   whether the tool errored, was not found, or was never attempted).
3. If CrewAI resolves tools by a normalised name, align the `Action:` name the
   mock emits with whatever CrewAI advertises in its prompt.
4. Consider reading tool calls from CrewAI's event bus instead of a wrapper sink.

Until the sink works, `crewai` stays **out of the required `mock-smoke` matrix**.

```bash
python3.12 -m venv .venv-crewai && . .venv-crewai/bin/activate
pip install -e . -r frameworks/crewai/requirements.txt
python -m arena run --arena tool_use --framework crewai --mode mock
```
