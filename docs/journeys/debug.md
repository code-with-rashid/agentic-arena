# Debug reliability and cost

Find the point where intent, execution, and observation diverge.

## Questions to answer

Is the bill caused by retries, history growth, duplicated schemas, or delegation? Did a missing result cause repeated work?

## Start here

Read [transport behavior](../transport.md), [prompt growth](../overhead.md), and [tool schema fidelity](../tool-schemas.md). Compare the actual request/response transcript and tool effects before changing prompts.

Prerequisites: a small task you can describe, its permitted effects, and basic Python for executable examples. Reading the guides needs no API key.

## Evidence and coverage

The existing measurements cover scripted gateway failures and framework mechanics. A general production incident cannot be diagnosed from mock pass rates alone.

Follow [the concept and build path](../build/README.md) for runnable lessons and [the ecosystem map](../ecosystem.md) for wider coverage. Return to [all journeys](../index.md).

