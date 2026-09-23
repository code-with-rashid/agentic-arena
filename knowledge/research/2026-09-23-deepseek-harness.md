---
title: "DeepSeek Harness Source Review"
type: research
status: complete
updated: 2026-09-23
tags: [agentic-ecosystem, coding-harness, deepseek]
---

# DeepSeek Harness source review

Question: should DeepSeek Harness appear in Agentic Arena, and which ideas should inform a future independent harness?

## Decision

Yes, as the first reviewed **complete coding harness**. It should not appear as one more framework adapter. Whole harnesses change prompts, tools, execution, permissions, storage, and interaction, so their evaluation needs a dedicated contract and independent final-state scoring.

Reviewed upstream commit: `46a7f68b0922371ce7144b668b90e377d8e799f4`, version `0.1.7-rc.1`, checked 2026-09-23. No runtime or model execution was performed.

## Sources inspected

- Root README, package manifest, license, safety notice, contributing and architecture documentation.
- Agent lifecycle and event/session contracts.
- SDK protocol, TypeScript client, Python SDK, SDK server, and `sdk-minimal` bundle.
- Model, tool, policy, retry, persistence, subagent, skill, MCP, and bundle packages plus selected tests.

The reviewed tree contains 316 package manifests. That number describes repository shape at the pinned revision, not product maturity.

## Findings that change our design

1. **Persistence vocabulary matters.** DeepSeek Harness separates durable session facts from ephemeral coordination. Our harness contract should say which events can rebuild model-visible history and which exist only for live UI or control.
2. **Settled and unknown are different.** A tool invocation can survive without its outcome. Recovery must reconcile a stable operation ID rather than assume failure and repeat the effect.
3. **Retry state belongs before the clock.** Recording a scheduled retry before sleeping makes interruption explainable and prevents a hidden attempt after restart.
4. **Profiles are auditable experiments.** A minimal profile makes every added capability visible. Arena should record the complete resolved profile rather than only a product name.
5. **Extensibility is authority.** An in-process plugin can read or modify anything the host process can. Plugin source, version, integrity, review, capabilities, and updates belong in the security model.
6. **Delegation should narrow context and tools.** Fresh subagents demonstrate a useful default: explicit work context and scoped tools, with a small result returned to the parent.
7. **Automation needs causal semantics.** A durable enqueue receipt plus global idle is insufficient for concurrent evaluation. Our future protocol should correlate submission, events, terminal result, usage, cancellation, and reconciliation.
8. **The outer sandbox remains necessary.** A permission preset inside a harness cannot protect resources already available to the process. Evaluation must record host/container isolation independently.

## Integration assessment

The SDK is the supported machine boundary. `sdk-minimal` reduces product services and exposes a patch/MCP seam, but its default persistent shell has broad process-level access. A credible experiment therefore needs an isolated workspace, exact profile and patch capture, fixed model settings and budgets, and observations outside the SDK event stream.

The existing Arena `AgentRunner` intentionally shares model, tools, and task semantics among frameworks. Forcing a complete harness through it would remove or conceal what the harness contributes. The new track should instead define a `HarnessRun` record containing task revision, runtime image, authority, harness profile, model route, budgets, events, filesystem diff, effects, outcome, and limitations.

## Claims we are not making

- No answer-quality, latency, token, cost, safety, or reliability comparison has been run.
- Source structure does not prove containment or production readiness.
- A large package and test surface does not establish user experience or correctness.
- Our proposed comparison track is not an upstream DeepSeek roadmap.

## Follow-up

The next bounded step is the isolated `sdk-minimal` experiment described in the [project profile](../projects/deepseek-harness.md). Its result should update the [public harness profile](../../docs/harnesses/deepseek-harness.md) and the [design dossier](../../docs/build/design-dossier.md), whether it passes or fails.
