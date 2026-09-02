# When the gateway fails

## What this measures

Every arena here scripts the **model** doing something — answering, calling a
tool, misbehaving on purpose in `resilience`. None of them scripts the
**provider** failing, and that is the failure real deployments actually hit: a
429 in a burst, a 500 from a proxy, a 400 for a request that was never going to
work.

The mock server takes a `faults` list — one HTTP status per attempt, so
`[429, 429, 200]` fails the first two attempts and serves the third normally. A
faulted attempt never reads the prompt, so it consumes no scripted turn and
appears in `MockServer.attempts` but not in `requests`. The difference between
those two counts *is* the retry behaviour.

Nothing about this needs a real provider, and nothing about it is a property of
the arena. It measures the HTTP layer each framework ships with — which, for
most of them, is the one they inherited from the official OpenAI client.

## The numbers

| framework | healthy | 429 once | 429 ×3 | 500 once | 400 |
|---|---|---|---|---|---|
| `vanilla` (stdlib baseline) | ok (1) | **raises (1)** | raises (1) | **raises (1)** | raises (1) |
| `langgraph` | ok (1) | ok (2) | **raises (2)** | ok (2) | raises (1) |
| `pydantic_ai` | ok (1) | ok (2) | raises (3) | ok (2) | raises (1) |
| `openai_agents` | ok (1) | ok (2) | raises (3) | ok (2) | raises (1) |
| `microsoft_af` | ok (1) | ok (2) | raises (3) | ok (2) | raises (1) |
| `google_adk` | ok (1) | ok (2) | raises (3) | ok (2) | raises (1) |
| `smolagents` | ok (1) | ok (2) | **ok (4, +2–4 min)** | ok (2) | raises (1) |

Bracketed numbers are HTTP attempts that reached the wire, retries included.
Backoff between the first retries is ~0.5 s then ~0.8 s, near-identical
everywhere — five of these libraries are wrapping the same official client.

Regenerate with:

```bash
python .github/scripts/report_transport.py
```

(add `--deep` for the 429 ×3 column, which is slow for the reason below)

## What it says

### This is the clearest answer yet to "what does the framework buy you?"

The hand-rolled stdlib loop has **no retry at all**. One 429 and the item is
lost. Every framework here survives a transient rate limit without the caller
doing anything.

That matters because it is the first dimension in this repo where the baseline
loses outright. On prompt size the hand-rolled loop is
[middle of the pack](overhead.md); on `resilience` it is
[joint best at 8/8](decision-guide.md); on delegation cost it is
[exactly as expensive as a graph library](multi-agent.md). Here it is simply
worse, and no arena could see it, because no arena fails a request.

### Five of six retry twice. LangGraph retries once.

LangGraph gives up a whole attempt earlier than everyone else — 2 attempts where
the others make 3. Against a provider that rate-limits in short bursts, that is
the difference between a blip and a lost item. It is not a bug; it is a default,
and one worth knowing before you rely on it.

### smolagents keeps going, and blocks for over two minutes

It is the only entry that eventually **succeeds** through three consecutive
429s — after sleeping for **minutes** on a single item. Measured three times at
139 s, 160 s and 225 s, so the delay is heavily jittered and the range, not a
point estimate, is the honest number.

Nothing in the scorecard would ever show this. The item *passes*. Pass rate,
correctness, token count: all fine. What you would notice in production is
throughput quietly collapsing while one worker sits in a sleep.

It is the opposite trade-off from everyone else's, and both are defensible:

- **fail fast** (everyone else) — you get the error in ~1.3 s and decide what to
  do about it;
- **keep trying** (smolagents) — the item completes without you writing any
  retry code, and you pay in minutes of latency you did not choose and cannot
  predict.

The second is the wrong default for a batch job and arguably the right one for
an interactive script. Neither is visible from the documentation.

### Everyone refuses to retry a 400

Universal, and correct: a malformed request will be malformed the second time
too. This is the one row that is a **gate** rather than a finding — a library
that started retrying 400s would be burning quota for nothing, and that is
unambiguous enough to fail CI over.

## What is gated, and what is not

Following the same rule as [`resilience`](methodology.md#5-what-mock-mode-does-and-does-not-tell-you):
differences between frameworks are findings, invariants are gates.

Gated in `tests/test_transport_faults.py`:

- a healthy gateway costs exactly **one** attempt (without this, a framework that
  retried constantly would look fine);
- nobody retries a 400;
- one 429 is either survived **or reported** — never answered as though nothing
  happened;
- the baseline still has no retry, pinned, because the whole comparison above
  rests on that control;
- a faulted attempt consumes no scripted turn, which is the instrument checking
  itself: if it did, a retrying framework would be served the *next* turn and
  every row above would be comparing different conversations.

**The 429 ×3 column is deliberately not gated.** Reproducing smolagents' sleep
would add two to four minutes to every CI run to re-measure a number that is
already written down — and being jittered, it is not a number a test could assert
tightly anyway.

## Not measured

- **`Retry-After`.** The mock sends no such header, so every backoff above is the
  client's own choice. A provider that asks for a specific delay might change all
  of these, and the frameworks may not agree on whether to honour it.
- **Timeouts and connection failures.** A hung connection is a different failure
  from a fast 500, and `request_timeout_s` exists in `ArenaConfig` but nothing
  exercises it.
- **Whether retries are counted in reported cost.** A retried attempt that
  reached the provider may still be billed.
  [`tests/test_usage_accounting.py`](../tests/test_usage_accounting.py) holds
  adapters to what the mock *served*, and a faulted attempt is served nothing —
  so this is consistent, but it is not the same question.
