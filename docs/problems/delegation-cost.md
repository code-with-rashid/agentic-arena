# Delegation overhead and ownership

Status: evidence-backed problem, not a universal framework ranking. Reviewed 2026-09-19 against local tests and published findings; see those pages for the exact dependency pins and measured configurations.

## Symptom and mechanism

A multi-agent workflow costs more even when it produces the same answer.

Delegation can advertise schemas repeatedly, copy context, or add model turns. Orchestration shape changes the bill.

## Diagnose and reproduce

Separate calls for handoff, worker execution, context forwarding, and task tools.

From the repository root, with the relevant optional adapters installed:

```bash
python -m pytest tests/test_delegation_depth.py tests/test_delegation_forwarding.py -q
```

The [test](../../tests/test_delegation_depth.py) is the executable contract; [published evidence](../multi-agent.md) explains scoped findings. Missing adapters may skip comparisons; inspect the test summary before generalizing.

## Alternatives and tradeoffs

Use a single loop when roles add no verified benefit. Isolated workers reduce context sharing but can duplicate calls.

## Verification and open question

Hold task and scripted responses fixed; vary depth and forwarded evidence while measuring the wire.

Open question: does the same outcome hold for your actual provider, workload, configuration, and framework version? Existing scripted findings alone cannot answer that.

## Implication for a new harness

Parent task/actor IDs, propagated budgets, and explicit ownership of worker failure.

Return to [the problem register](index.md).


