# Choose a stack

Translate requirements into experimental questions.

## Choose the system boundary first

Do you need building blocks for an application you will design, or a complete
coding environment around the model?

| Decision | Start with |
|---|---|
| I need orchestration, tools, state, approvals, or delegation APIs inside my application | [Frameworks and SDKs](../frameworks/README.md) |
| I need a coding agent that already owns prompts, tools, execution, permissions, persistence, and interaction | [Coding agents and harnesses](../harnesses/README.md) |

Do not combine them in one ranking. A harness owns many variables that the
framework experiment deliberately holds fixed. The
[comparison gateway](../compare/index.md) explains the boundary.

## Start here

Write down provider/protocol, tool access, approvals, durability, latency and
budget requirements. For frameworks, read the
[decision guide](../decision-guide.md) and [feature matrix](../feature-matrix.md).
For complete environments, use the
[coding-harness matrix](../harnesses/comparison.md). Check the
[profile evidence label](../reference/profile-evidence.md), inspect the
[methodology](../methodology.md), and reproduce the relevant arena before
choosing.

Prerequisites: a small task you can describe, its permitted effects, and basic Python for executable examples. Reading the guides needs no API key.

## Evidence and coverage

Existing offline comparisons establish mechanics. Native provider answer-quality rankings remain unavailable until repeated live scorecards are published.

Follow [the concept and build path](../build/README.md) for runnable lessons and [the ecosystem map](../ecosystem.md) for wider coverage. Return to [all journeys](../index.md).
