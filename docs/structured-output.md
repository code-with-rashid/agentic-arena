# Structured output, and what this arena is really testing

## The question

`arenas/structured_output/arena.toml` says, in a comment written before anyone
measured it:

> Adapters ... may use a native structured-output mechanism (`response_format`, a
> Pydantic result type, a tool-as-schema). Which mechanism each one uses is a
> finding for the feature matrix.

Nobody had checked which one each uses. This is that check, and the answer is
short.

## The numbers

Four ways to violate the schema, plus a valid record and a fenced one, scripted
identically for every framework:

| framework | asks the provider? | valid | not JSON | wrong types | missing field | extra field |
|---|---|---|---|---|---|---|
| all seven | **no — prompt only** | unchanged (2) | unchanged (2) | unchanged (2) | unchanged (2) | unchanged (2) |

"unchanged" means the framework returned the model's text byte-for-byte;
the bracketed number is LLM calls.

Regenerate with:

```bash
python .github/scripts/report_structured_output.py
```

## What it says

### Nobody asks the provider for a schema

`response_format` is absent from every request every framework makes — including
`pydantic_ai`, whose stated reason to exist is typed results, and whose adapter
here declares `output_type=str`. All seven ask the model nicely in the system
prompt and take what comes.

That is partly this repo's own doing. The adapters were written to be
*comparable* first, and giving one of them a native schema mechanism while the
others get a prompt would make the arena measure the mechanism rather than the
framework. But it means the row "structured output support" in the feature
matrix has never been earned by anything measured here.

### Nobody validates what comes back

Given a record that is not JSON, or has the wrong types, or is missing a required
field, or carries an extra one, every framework returns it unchanged in exactly
**two** LLM calls — the same two a valid record costs. Nobody re-prompts, nobody
raises, nobody repairs.

Two of those are worth separating. *Not validating* is a defensible default: the
caller may want the raw text. *Not re-prompting* is the one that costs you in
production, because the obvious remedy for a malformed record is to ask again,
and none of these does it for you on this path.

### So the arena grades the model, not the framework

Put those together and the `structured_output` arena, as it stands, is a
`tool_use` arena whose answer happens to be JSON-shaped. Every framework passes
every item, because the mock replays a valid record and every framework hands it
straight through. In a live run it would measure how well *the model* follows a
formatting instruction — a real question, but not the one the arena's description
claims.

The honest statement is: **this arena does not yet discriminate between
frameworks, and the reason is measured rather than assumed.**

### The scorer is the only thing checking

Which makes `arena/scorer.py` load-bearing in a way nothing was pinning. It does
reject all four violations — including the `extra field` case, which a lenient
parser would let through and which the dataset asks about with
`additionalProperties: false`. But if `json_schema` ever stopped validating,
every `structured_output` run would go green and read as seven frameworks with
flawless typed output.

That is now gated in
[`tests/test_structured_output_contract.py`](../tests/test_structured_output_contract.py).

### One deliberate leniency, stated so nobody over-reads the arena

The system prompt says "no prose, no markdown fences". `extract_json` accepts
both — it tries the whole string, then a fenced block, then the first balanced
span. That is the right call for a live run against a real model, and it is
documented in the scorer, but the consequence is worth writing down: the arena
grades whether the record is **extractable and correct**, not whether the model
obeyed the envelope. A framework returning clean JSON earns nothing here over one
that wraps it in chat.

## What is gated, and what is not

Following the same rule as [`resilience`](methodology.md#5-what-mock-mode-does-and-does-not-tell-you)
and [`transport`](transport.md): differences between frameworks are findings,
invariants are gates.

Gated:

- the scorer accepts a valid record and **rejects each of the four violations** —
  the instrument this arena's entire result rests on, and the one nothing else
  covers, precisely because no framework validates;
- the model's answer reaches the scorer **unchanged** — a framework that repaired
  or reformatted JSON would have the arena grading its repair layer while
  reporting the number as the model's output;
- a schema violation **costs no extra model calls**, so cost numbers on this
  arena stay comparable between frameworks that re-prompt and ones that do not;
- the fenced and chatty cases still pass, pinning the leniency above as
  deliberate rather than accidental.

Not gated: that nobody uses a native mechanism. That is a finding, and if it
changes, this page is what needs rewriting.

## Next

Wiring a native mechanism per framework is real work and deliberately not
half-done here — doing it for `pydantic_ai` alone would make the arena
incomparable. Doing it properly means:

1. a second **variant entry** per framework (`pydantic_ai_typed`, and so on),
   the same pattern the `_multi` pipelines use, so the prompt-only entry stays
   as the control;
2. deciding what the mock does when a client sends `response_format` — a real
   provider constrains generation, and a mock that ignores it would make every
   typed entry look identical to its control;
3. a violation-scripted arena, so the difference between "the framework caught
   it" and "the scorer caught it" is visible in a scorecard rather than only in
   a test.

Step 2 is the interesting one and the reason this is not a small change: the
mock would have to *enforce* the schema it was handed, which is the first time it
would be doing something other than replaying a script.
