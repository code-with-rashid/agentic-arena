---
title: "Open Agent Security Benchmark"
type: repository
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Open Agent Security Benchmark

Domain: Security product evaluation  
Source: [upstream repository](https://github.com/opena2a-org/oasb)  
Review depth: **documentation**  
Source checked: 2026-09-18; upstream revision not pinned. Recheck before implementation.  
Execution by us: **none**.

## Documented direction

Describes a capability-aware adapter interface and standardized security scenarios. It documents withdrawals of comparative scanner metrics caused by corpus-labeling bias. [Primary source](https://github.com/opena2a-org/oasb).

## Proposed relationship to Agentic Arena

Adopt explicit applicability and independently labeled expected outcomes. Evaluate third-party detectors only in a separate benchmark track. This is our recommendation, not an upstream roadmap commitment.

## Evidence limits

A detector's own labels cannot supply independent ground truth. Pattern-conformance tests are different from neutral detection-quality comparisons.

## Review record and next step

README including scoring limitations and withdrawal notice was reviewed; no tests were run. Next: inspect the relevant contracts and tests, record an immutable revision, verify license conditions before reuse, and run a bounded reproduction if integration is selected. [Additional source](https://github.com/opena2a-org/oasb/blob/main/BENCHMARK-RESULTS.md).

Related: [ecosystem map](../maps/ecosystem.md), [delivery plan](../strategy/delivery-plan.md), [research backlog](../research/backlog.md).

