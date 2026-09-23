---
title: "Developer Workbench"
type: initiative
status: active
updated: 2026-09-23
tags: [agentic-ecosystem, developer-experience, learning]
---

# Developer Workbench

Status: tracked in [issue #127](https://github.com/code-with-rashid/agentic-arena/issues/127). Implemented slices: [tool failure and recovery](../../docs/labs/tool-failure-recovery.md) and the [context budget explorer](../../docs/labs/context-budget.md).

## Purpose

Turn the repository from a reading collection into a place where developers can predict behavior, change a harness policy, inspect the resulting event sequence, reproduce it locally, and reuse the contract in their own implementation. The workbench remains framework-neutral; product comparisons are a later evidence layer.

## Reusable learning loop

1. Orient around a concrete developer problem.
2. Predict the outcome before seeing it.
3. Change one policy while holding the workload fixed.
4. Inspect attempts, effects, events, and the stop reason.
5. Run a deterministic local fixture.
6. Compare frameworks only after the contract is understood.
7. Export the contract into a harness design dossier or evaluation.

## Delivery order

1. Tool failure and recovery: malformed calls, retry classification, lost acknowledgements, idempotency, and reconciliation.
2. Context budget explorer: observe growth, compaction, retrieval, and information loss.
3. Approval and restart clinic: pause, persist, resume, reject, and verify zero unauthorized effects.
4. Harness architecture builder: compose loop, state, tools, boundaries, evaluation, and operations into a design dossier.
5. Evidence workspace: save comparable run manifests and framework findings without mixing measured facts with design guidance.

## Evidence rule

Every browser interaction must state whether it is an explanation, deterministic simulation, offline executable fixture, real-model functional check, or live provider benchmark. A polished visualization never upgrades the strength of the evidence behind it.

## Maintenance

New labs should use the same control → prediction → timeline → local command structure. Each lab needs a deterministic executable module, focused tests for its central contract, links into Learn/Build/Problems, and a statement of what the result cannot prove.
