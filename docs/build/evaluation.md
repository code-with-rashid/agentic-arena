# Evaluation and observability

```bash
python -m examples.harness.evaluate --output runs/learning/retry-comparison.json
pytest tests/test_learning_evidence.py -q
```

Both variants face the same synthetic lost acknowledgement. A stable operation
key yields one booking; a fresh key on retry yields two. The scorer reads the sink,
not the client's success claim. Both complete useful work, but only one meets
the exact-effect contract. This is a deterministic mechanics experiment, not a
model benchmark or statistical reliability estimate.

## Evidence contract

[arena.evidence/v1](../../arena/evidence.py) records run, item, call, actor,
optional parent/delegation IDs, event kind and value. Kinds separate **attempt**,
**decision** (including reason), **effect**, **response** visible to a model,
**error**, and **usage**. Unknown provenance stays null rather than invented.
A synthetic lesson may have no model; its response events are service responses.

Artifacts include command, commit, tracked-change indicator, explicit configuration,
repetitions, Python version, source/dataset/scorer SHA-256 identities, mode and
exclusions. The embedded fixture configuration is the dataset; its defining
source is hashed. Hashes identify bytes, not authenticity. Do not export secrets,
private prompts or credentials; these examples contain synthetic data only.

Completeness compares expected calls to trace entries and independently read
effects to reported effects. Tests deliberately remove an event and invent an
effect. A perfect trace cannot prove coverage of actions outside the instrumented
service. The [boundary arena](../arenas/boundary_response.md) extends this contract
to independent model-wire and fixture observations.

| Axis | Question | Evidence |
|---|---|---|
| Correctness | Is the result/effect exactly what was requested? | Independent oracle |
| Useful work | Did permitted work finish? | Allowed controls, separate from denials |
| Cost | What resources were consumed? | Provider usage, or explicitly labelled estimates |
| Latency | What wall time elapsed? | Local clock, environment and repetitions |
| Reliability | Does behavior persist across faults/repeats? | Fault plan and denominator |
| Safety | Which forbidden effects occurred within scope? | Boundary-specific observations |

Never collapse these into a single security score. Offline/mock mechanics,
subscription functional checks, and native API outcomes have distinct mode values.
No model tokens or price are fabricated for this fixture.

## Where existing tools fit

Primary documentation reviewed **2026-09-19**; this is documentation evidence,
not executed integrations or comparative findings:

| Tool | Question it helps answer | Boundary of our review |
|---|---|---|
| [Inspect](https://inspect.aisi.org.uk/) | How do I compose datasets, solvers, scorers and evaluation logs? | Evaluation infrastructure; sandbox choice remains separate |
| [Harbor](https://docs.harborframework.com/) | How do I package and run agent tasks in environments? | Task/environment infrastructure, not a universal harness ranking |
| [AgentDojo](https://github.com/ethz-spylab/agentdojo) | How do agents behave under prompt-injection attacks and defenses? | Specific attack/task setting; model behavior matters |
| [OASB](https://github.com/opena2a-org/oasb) | How do I exercise security scenarios through an adapter? | Check capabilities, scoring and target scope before interpreting totals |
| [Langfuse](https://langfuse.com/docs) | How do I inspect traces and evaluation observations? | Optional observability; instrumentation alone cannot prove containment |

Our recommendation is to export only after local completeness checks pass.
A future OpenTelemetry/export adapter should preserve IDs, null/missing evidence,
mode, source hashes and separate metrics, support redaction, and round-trip without
dropping events. No hosted service or exporter is required or implemented.

