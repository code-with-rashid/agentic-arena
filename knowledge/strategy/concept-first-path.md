---
type: reference
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Concepts and the Build-Your-Own-Harness Path

Organize around engineering problems and concepts. Existing providers, frameworks, and harnesses illustrate implementations; none defines the curriculum.

Two valid paths share the same foundation:

- Assemble: requirements → choose components → integrate → evaluate → operate.
- Build: contracts → minimal loop → add needed capabilities → test failures → compare alternatives → operate.

## Learning sequence

| Concept | Understand and implement | Verify |
|---|---|---|
| Model boundary | Replaceable transport, messages, usage, protocol differences | Request/response preservation |
| Agent loop | State transitions, stopping, budgets | Completion and repeated-call limits |
| Tools | Registry, schema, errors, direct/remote dispatch | Actual effects and error delivery |
| Context | Transcript, retrieval, persistent memory, compaction | Provenance and session separation |
| Reliability | Retry, cancellation, checkpoint, idempotency | No duplicate or premature effects |
| Policy and execution | Authority, approval, isolation | Paired allowed/denied controls |
| Delegation | Ownership, identity, context transfer | Attribution and inherited budgets |
| Evaluation | Independent oracles, useful work, overhead | Deliberate defects detected |
| Operations | Concurrency, deployment, cleanup, resources | Recovery and enforced limits |

For every topic: problem → mechanics → minimal design → alternatives/tradeoffs → failures → verification → sourced implementation examples.

## Future harness

Research → problem register → candidate designs → separate implementation → controlled experiments → generalizable findings back here.

Keep production implementation in the future repository. Keep educational examples here small and replaceable. The future harness receives identical evidence and comparison standards, including publication of failures. [Issue #118](https://github.com/code-with-rashid/agentic-arena/issues/118) creates a design dossier, not the new repository or production runtime.

## Personal learning

Record what I understand, what I can reproduce, what remains unclear, and which design choices need experiments. Use [personal notes](../personal/README.md), alongside [the ordered backlog](implementation-backlog.md).
