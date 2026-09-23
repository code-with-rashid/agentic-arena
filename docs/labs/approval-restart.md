---
hide:
  - toc
---

# Approval and restart clinic

Change the decision, enforcement, persistence, and crash point. The clinic separates a reported approval request from actual dispatch control, then uses an independent effect count to verify what happened across restart.

<div class="failure-lab" data-approval-lab>
  <div class="failure-lab__controls" aria-label="Approval clinic controls">
    <label><span>Decision</span><select data-approval-decision><option value="approve" selected>Approve</option><option value="deny">Deny</option></select></label>
    <label><span>Crash point</span><select data-approval-crash><option value="none">No crash</option><option value="after_pause">After pause</option><option value="after_effect" selected>After effect, before checkpoint</option></select></label>
    <label class="failure-lab__check"><input data-approval-gated type="checkbox" checked><span>Gate dispatch on approval</span></label>
    <label class="failure-lab__check"><input data-approval-durable type="checkbox" checked><span>Persist resume state</span></label>
    <label class="failure-lab__check"><input data-approval-stable type="checkbox" checked><span>Reuse operation identity</span></label>
  </div>
  <div class="failure-lab__result">
    <div class="failure-lab__summary"><div><span>Outcome</span><strong data-approval-outcome></strong></div><div><span>Restarts</span><strong data-approval-restarts></strong></div><div><span>Effects</span><strong data-approval-effects></strong></div></div>
    <ol class="failure-lab__timeline" data-approval-timeline></ol>
  </div>
</div>

## Read the result as three separate contracts

1. **Authorization:** a pause must gate the actual dispatch. An advisory callback can report a request after work has already happened.
2. **Durability:** pending operation, decision, and resume state must cross a process boundary as serializable data. Keeping a live runner in memory is not restart recovery.
3. **Effect safety:** a crash after commit but before checkpoint creates an unknown outcome. Stable operation identity prevents replay from becoming a second effect.

The trusted caller supplies the decision in this fixture. A production approval must also bind approver identity, exact operation and arguments, expiry, and policy revision.

## Produce the same run locally

```bash
python -m examples.harness.approval_lab --decision approve --crash after_effect --gated --durable --stable-operation
python -m examples.harness.approval_lab --decision deny --crash none --no-gated
pytest tests/test_approval_lab.py tests/test_learning_reliability.py -q
```

Then run the repository's framework-neutral behavior checks:

```bash
python -m pytest tests/test_suspend_resume.py tests/test_durable_state.py -q
```

The `human_in_the_loop` arena measures pause-before-effect and approved/denied outcomes. The `durable_state` arena discards the runner, JSON round-trips resume state, builds a fresh runner, and fails correct answers that repeated earlier tool work.

Read [human approval evidence](../arenas/human_in_the_loop.md), [durable-state evidence](../arenas/durable_state.md), and the [restart problem note](../problems/restart.md).

Next: [Reliability and restart](../build/reliability.md) · [Developer labs](index.md)
