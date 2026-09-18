# Problem register

Start with the symptom, reproduce it, then select a remedy. These entries connect
existing framework evidence to portable harness requirements. Results apply to the
published configurations, not every version or use of a library.

- [Growing context](context-growth.md): Cost climbs as a task gets longer, even when tool schemas do not change.
- [Lost tool errors](tool-errors.md): The same invalid call repeats, or a final answer silently ignores part of a batch.
- [Retry amplification](retry-amplification.md): An intermittent failure turns into minutes of waiting or unexpectedly many requests.
- [Approval that does not enforce](approval.md): The trace reports an approval request but execution can still happen before a decision.
- [Crash and replay](restart.md): After restart, work disappears or a side effect happens twice.
- [Delegation overhead and ownership](delegation-cost.md): A multi-agent workflow costs more even when it produces the same answer.

## Worked investigation: a costly repeating loop

1. Capture request count and tool-call IDs at the model boundary. Do not begin with prompt tuning.
2. If requests repeat with identical context, check [error delivery](tool-errors.md). A model cannot correct an error it never sees.
3. If requests multiply during gateway failures, inspect [retry ownership](retry-amplification.md) and distinguish attempt timeout from task deadline.
4. If each request grows, measure [context accumulation](context-growth.md); separate its slope from constant schema/prompt overhead.
5. If roles multiply the bill, account for [delegation](delegation-cost.md), including copied context and advertised schemas.
6. Change one design variable and rerun the same fixture. Check useful task completion as well as lower cost.

A correction is successful only when the original failure is absent and allowed
work still completes. Report configuration, model mode, versions, missing adapter
coverage, and side effects. Never translate a synthetic token estimate into an
unqualified production bill.

New entries should contain symptom, minimal reproducer, affected configuration,
evidence, alternatives, uncertainty, and an acceptance experiment. See
[the experiment template](../../knowledge/templates/experiment.md).


