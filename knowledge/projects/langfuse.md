---
title: "Langfuse"
type: repository
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Langfuse

Domain: Observability and evaluations  
Source: [upstream repository](https://github.com/langfuse/langfuse)  
Review depth: **overview**  
Source checked: 2026-09-18; upstream revision not pinned. Recheck before implementation.  
Execution by us: **none**.

## Documented direction

Presents an open-source platform for tracing, evaluation, and improvement of LLM applications. [Primary source](https://github.com/langfuse/langfuse).

## Proposed relationship to Agentic Arena

Investigate optional trace export and compare trace completeness against the harness's independent records. This is our recommendation, not an upstream roadmap commitment.

## Evidence limits

Tracing SDK presence does not prove complete evidence. Export must redact sensitive fields and record dropped events.

## Review record and next step

Repository overview inspected; SDK/export contracts remain to be reviewed. Next: inspect the relevant contracts and tests, record an immutable revision, verify license conditions before reuse, and run a bounded reproduction if integration is selected. [Additional source](https://github.com/langfuse/langfuse).

Related: [ecosystem map](../maps/ecosystem.md), [delivery plan](../strategy/delivery-plan.md), [research backlog](../research/backlog.md).

