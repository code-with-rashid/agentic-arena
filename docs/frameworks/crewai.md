# CrewAI — deep dive

## At a glance

- Package / repo: [`crewai`](https://github.com/crewAIInc/crewAI) — requirement is
  a **range** (`crewai>=0.130,<1.0`), not a pin, because the adapter is not yet
  verified. See [dependencies.md](../dependencies.md).
- Licence: MIT
- Adapter: [`frameworks/crewai/adapter.py`](../../frameworks/crewai/adapter.py)
- Status: **builds and answers correctly, but scores 0/15** — tool evidence is
  missing. Deliberately kept out of the required CI matrix.

Full debugging notes, including the reproduction command and the four concrete
next steps, live in
[`frameworks/crewai/README.md`](../../frameworks/crewai/README.md).

## The finding: CrewAI does not use native tool calling

This is the comparative fact worth carrying, and it was measured from the request
bodies the mock server actually received:

```
advertised tools : []
stop param       : ['\nObservation:']
```

CrewAI's agent executor advertises **no** OpenAI functions. It drives a **text
ReAct loop**: the prompt ends on a dangling `Thought:`, and it expects the
completion to continue with `Action:` / `Action Input:`, stopping at
`Observation:`. Notably `llm.supports_function_calling()` returns `True` — the
executor simply does not use it.

Anything you write that assumes function-calling semantics — tool-call logging,
parallel tool calls, strict argument schemas — needs rework here.

## What this cost the harness, and what it bought

The original adapter scored 0/15 with `AttributeError: 'list' object has no
attribute 'rstrip'`. Root cause: the mock replayed native `tool_calls` with
`content: None`, CrewAI's parser got a list where it wanted a string, and
`format_message_for_llm` blew up.

Rather than exclude CrewAI on protocol grounds, `arena.llm.mockserver` now renders
each scripted turn **in whichever protocol the client asked for**
(`_looks_like_react` detects a text-ReAct client by the absence of `tools` and an
`Observation` stop sequence). CrewAI therefore faces the *same scripted decisions*
as every other framework. That fixed the crash and the final answers.

This is the methodology working as intended: a framework that speaks a different
protocol is a finding to accommodate, not a reason to drop it from the comparison.

## Still open

The tool-call sink stays empty even though the answers come out right — CrewAI
reaches the second scripted turn without `BaseTool._run` ever firing. Until that
is resolved, every `tool_used` check fails and the mock score is 0/15.

`crewai` therefore stays out of the required `mock-smoke` matrix and out of
Dependabot's update groups: a bump PR against an unverified adapter carries no
signal.

## Gotchas

- **Python 3.11 / 3.12 only.** The transitive tree (chromadb → onnxruntime, numpy)
  has no wheels for 3.14, so it cannot be developed on the same interpreter as the
  rest of this repo. Debugging happens through
  `.github/workflows/crewai-debug.yml` (`workflow_dispatch`).
- **Tool-call history is not exposed.** The adapter wraps each tool in a
  `BaseTool` subclass that records into a sink list. Retries could undercount.
  Reading from CrewAI's event bus instead is one of the open next steps.
- Routes through LiteLLM, so the shared gateway is configured as an
  `openai/<model>` provider.

## Results

| Arena | Mode | Pass rate | Note |
|---|---|--:|---|
| `tool_use` | mock | **0/15** | correct answers, no recorded tool calls |
| everything else | — | not run | out of the CI matrix until the sink works |
