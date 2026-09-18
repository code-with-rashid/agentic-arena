# Retry amplification

Status: evidence-backed problem, not a universal framework ranking. Reviewed 2026-09-19 against local tests and published findings; see those pages for the exact dependency pins and measured configurations.

## Symptom and mechanism

An intermittent failure turns into minutes of waiting or unexpectedly many requests.

Transport and framework retry layers can multiply attempts. A per-attempt timeout is not a task deadline.

## Diagnose and reproduce

Count requests at the gateway; identify each retry owner and its backoff. Compare timeout versus rate-limit behavior.

From the repository root, with the relevant optional adapters installed:

```bash
python -m pytest tests/test_transport_faults.py -q
```

The [test](../../tests/test_transport_faults.py) is the executable contract; [published evidence](../transport.md) explains scoped findings. Missing adapters may skip comparisons; inspect the test summary before generalizing.

## Alternatives and tradeoffs

One retry owner, shared budget, total deadline, and idempotency for effects. Fail-fast may reduce recovery; longer retries consume throughput.

## Verification and open question

Script 429, 500, nonretryable 400, and a hung response. Test changed timeout values, not one magic duration.

Open question: does the same outcome hold for your actual provider, workload, configuration, and framework version? Existing scripted findings alone cannot answer that.

## Implication for a new harness

Task-wide budget propagated to every retry and explicit cancellation semantics.

Return to [the problem register](index.md).


