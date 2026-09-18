# Crash and replay

Status: evidence-backed problem, not a universal framework ranking. Reviewed 2026-09-19 against local tests and published findings; see those pages for the exact dependency pins and measured configurations.

## Symptom and mechanism

After restart, work disappears or a side effect happens twice.

In-memory continuation cannot survive process loss. Persisting before versus after an effect creates different ambiguity windows.

## Diagnose and reproduce

Restart in a fresh interpreter. Inspect checkpoint contents and the effect sink independently.

From the repository root, with the relevant optional adapters installed:

```bash
python -m pytest tests/test_durable_across_a_restart.py -q
```

The [test](../../tests/test_durable_across_a_restart.py) is the executable contract; [published evidence](../arenas/durable_state.md) explains scoped findings. Missing adapters may skip comparisons; inspect the test summary before generalizing.

## Alternatives and tradeoffs

Serializable transcript or native checkpointer; side-effect idempotency in the sink. Neither alone proves distributed exactly-once execution.

## Verification and open question

Crash after sink commit but before acknowledgement. Replay must return the same receipt and not create another effect.

Open question: does the same outcome hold for your actual provider, workload, configuration, and framework version? Existing scripted findings alone cannot answer that.

## Implication for a new harness

Stable operation IDs, durable sink receipts, and explicit unknown-outcome reconciliation.

Return to [the problem register](index.md).


