---
title: "Decision 001: Ecosystem Hub with Focused Evaluations"
type: decision
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Decision 001: Ecosystem Hub with Focused Evaluations

Date: 2026-09-18. Status: refined by [Decision 002](002-concepts-and-independent-harness.md); retained as historical context.

## Context

The user wants one open-source reference spanning agentic development and research, usable in Obsidian and any coding harness. Agentic Arena already has a controlled framework comparison core.

## Decision

Keep a Markdown knowledge vault in the repository, organized around developer questions and lifecycle domains. Broaden curated coverage immediately, and add executable capabilities in bounded milestones. Begin with [Boundary Response](../initiatives/boundary-response.md).

## Alternatives considered

- A standalone personal vault: convenient privately, but separates shared research from implementation review.
- Rebuild every ecosystem component: a very large maintenance burden and weak differentiation.
- An unannotated repository list: broad coverage without evidence or decision support.
- Immediately adopt a large evaluation platform as mandatory core: potentially useful infrastructure, but adds migration cost before a concrete need.

## Consequences

Relative Markdown links and YAML properties support Obsidian, GitHub, and file-reading harnesses. Existing result/docs files remain authoritative, limiting drift. Additional domains require explicit review states. External benchmark adapters remain optional until a bounded experiment justifies them.

## Revisit when

Multiple contributors cannot maintain freshness; cross-repo knowledge needs exceed this vault; reproducible runtime integration outgrows the current harness; or users need generated search/navigation. See [delivery plan](../strategy/delivery-plan.md).
