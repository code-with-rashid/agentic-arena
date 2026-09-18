# Reliability: what survives failure?

Run the offline lesson:

```bash
python -m examples.harness.reliability
pytest tests/test_learning_reliability.py -q
```

The lesson rejects an unapproved booking, then starts a child interpreter that
commits a synthetic booking and dies **before** writing its checkpoint. A fresh
interpreter retries the same operation. An independent SQLite sink contains one
effect, while the client reports a replay. A negative test changes the retry key
and detects two effects. Another checks that rejection must leave zero effects.

## Contracts to choose

| Contract | This lesson | Alternative and cost |
|---|---|---|
| Attempt timeout | Interrupt one cooperative async attempt | Thread/process isolation for uncooperative blocking work costs setup and supervision |
| Task deadline | Bounds all attempts and backoff together | Per-attempt limits alone can multiply total wait |
| Retry policy | Only connection failures/timeouts, bounded attempts | Retrying every error can amplify invalid input and denied actions |
| Cancellation | Propagates cancellation, executes cleanup | Forceful process termination cannot promise application cleanup |
| Approval | Trusted caller supplies approval before dispatch | Bind persisted approval to identity, exact payload, expiry and policy revision in production |
| Checkpoint | Written after sink acknowledgement, atomically replaced | Checkpoint before effect risks falsely declaring completion |
| Idempotency | Sink transaction binds stable operation ID to payload | Client-only deduplication loses knowledge on restart |

The operation key identifies the intended side effect, not an individual model
call or retry. A changed payload with the same key is rejected. The sink owns
deduplication; the harness checkpoint alone cannot close the crash window.

This is a single-machine synthetic service with SQLite transactions. It does not
establish distributed exactly-once delivery, power-loss durability, approval
authentication, or cancellation of a remote effect already in flight. An external
service needs its own idempotency or reconciliation contract. The cancellation
example is deliberately cooperative.

## Connect to measured framework behavior

The existing [approval arena](../arenas/human_in_the_loop.md) measures native
pause/resume; [durable state](../arenas/durable_state.md) tests persistence; and
[transport findings](../transport.md) show how retry defaults differ. Unsupported
resume remains **unsupported**, not a failed execution or a successful rejection.
Use the [restart](../problems/restart.md) and [approval](../problems/approval.md)
problem notes to choose an experiment before choosing a framework.

Implementation: [reliability lesson](../../examples/harness/reliability.py).

