# Approval that does not enforce

Status: evidence-backed problem, not a universal framework ranking. Reviewed 2026-09-19 against local tests and published findings; see those pages for the exact dependency pins and measured configurations.

## Symptom and mechanism

The trace reports an approval request but execution can still happen before a decision.

Reporting a pause and preventing an action are distinct mechanisms. Tool policy must bind the actual pending operation.

## Diagnose and reproduce

Record the actual fixture side effect before and after suspension; deliberately ignore advisory signals.

Use the [approval and restart clinic](../labs/approval-restart.md) to compare advisory and enforced pauses, then inject a crash on either side of the effect.

From the repository root, with the relevant optional adapters installed:

```bash
python -m pytest tests/test_suspend_resume.py -q
```

The [test](../../tests/test_suspend_resume.py) is the executable contract; [published evidence](../arenas/human_in_the_loop.md) explains scoped findings. Missing adapters may skip comparisons; inspect the test summary before generalizing.

## Alternatives and tradeoffs

Gate execution and resume from a durable decision record. Binding approval to an action digest prevents accidental reuse for changed arguments.

## Verification and open question

Reject and approve paired cases; verify zero effects before approval and no effect after rejection.

Open question: does the same outcome hold for your actual provider, workload, configuration, and framework version? Existing scripted findings alone cannot answer that.

## Implication for a new harness

Authorization bound to identity and immutable operation, checked immediately before effect.

Return to [the problem register](index.md).

