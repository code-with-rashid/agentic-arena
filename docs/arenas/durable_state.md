# Arena design: `durable_state`

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
