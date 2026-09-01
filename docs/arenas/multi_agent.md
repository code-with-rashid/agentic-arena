# Arena design: `multi_agent`

## Goal

A three-role pipeline — **researcher → writer → editor** — produces a short brief
on a topic drawn from the shared corpus. Tests how a framework expresses handoffs,
shared context, and role separation, and what that costs in tokens and LLM calls.

## Task

Input: a topic string (e.g. "the Eiffel Tower") plus a required structure:
a 3-sentence brief with (1) what it is, (2) a key date, (3) a key measurement.

- **researcher**: uses `search` to gather facts, emits bullet points.
- **writer**: turns bullets into the 3-sentence brief.
- **editor**: checks the structure and the presence of a date + a number; may send
  it back to the writer once.

## Tools

`search` only. No calculator.

## Scoring (mechanical)

Per item, all must pass:

- `iregex` for a 4-digit year present
- `numeric_equals` (with tolerance) for the expected key measurement
- `icontains` the subject name
- sentence count between 3 and 5 (add a `sentence_count` check type)
- `min_tool_calls` >= 1 (research actually happened)

## Notes / open questions

- Do we require three distinct LLM personas, or allow a single agent that role-plays
  the pipeline? Proposal: require the framework's real multi-agent mechanism; a
  single-agent implementation is a valid *contrast* entry named `<fw>-single`.
- Editor loop bounded to one revision to keep token cost comparable.
- Mock script: 3–4 turns (search → bullets → brief → "approved").
