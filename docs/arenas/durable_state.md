# Arena design: `durable_state`

## Status

Shipped as `arenas/durable_state/` — 8 items. Five adapters score 8/8 across a
real process restart (`tests/test_durable_across_a_restart.py` runs the two legs
in two interpreters): `langgraph` and `google_adk` keep an on-disk sqlite store,
`openai_agents` serialises the whole run, `pydantic_ai` and `vanilla` serialise
the transcript. `microsoft_af` pauses but reports *unsupported* here — its
`AgentSession` store does not survive a JSON round trip — and `smolagents` has no
`resume` at all. What the pause costs in bytes, per mechanism, is in
[findings.md §4](../findings.md#4-pausing-and-surviving-a-crash).

Two decisions differ from the draft below:

- **No process is actually killed.** `arena.toml` sets `durable = true`, and the
  harness JSON round-trips `resume_state` and then **discards the runner and
  builds a new one**. That reproduces what matters about a crash — nothing in
  memory survives, and no live reference can be handed across — without the
  complexity of a real subprocess. An adapter that tries to smuggle a live object
  through gets a clear error rather than a pass.
- **`vanilla` is not `n/a`.** It serialises the whole transcript into
  `resume_state`, which crosses the gap intact. Stateless resume is a legitimate
  way to be durable, so it scores 8/8 — but it is not a checkpointer, and the
  feature matrix keeps the two apart.

`call_counts` is what makes the arena real: an adapter patched to restart from
scratch still reaches the right answer, and still drops from 8/8 to **0/8**,
because it redoes both lookups.

## Goal

A multi-step task is interrupted mid-run (simulated crash); a fresh process must
resume from a checkpoint and finish without repeating completed, side-effecting
steps. Tests checkpointing / persistence support.

## Task

A 4-step "data gathering" job: `search` fact 1 → `search` fact 2 → `calculator`
combine → write final answer. The harness kills the runner after step 2 completes
(detected via a step-logging tool), then rebuilds the agent pointed at the same
checkpoint store and calls `resume(item, checkpoint_id)`.

## Scoring (mechanical)

- final answer correct (`numeric_equals`)
- each side-effecting tool call appears exactly once across the pre-crash and
  post-resume segments (no duplicate `search`/`calculator` calls) — needs a
  `call_counts` check over the merged trace
- resume used the checkpoint (framework reports it, or step log shows steps 1–2
  were not re-executed)

## Notes

- Checkpoint store: a temp dir / sqlite file the harness controls, passed via
  `config`. Add `config.checkpoint_dir`.
- `vanilla` has no persistence → expected `n/a` unless a contributor adds a manual
  JSON checkpoint (contrast row).
- LangGraph's `checkpointer` is the reference implementation to design the harness
  API against.
