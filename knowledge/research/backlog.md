---
title: "Research Backlog"
type: backlog
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Research Backlog

The items below are questions to investigate, not verified capabilities or endorsements.

| Priority | Domain | Bounded question | Evidence needed |
|---|---|---|---|
| P0 | Boundary response | Does a denial reach the next model turn, and does allowed work survive? | [Issue #107](https://github.com/code-with-rashid/agentic-arena/issues/107), fixture oracle, three adapters |
| P0 | Existing docs | Which recommendations conflict with newer tests? | Audit [current-state discrepancies](../projects/agentic-arena.md), regenerate relevant findings |
| P1 | Protocols | Do MCP clients preserve errors, schema meaning, cancellation, and identity? | Pinned spec, two clients, contract fixtures |
| P1 | Observability | Are traces complete across tool batches and resume? | Independent event ledger and exporter comparison |
| P1 | Native models | How stable are quality outcomes with a fixed native provider? | Provider credentials, repeated full runs, versioned artifacts |
| P2 | Memory | How do compaction and persistent memory affect cost and leakage between sessions? | Controlled corpus, contamination controls, model/version isolation |
| P2 | Sandboxes | Which configuration was actually enforced during an experiment? | Pinned runtime/config, host evidence, bounded probes |
| P2 | Agent protocols | Is identity retained over remote delegation and cancellation? | A2A contract review and independent endpoints |
| P2 | Coding harnesses | Does a complete harness preserve task, authority, cancellation, and effect evidence under interruption? | Isolated DeepSeek Harness `sdk-minimal` run, then equivalent OpenHands review and shared task |
| P2 | Operations | What survives cancellation, process loss, retries, and duplicate delivery? | Durable queue/idempotency fixtures and reproducible fault plans |
| P3 | Skills and supply chain | How are skill origin, permissions, and updates represented? | Primary manifests, package provenance, independent expectations |
| P3 | Interaction | How do browser/computer-use environments change evaluation? | Dedicated task/observation contract, safe fixture environments |
| P3 | Learning and optimization | How do prompt optimization and agent training avoid evaluation leakage? | Separate train/eval sets, reproducible methods, contamination checks |

Candidate families for later source discovery include local inference/gateways, memory stores, workflow engines, browser automation, retrieval systems, and OpenTelemetry conventions. Do not add product recommendations until primary sources have been reviewed.

Intake question: which developer choice would this investigation change? If no concrete choice or reproducible observation is available, keep it as a research lead rather than adding an implementation milestone.
