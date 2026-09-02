# Arena design: `multi_agent`

## Status

Shipped as `arenas/multi_agent/` — 10 items over landmarks in the shared corpus.
The eval is shape-based, so the current single-agent adapters role-play the
pipeline and all score 10/10 in mock mode. What is **not** yet built: entries that
use a framework's real multi-agent mechanism (a graph, a crew, handoffs). Those
land as separate `<fw>-multi` adapter entries and are compared to the single-agent
run on tokens and LLM calls — the cost of the abstraction is the finding.

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

- `iregex` `\b<year>\b` — the correct completion/opening year is present
- `numeric_equals` (with tolerance 1) — the expected key measurement is present
- `icontains` the subject name
- `sentence_count` `min 3, max 5` — the brief is a brief, not an essay or a fragment
- `min_tool_calls` >= 1 — research actually happened

`sentence_count` was added to `arena/scorer.py` for this arena: it splits on
`.!?`, ignores a period between two digits (a decimal point), and counts spans
that contain a letter.

## Notes / open questions

- Do we require three distinct LLM personas, or allow a single agent that role-plays
  the pipeline? Proposal: require the framework's real multi-agent mechanism; a
  single-agent implementation is a valid *contrast* entry named `<fw>-single`.
- Editor loop bounded to one revision to keep token cost comparable.
- Mock script: 3–4 turns (search → bullets → brief → "approved").
