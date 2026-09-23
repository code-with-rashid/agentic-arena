---
title: "Cline"
type: repository
status: active
updated: 2026-09-23
tags: [agentic-ecosystem, coding-harness]
---

# Cline

Source: [upstream repository](https://github.com/cline/cline)<br>
Review depth: **source and selected contracts**<br>
Source checked: 2026-09-23 at `9c0e4aaee09f6593eb8d06ec4a35bf19b7dc33f1`<br>
License: Apache-2.0<br>
Execution by us: **none**.

## Documented direction

Shared agent core for IDE extensions, CLI, desktop, and Node SDK. The CLI supports headless use; shared features include plan/act modes, MCP, rules, skills, provider configuration, approvals, and checkpoints.

## Comparison value

Current SDK history describes session recovery across aborts/restarts and Git-backed workspace checkpoints. This makes Cline useful for testing conversation recovery and filesystem rewind as separate semantics across IDE and headless hosts.

## Evidence limits and next step

No local execution. Release-note behavior remains an upstream claim until reproduced. Next: interrupt and resume a headless task, then verify checkpoint restore—including created and ignored files—with an independent observer.

Related: [landscape research](../research/2026-09-23-coding-harness-landscape.md), [public profile](../../docs/harnesses/cline.md).
