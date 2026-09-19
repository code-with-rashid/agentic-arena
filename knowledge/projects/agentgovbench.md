---
title: "AgentGovBench"
type: repository
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# AgentGovBench

Domain: Governance evaluation  
Source: [upstream repository](https://github.com/agentic-control-plane/agentgovbench)  
Review depth: **documentation**  
Source checked: 2026-09-18; upstream revision not pinned. Recheck before implementation.  
Execution by us: **none**.

## Documented direction

Describes deterministic governance scenarios for identity, scoped authorization, delegation, rate limits, audit, fail modes, and tenant isolation. Its maintainers also build the reference governance product. [Primary source](https://github.com/agentic-control-plane/agentgovbench).

## Proposed relationship to Agentic Arena

Compare our event schema and scenario boundaries with its runner contract before adding overlapping scenarios. This is our recommendation, not an upstream roadmap commitment.

## Evidence limits

Published reference scores were not independently reproduced. Product-specific integration patterns may influence results; distinguish scope limitations from failures.

## Review record and next step

Repository README and its methodology description were reviewed; runner code has not been audited. Next: inspect the relevant contracts and tests, record an immutable revision, verify license conditions before reuse, and run a bounded reproduction if integration is selected. [Additional source](https://github.com/agentic-control-plane/agentgovbench/blob/main/METHODOLOGY.md).

Related: [ecosystem map](../maps/ecosystem.md), [delivery plan](../strategy/delivery-plan.md), [research backlog](../research/backlog.md).

