---
title: "Inspect AI and Sandboxing Toolkit"
type: repository
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Inspect AI and Sandboxing Toolkit

Domain: Evaluation infrastructure  
Source: [upstream repository](https://github.com/UKGovernmentBEIS/inspect_ai)  
Review depth: **documentation**  
Source checked: 2026-09-18; upstream revision not pinned. Recheck before implementation.  
Execution by us: **none**.

## Documented direction

Provides extensible model evaluations and sandbox environments. Related AISI tooling covers Docker, Kubernetes, and VM-based execution. [Primary source](https://github.com/UKGovernmentBEIS/inspect_ai).

## Proposed relationship to Agentic Arena

Investigate a result export or optional task integration once our event/provenance schema stabilizes. This is our recommendation, not an upstream roadmap commitment.

## Evidence limits

Adding Inspect as mandatory runtime infrastructure would change the lightweight harness. Sandbox provider assumptions and configuration must be evaluated independently.

## Review record and next step

README, sandbox docs, and toolkit/provider overviews were reviewed; no integration was executed. Next: inspect the relevant contracts and tests, record an immutable revision, verify license conditions before reuse, and run a bounded reproduction if integration is selected. [Additional source](https://inspect.aisi.org.uk/sandboxing.html).

Related: [ecosystem map](../maps/ecosystem.md), [delivery plan](../strategy/delivery-plan.md), [research backlog](../research/backlog.md).

