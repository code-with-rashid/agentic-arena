---
title: "OpenHands"
type: repository
status: active
updated: 2026-09-23
tags: [agentic-ecosystem, coding-harness]
---

# OpenHands

Domain: Agentic software development<br>
Source: [Software Agent SDK](https://github.com/OpenHands/software-agent-sdk)<br>
Review depth: **source and selected contracts**<br>
Source checked: 2026-09-23 at `5b36cacccc2bbe6f8fbce9e1d3ff4b0a3dcddadb` (`v1.49.5`)<br>
License at reviewed revision: MIT<br>
Execution by us: **none**.

## Documented direction

The V1 SDK owns agents, tools, conversations, workspaces, events, the Python SDK, Agent Server REST/WebSocket API, and TypeScript client. The application repository consumes those contracts. Workspaces may be local or ephemeral remote environments.

## Proposed relationship to Agentic Arena

Primary complete-harness candidate. Compare its embedded SDK and Agent Server modes separately. Its event-driven loop, conversation persistence, remote workspaces, security analyzer, and confirmation policy are useful references for our independent harness.

## Evidence limits

No local execution or security validation was performed. A remote workspace is not equivalent to a local SDK run, and an action analyzer is not proof of outer containment.

## Review record and next step

Selected SDK architecture, Agent Server, workspace, persistence, pause/resume, and security documentation inspected. Next: run the same fixture through embedded SDK and Agent Server, then compare events and final workspace state independently.

Related: [harness landscape](../research/2026-09-23-coding-harness-landscape.md), [public profile](../../docs/harnesses/openhands.md), [comparison](../../docs/harnesses/comparison.md).
