---
title: "Boundary Response Arena"
type: initiative
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Boundary Response Arena

Status: proposed implementation; tracked in [GitHub issue #107](https://github.com/code-with-rashid/agentic-arena/issues/107). Direction selected on 2026-09-18; no arena code added by this knowledge-base change.

Roadmap update: this is a supporting reliability/security experiment, not the
project's organizing direction or first implementation task. It follows the
knowledge foundation (#108), reliability lessons (#115), and evaluation/event
contracts (#116). See [the ordered backlog](../strategy/implementation-backlog.md).

## Question

When a shared policy denies an action, how does each framework expose the decision, preserve allowed work, and recover within its budget?

## Experimental contract

The common policy and fixture services are controlled inputs. Their correct decisions are harness invariants; measuring them repeatedly is not evidence of a framework's security. Independent fixture effects and model-facing transcripts determine what happened. Framework-native policy hooks, if later compared, must be named configuration variants.

Start with eight scenario families, each paired with an allowed control: protected read, prohibited network destination, synthetic credential access, rejected approval, unavailable policy service, mixed allowed/denied batch, repeated denied action, and permitted alternative. Expand to delegation and resume only after single-agent evidence is sound.

## Observation

Separate model intent, attempted dispatch, policy decision, fixture effect, and model-visible tool response. Use stable run/item/call IDs. Record actor/parent IDs only where the adapter can actually establish them. Never infer an identity chain from tool names alone.

The fixture oracle must observe independently from adapter-reported tool_calls. A shared callback may be useful but cannot alone prove complete mediation across processes or arbitrary code. Test unknown and renamed tool requests as dispatch outcomes; do not claim prevention of filesystem/network bypass from a simulated service.

## Metrics

- Denial delivery and reason fidelity, with a defined eligible-call denominator.
- Allowed-control completion and permitted-recovery completion.
- Policy-service failure behavior and actual prohibited fixture effects.
- Repeated attempts per denied action and call-budget consumption.
- Preservation of allowed results in mixed batches.
- Event completeness and explicitly missing attribution.
- Framework overhead under the same workload.

Report each dimension separately; no combined security score. Unsupported is distinct from failed, not assessed, and harness error. Missing audit evidence cannot count as safe behavior.

## Implementation sequence

1. Freeze versioned fixture/scenario definitions and expected effects.
2. Add structured action observations and preserve them through runner serialization and resume merging.
3. Implement independent recording and mechanical checks.
4. Integrate vanilla, LangGraph, and OpenAI Agents SDK.
5. Prove deliberate defects are detected, then publish a reproducible comparison.
6. Expand adapters, delegation/resume, and real-model trials.

Likely touch points: [types](../../arena/types.py), [runner](../../arena/runner.py), [scorer](../../arena/scorer.py), [shared tools](../../arena/tools/__init__.py), and [registry](../../arena/registry.py). Event schema and injection APIs are still design decisions, not established interfaces.

## Research connection

Use [AST](../projects/agent-sandbox-taxonomy.md) L3-L7/T1/T3/T4/T5 as descriptive tags. Consult [AgentGovBench](../projects/agentgovbench.md) before duplicating governance tests. Keep [AgentDojo](../projects/agentdojo.md) model robustness and [BoundaryBench](../projects/boundarybench.md) full workflow utility as separate experimental questions.
