---
title: "OpenCode"
type: repository
status: active
updated: 2026-09-23
tags: [agentic-ecosystem, coding-harness]
---

# OpenCode

Source: [upstream repository](https://github.com/anomalyco/opencode)<br>
Review depth: **source and selected contracts**<br>
Source checked: 2026-09-23 at `7cb044ee892fa8116610ba31a82922c656eaf86c`; release context `v1.18.32`<br>
License: MIT<br>
Execution by us: **none**.

## Documented direction

Local open-source coding agent with client/server architecture, a headless OpenAPI server, in-process SDK, addressable sessions, tools, skills, MCP, plugins, and named subagents.

## Comparison value

The server exposes create, status, child sessions, diff, fork, abort, summarize, revert, and permission-response operations. Ordered action/resource permissions resolve to allow, ask, or deny. Child agents use their own policies.

## Evidence limits and next step

No local execution. Permission rules control harness actions but do not establish process isolation. V1 and V2 configuration vocabularies differ and must be pinned. Next: exercise causal completion, abort, fork/revert, external-directory denial, and broader child policy through the server SDK.

Related: [landscape research](../research/2026-09-23-coding-harness-landscape.md), [public profile](../../docs/harnesses/opencode.md).
