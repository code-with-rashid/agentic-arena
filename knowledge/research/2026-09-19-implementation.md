---
type: experiment
updated: 2026-09-19
tags: [agentic-ecosystem, implementation, evidence]
---

# Roadmap implementation: 2026-09-19

## Direction retained

Agentic Arena is a concept-first ecosystem field guide and practical lab.
The production harness remains a separate future repository. Concepts,
alternatives, failure modes and acceptance experiments come before product names.
Coverage gaps remain visible; this milestone does not cover every future topic.

## Implementation map

| Issues | Artifact | Evidence class |
|---|---|---|
| #108–110 | [Charter](../strategy/vision.md), [journeys](../../docs/ecosystem.md), [architecture](../../docs/concepts/architecture.md) | Design and inspected local implementation |
| #111 | [Loop lesson](../../docs/build/loop.md) | Offline execution with deliberately malformed calls and bounded loops |
| #112 | [Problem register](../../docs/problems/index.md) | Links to existing repository experiments; scoped diagnoses |
| #113 | [Context/memory](../../docs/build/context.md) | Budget, required-fact, scope-isolation and fresh-process tests |
| #114 | [MCP recipe](../../docs/build/protocols.md) | Executed stdio discovery/success/invalid/service-error round trip, SDK 2.2.0, protocol 2026-07-28 |
| #115 | [Reliability](../../docs/build/reliability.md) | Actual child-process crash after sink commit; fresh-process replay; cancellation/deadline cleanup |
| #116 | [Evaluation](../../docs/build/evaluation.md) | Independent sink comparison; corrupted trace and false effect detected |
| #107 | [Boundary response](../../docs/arenas/boundary_response.md) | 16 mock cases each through vanilla, LangGraph 1.2.11 and OpenAI Agents 0.22.0 |
| #117 | [Security/operations](../../docs/build/security-operations.md) | Container recipe passed in Linux CI, including effective limits and teardown; local Docker startup unavailable |
| #118 | [Design dossier](../../docs/build/design-dossier.md) | Proposed contracts, alternatives and acceptance experiments; no production runtime |

Dependencies are implemented as ordered commits on one review branch,
`codex/ecosystem-field-guide`, rather than separately merged prerequisite PRs.
Issues remain open until the work is accepted and merged.

Review: [PR #120](https://github.com/code-with-rashid/agentic-arena/pull/120).
The final end-to-end command used two repetitions and generated the standard
scorecard with separate boundary dimensions: **96/96 item runs passed**,
32/32 per adapter, 20/20 propagated denials and 28/28 permitted effects per
adapter. Verdicts were stable across both repetitions. This verifies repeat
isolation and report generation, not statistical model quality.

## Verification record

Local environment: Windows, Python 3.14.7. The full existing regression suite
(excluding documentation in that invocation) passed with optional adapter skips.
Documentation link/reachability checks and strict MkDocs build passed separately.
All eight arena definitions validated. The boundary matrix passed 48/48 item runs;
negative tests detect dropped denials, missing policy events, forbidden effects
and blanket refusal. These are mock mechanics, not model quality.

The local Docker CLI was installed, but startup/info commands did not complete.
The waiting client processes were stopped. This is an environment limitation,
not a passing containment result. The opt-in recipe passed in
[Linux CI run 35425706375](https://github.com/code-with-rashid/agentic-arena/actions/runs/35425706375).
Docker 28.0.4 observed UID 65534, zero effective capabilities, no-new-privileges,
128 MiB memory, 32 processes, 0.5 CPU, only loopback, a read-only root, a permitted
temporary write and successful teardown. Image digest:
`python@sha256:64259673bf7dc32a42821929e59682f6cfda0341f0a5345af35d209db236940e`.
This is a scoped runtime observation, not certification.

No paid/native model calls were made for this milestone. Real-model recovery,
delegation boundary provenance, distributed leases, production identity,
adversarial sandbox testing and trace exports remain explicitly unassessed.

## Research refresh

Primary documentation for Inspect, Harbor, AgentDojo, OASB and Langfuse was
rechecked on 2026-09-19 for the [evaluation tool map](../../docs/build/evaluation.md).
This is documentation-level evidence; no upstream integration was executed.
MCP alone was integrated at a pinned SDK version. A2A remains conceptual.
Docker runtime/reference documentation and AST vocabulary were rechecked for
the security guide. No external scoring or certification is inherited.

## Personal learning route

Open this repository's `knowledge/` folder as an Obsidian vault. Start with
[the build path](../../docs/build/README.md), then reflect in the ignored
`knowledge/personal/` folder. Keep private plans and subjective preferences
there; update public experiment notes only with reproducible, non-sensitive
evidence. [Maintenance](../operations/maintenance.md) defines the update loop.
