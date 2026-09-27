---
title: "Decision 004: One Repository with Bounded Journeys"
type: decision
status: accepted
updated: 2026-09-27
tags: [agentic-ecosystem, repository-design, information-architecture]
---

# Decision 004: One Repository with Bounded Journeys

Date: 2026-09-27. Status: accepted.

## Context and developer need

Agentic Arena contains concept-first education, build-from-scratch material,
framework comparisons, and complete coding-harness comparisons. The concern is
that this breadth could weaken the project's identity and make visitors lose
their way. The maintainer also plans to build a production harness separately.

## Evidence and constraints

[Repository-scope research](../research/2026-09-27-repository-scope.md) found no
useful rule that focused repositories always receive more attention. Both
focused tools and broad platforms succeed when they have a sharp promise,
immediate utility, and predictable navigation. Documentation research supports
separating user needs and progressively revealing detail.

Agentic Arena's current areas share one developer audience, one conceptual
model, one evidence policy, and many cross-cutting examples. Those connections
would be harder to maintain across repositories.

## Decision and rationale

Keep education, framework comparison, coding-harness comparison, developer
labs, and shared reference material in one Agentic Arena repository and public
site.

Treat them as bounded user journeys. The entrance must route visitors by their
goal before exposing the detailed inventory. Frameworks and coding harnesses
remain separate comparison tracks with separate evidence contracts. Their
results may meet in a decision guide, but their score tables must not be merged
as if they were the same kind of system.

Develop the planned production harness in a separate repository. It will have
independent installation, releases, runtime dependencies, security handling,
and product issues. Agentic Arena will treat it as another evaluated harness
without privileged evidence or recommendations.

## Alternatives considered

- **One repository per content area:** provides narrow repository identities but
  duplicates concepts and methodology, fragments navigation, and makes
  cross-cutting changes harder.
- **One undifferentiated ecosystem repository:** preserves breadth but increases
  cognitive load and turns the project into a directory instead of a guided
  developer tool.
- **Education only:** offers a simple promise but discards Agentic Arena's
  differentiator: reproducible evidence connecting concepts to real design and
  product choices.

## Consequences and implementation scope

- Keep the public promise centered on understanding, building, and choosing
  agentic developer systems with reproducible evidence.
- Preserve Learn, Build, Compare, and Reference as distinct content spaces.
- Add a clear framework-versus-harness choice at the start of comparison flows.
- Keep evaluation methods and arenas as shared supporting infrastructure.
- Give every public page one primary user question and one primary navigation
  home.
- Use the repository boundary test from the research note before adding a new
  runtime product or independently released tool.

## Completion criteria

The decision is reflected when a first-time visitor can select a learning,
building, framework-selection, or harness-selection route without understanding
the repository structure first, and when every comparison clearly identifies
whether its subject is a building-block framework or a complete harness.

## Revisit triggers

Reconsider the boundary when independently released components dominate the
repository, CI and checkout costs become material, contributor ownership splits
into independent communities, or user research shows that goal-based routing no
longer prevents confusion.

This decision refines [Decision 001](001-ecosystem-hub.md),
[Decision 002](002-concepts-and-independent-harness.md), and
[Decision 003](003-separate-harness-track.md).

