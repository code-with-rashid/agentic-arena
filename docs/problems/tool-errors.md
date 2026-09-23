# Lost tool errors

Status: evidence-backed problem, not a universal framework ranking. Reviewed 2026-09-19 against local tests and published findings; see those pages for the exact dependency pins and measured configurations.

## Symptom and mechanism

The same invalid call repeats, or a final answer silently ignores part of a batch.

A framework may reject before the tool body or omit a failed tool response. A tool-call list alone cannot prove the error reached the model.

## Diagnose and reproduce

Inspect the next model request and independently record which sibling tools ran.

First use the [tool failure and recovery lab](../labs/tool-failure-recovery.md) to see how a structured error returns to the model and where retries do and do not belong.

From the repository root, with the relevant optional adapters installed:

```bash
python -m pytest tests/test_parallel_tool_calls.py -q
```

The [test](../../tests/test_parallel_tool_calls.py) is the executable contract; [published evidence](../findings.md) explains scoped findings. Missing adapters may skip comparisons; inspect the test summary before generalizing.

## Alternatives and tradeoffs

Deliver structured per-call results or fail the batch explicitly. Raising stops work; continuing needs every retained sibling correlated.

## Verification and open question

Inject malformed arguments alongside a successful call. Verify both the error and successful result, not only final output.

Open question: does the same outcome hold for your actual provider, workload, configuration, and framework version? Existing scripted findings alone cannot answer that.

## Implication for a new harness

One terminal response per accepted call and an explicit partial-batch policy.

Return to [the problem register](index.md).

