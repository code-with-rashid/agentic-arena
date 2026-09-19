# A minimal model and tool loop

Run from the repository root after installing the harness:

```bash
python -m examples.harness.loop
python -m pytest tests/test_learning_loop.py -q
```

The offline task asks for 17 × 23 + 4. A scripted model emits a calculator call,
then returns the actual tool result supplied in the next request. Expected:
status `completed`, output representing 395, two model calls, one event. The JSON
prints the full synthetic transcript so the call/result ID pair can be followed.

Read [loop.py](../../examples/harness/loop.py) in order: Model contract, scripted
transport, optional native transport, loop state, validation, dispatch, result
append, stopping. Replace `Model.complete` to change providers. Replace the small
registry/schema/dispatch combination to add a tool; preserve validation and IDs.

Malformed/unknown calls produce model-visible errors. Duplicate IDs reject the
whole batch before execution. Step and action budgets stop repeated requests;
exhaustion is a terminal status, not a successful answer. The model can propose
actions but cannot expand the registered tool set.

## Optional native provider

Configure the existing [native gateway variables](../../README.md), including
`ARENA_LLM_MODE=live`, then explicitly run:

```bash
python -m examples.harness.loop --live
```

This can consume provider credits. The example never invokes it by default. The
native transport uses the shared ChatClient; its timeout bounds an attempt. This
lesson does not implement whole-task deadlines, persistence, policy or a process
sandbox. Do not add consequential tools before defining those contracts.

## Failure experiments

Return an unknown name or malformed JSON: check the next model request contains
the error. Emit new call IDs forever: check `exhausted`, not completion. Return
two identical call IDs: verify zero dispatches. Delete the result-append line:
the round-trip test fails. These checks exercise contracts, not answer quality.

Continue through [the learning path](README.md).
