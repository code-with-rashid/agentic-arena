---
type: reference
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Ordered Implementation Backlog

The roadmap was merged in [PR #120](https://github.com/code-with-rashid/agentic-arena/pull/120),
deployed to the [public field guide](https://code-with-rashid.github.io/agentic-arena/),
and its issues were closed on 2026-09-19. See the
[2026-09-19 evidence record](../research/2026-09-19-implementation.md) and
[build path](../../docs/build/README.md). The GitHub tracker remains authoritative
for future work. Optional runtime verification is stated separately.

[Roadmap issue #119](https://github.com/code-with-rashid/agentic-arena/issues/119) is the public tracker. All issues were open when created. Check GitHub for current state; this note is not a separate completion ledger.

| Order | Issue | Outcome |
|---|---|---|
| 01 | [#108](https://github.com/code-with-rashid/agentic-arena/issues/108) | Establish the concept-first ecosystem charter and portable knowledge foundation |
| 02 | [#109](https://github.com/code-with-rashid/agentic-arena/issues/109) | Build a problem-oriented front door and ecosystem coverage map |
| 03 | [#110](https://github.com/code-with-rashid/agentic-arena/issues/110) | Write the framework-neutral agent and harness architecture guide |
| 04 | [#111](https://github.com/code-with-rashid/agentic-arena/issues/111) | Add an executable build-your-own-harness lesson for the model and tool loop |
| 05 | [#112](https://github.com/code-with-rashid/agentic-arena/issues/112) | Create an evidence-backed problem register and troubleshooting playbooks |
| 06 | [#113](https://github.com/code-with-rashid/agentic-arena/issues/113) | Add context, retrieval, and memory design lessons with controlled fixtures |
| 07 | [#114](https://github.com/code-with-rashid/agentic-arena/issues/114) | Document tool and agent interoperability and add a bounded MCP contract recipe |
| 08 | [#115](https://github.com/code-with-rashid/agentic-arena/issues/115) | Teach durable execution, approvals, retries, and cancellation with fault examples |
| 09 | [#116](https://github.com/code-with-rashid/agentic-arena/issues/116) | Add an evaluation and observability workbench for harness developers |
| 10 | [#117](https://github.com/code-with-rashid/agentic-arena/issues/117) | Add execution, security, and deployment decision guides with a local recipe |
| 11 | [#118](https://github.com/code-with-rashid/agentic-arena/issues/118) | Synthesize a framework-neutral harness design dossier for a separate implementation |

Insert [#107](https://github.com/code-with-rashid/agentic-arena/issues/107) after #116 and before expanding security comparisons. It depends on #108, #115, and #116.

## Dependencies

- #108 → #109 → #110 → #111.
- #112 depends on #109 and #110.
- #113 depends on #111 and #112.
- #114 depends on #111.
- #115 and #116 depend on #111 and #112.
- #117 depends on #115 and #116.
- #118 depends on #113, #114, #115, #116, and #117; it can list #107 findings as pending.

The order expresses preference; independent work can proceed once its dependencies land. Avoid simultaneous changes to shared contracts/navigation without coordination.

## Agent handoff

> Implement issue #108 in code-with-rashid/agentic-arena. Read its full body and dependencies, verify their status, and work from current main on a dedicated branch. Complete the scoped deliverables, update docs and knowledge notes, run appropriate checks, and open a PR with evidence and limitations. Preserve unrelated work. Do not merge automatically. Complete independent offline work when optional credentials are unavailable.

Replace #108 with the next ready issue. Issue bodies are self-contained for a clean checkout; the unpublished local vault is optional input.

These issues establish foundations. Later topics include interaction, optimization/training, skills supply chain, local inference, and distributed operations. See [the ecosystem map](../maps/ecosystem.md) and [research backlog](../research/backlog.md).
