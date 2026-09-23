---
title: "Separate Complete Harness Comparisons"
type: decision
status: accepted
updated: 2026-09-23
tags: [agentic-ecosystem, evaluation, coding-harness]
---

# Separate complete harness comparisons

## Context

Agentic Arena's framework adapters share model transport, tools, datasets, and scoring to isolate framework behavior. Complete coding harnesses also own prompts, tools, execution, permissions, storage, user interaction, and orchestration. Treating one as a framework adapter would either discard its defining behavior or give it incomparable advantages.

## Decision

Maintain a separate coding-harness comparison track. Hold the task repository, exact model, runtime policy, authority, and budgets fixed where possible. Record each harness's resolved profile, prompts, tools, and execution behavior as part of the evaluated system. Score final state and external effects with an independent observer.

Profiles begin with source review. Numerical or behavioral claims require a pinned, repeatable run. Default and hardened configurations are distinct entries.

## Consequences

- Framework tables remain interpretable.
- Harness differences remain visible instead of being normalized away.
- The comparison runner needs a broader record than `AgentRunner`.
- Some controls will be unsupported by a harness; the result must record that state rather than infer success.
- The same contract can later compare our independent harness without privileged prompts or scoring.

First application: [DeepSeek Harness](../projects/deepseek-harness.md).
