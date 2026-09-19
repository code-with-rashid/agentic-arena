---
title: "Agentic Arena: Current State"
type: project
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Agentic Arena: Current State

## Identity and evidence

[Upstream](https://github.com/code-with-rashid/agentic-arena) compares agent frameworks with shared tasks, tools, and a model gateway. The local source snapshot reviewed was `1bfb5c6`. [PR #106](https://github.com/code-with-rashid/agentic-arena/pull/106) was confirmed merged on 2026-09-17; local checkout may not equal the latest main commit.

Authoritative references: [README](../../README.md), [methodology](../../docs/methodology.md), [findings](../../docs/findings.md), [feature matrix](../../docs/feature-matrix.md), [roadmap](../../ROADMAP.md), [adapter contract](../../arena/types.py), and [runner](../../arena/runner.py).

## Implemented capabilities

The original seven arenas cover tool use, structured output, resilience, RAG, multi-agent, human approval, and durable state. The eighth, [boundary response](../../docs/arenas/boundary_response.md), adds paired synthetic controls across three adapters. Shared tools and mechanical scorers constrain comparisons. Seven main adapters, a code-agent contrast, and five pipeline variants have documented mock coverage; support varies by arena. Consult the feature matrix for exact cells.

Three evidence modes: deterministic mock mechanics; Codex subscription-backed real-model functional checks; native API live comparisons. The repository has no committed native API answer-quality scorecard as of the reviewed snapshot.

## Recent validation

The prior development session reported 468 passing offline tests and 74 skips, plus green PR CI. Real-model functional trials included a clean 15/15 vanilla tool-use run and selected structured-output, RAG, HITL, and durability items. A multi-agent item returned correct facts but failed sentence-count requirements. These are a session summary, not a new independently reproduced run; generated artifacts remain local under ignored runs/. The PR records the scope.

## Important gaps

- First reproducible native API comparison still needs an actual provider setup.
- CrewAI tool-call evidence and the Claude SDK protocol mismatch remain documented gaps.
- No sandbox provider matrix, MCP/A2A conformance suite, production operations suite, or security certification exists.
- Some prose summaries predate later findings. For example, README's older resilience bullet conflicts with its current 8/8 smolagents summary; the decision guide's exclusive durable-pause language predates the five-adapter result. Resolve against tests and evidence before repeating such claims.

## Direction

[Vision](../strategy/vision.md) broadens the reference scope around concepts and
developer problems. The next implementation task is the portable knowledge
foundation in issue #108, followed by navigation and conceptual guides.
[Boundary Response](../initiatives/boundary-response.md) follows the reliability
and evaluation foundations. The [delivery plan](../strategy/delivery-plan.md)
separates knowledge coverage from measured capability.
