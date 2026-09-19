---
title: "Agent Sandbox Taxonomy"
type: repository
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Agent Sandbox Taxonomy

Domain: Sandbox classification and probing  
Source: [upstream repository](https://github.com/kajogo777/the-agent-sandbox-taxonomy)  
Review depth: **documentation-and-selected-artifacts**  
Source checked: 2026-09-18; upstream revision not pinned. Recheck before implementation.  
Execution by us: **none**.

## Documented direction

Defines seven defense layers, seven threat categories, and strength/granularity/portability dimensions. The repository also contains product metadata and a Go probe. [Primary source](https://github.com/kajogo777/the-agent-sandbox-taxonomy).

## Proposed relationship to Agentic Arena

Use layer/threat vocabulary as descriptive metadata and examine externally generated probe reports as optional environment evidence. This is our recommendation, not an upstream roadmap commitment.

## Evidence limits

Product ratings can depend on documentation and configuration choices. The probe documents limits in external audit visibility and derives threat coverage from layer scores. Passing a probe is not a proof of isolation.

## Review record and next step

README, products.yaml, probe/README, and contribution guidance were inspected through web sources; no binary was executed. Next: inspect the relevant contracts and tests, record an immutable revision, verify license conditions before reuse, and run a bounded reproduction if integration is selected. [Additional source](https://github.com/kajogo777/the-agent-sandbox-taxonomy/tree/main/probe).

Related: [ecosystem map](../maps/ecosystem.md), [delivery plan](../strategy/delivery-plan.md), [research backlog](../research/backlog.md).

