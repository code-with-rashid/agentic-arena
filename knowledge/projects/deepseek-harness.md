---
title: "DeepSeek Harness"
type: repository
status: active
updated: 2026-09-23
tags: [agentic-ecosystem, coding-harness, deepseek]
---

# DeepSeek Harness

Domain: Coding and interaction harnesses  
Source: [upstream repository](https://github.com/deepseek-ai/deepseek-harness)  
Review depth: **source and selected contracts**  
Source checked: 2026-09-23 at `46a7f68b0922371ce7144b668b90e377d8e799f4` (`0.1.7-rc.1`)  
License at reviewed revision: MIT  
Execution by us: **none**.

## Documented direction

An experimental developer-preview coding harness built from replaceable Cordis plugins. Profiles compose model adapters, agent loop, tools, policy, execution, session persistence, skills, subagents, user interfaces, and SDK serving. The TypeScript and Python SDKs drive a runtime subprocess over newline-delimited JSON-RPC.

Primary sources: [repository](https://github.com/deepseek-ai/deepseek-harness), [agent lifecycle](https://github.com/deepseek-ai/deepseek-harness/blob/46a7f68b0922371ce7144b668b90e377d8e799f4/docs/agent-lifecycle.md), [SDK protocol](https://github.com/deepseek-ai/deepseek-harness/blob/46a7f68b0922371ce7144b668b90e377d8e799f4/packages/sdk/protocol/README.md), [safety](https://github.com/deepseek-ai/deepseek-harness/blob/46a7f68b0922371ce7144b668b90e377d8e799f4/SAFETY.md).

## Architecture observations

- An append-only `SessionEvent` log is canonical durable state; live `agent/*` events coordinate the running process.
- A request is frozen after prompt and request hooks. Tool calls pass through a bounded parallel pipeline with exclusive barriers.
- Retry scheduling is persisted before waiting.
- JSONL session generations have explicit migrations.
- A persisted tool call without a result is an unknown outcome. The docs recommend forwarding the call ID as an idempotency key for side effects.
- Fresh in-process subagents start without the parent's transcript and return their final output. Their tools are selected by composition.
- Skills are discovered from providers and exposed through a model-facing loader.
- Third-party plugins run in-process, so installation changes the trusted computing base.

## Proposed relationship to Agentic Arena

Use it as the first source-reviewed entry in a complete coding-harness comparison track. Do not add it to framework overhead results: it owns prompts, tools, execution, state, policy, and orchestration that current framework comparisons hold shared.

The `sdk-minimal` profile is the narrowest later integration surface. Run it only in an isolated fixture workspace, configure shared capabilities through a controlled patch or MCP server, and score final repository state independently.

## Evidence limits

No local install, model run, security probe, or benchmark was performed. Upstream marks the software experimental, unaudited, and not production-ready. The reviewed SDK lacks turn cancellation, causal prompt-result matching, active server-to-client approval requests, and protocol-version negotiation.

## Next experiment

Build a disposable repository task with objective tests. Pin the runtime and model, run `sdk-minimal` in a container, record configuration and SDK events, terminate it during a side effect, and independently inspect final files and effect IDs. Compare default and restricted configurations as separate conditions.

Related: [source review](../research/2026-09-23-deepseek-harness.md), [ecosystem map](../maps/ecosystem.md), [harness-track decision](../decisions/003-separate-harness-track.md), [public profile](../../docs/harnesses/deepseek-harness.md).
