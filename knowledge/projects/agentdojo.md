---
title: "AgentDojo"
type: repository
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# AgentDojo

Domain: Prompt injection research  
Source: [upstream repository](https://github.com/ethz-spylab/agentdojo)  
Review depth: **documentation-and-paper-abstract**  
Source checked: 2026-09-18; upstream revision not pinned. Recheck before implementation.  
Execution by us: **none**.

## Documented direction

Provides dynamic tasks for studying prompt-injection attacks and defenses in tool-using agents. [Primary source](https://github.com/ethz-spylab/agentdojo).

## Proposed relationship to Agentic Arena

Keep real-model adversarial robustness as a separate research track; pair legitimate task utility with attacker-goal outcomes. This is our recommendation, not an upstream roadmap commitment.

## Evidence limits

A scripted denial-propagation test cannot establish prompt-injection resistance. Model, defense, attack, and suite versions must be controlled.

## Review record and next step

README and paper abstract were reviewed; no attack suite was run. Next: inspect the relevant contracts and tests, record an immutable revision, verify license conditions before reuse, and run a bounded reproduction if integration is selected. [Additional source](https://arxiv.org/abs/2406.13352).

Related: [ecosystem map](../maps/ecosystem.md), [delivery plan](../strategy/delivery-plan.md), [research backlog](../research/backlog.md).

