---
profile_type: coding-harness
evidence_status: source-reviewed
evidence_level: source-review
last_verified: 2026-09-23
revalidate_after: 2027-01-21
reviewed_version: "OpenHands Software Agent SDK v1.49.5 at 5b36cac"
best_for: "An embeddable coding-agent SDK paired with remote, long-running workspace services."
owns: "Agents, tools, conversations, events, workspaces, an Agent Server, and client APIs."
important_limit: "Local and remote workspace providers change the evaluated execution and recovery boundary."
evidence_summary: "Pinned source review only; Agentic Arena has not run it locally or with a real model."
---

# OpenHands

OpenHands now separates its application from the OpenHands Software Agent SDK.
The reviewed SDK repository owns agents, tools, conversations, workspaces,
events, a Python SDK, an Agent Server with REST/WebSocket APIs, and a TypeScript
client. The application consumes those contracts.

**Evidence status:** source-reviewed on 2026-09-23 at `5b36cac`
(`v1.49.5`). Agentic Arena has not run it locally.

- [Software Agent SDK](https://github.com/OpenHands/software-agent-sdk)
- [Official SDK architecture](https://docs.openhands.dev/sdk/arch/overview)
- [Agent Server](https://docs.openhands.dev/sdk/arch/agent-server)

## Distinguishing design

The reasoning-action loop is stateless over an event history: it prepares
context, queries the model, validates proposed actions, executes tools, and
appends observations. Conversation services own lifecycle and persistence.
Condensers manage history, while a security analyzer and confirmation policy
can inspect actions before execution.

A caller can embed the Python SDK or operate a long-running Agent Server. The
server exposes conversations, workspace files and commands, and streaming
events. Workspaces can be local or ephemeral remote environments, including
container and cluster-backed configurations. This makes the execution provider
an explicit comparison input.

## What Agentic Arena should test

Use the Python SDK first for a minimal run, then repeat through Agent Server to
measure boundary cost and recovery. Capture events independently and verify
that pause/resume, confirmation, process loss, and workspace cleanup preserve
the same task semantics. Treat local and remote workspace runs as separate
configurations.

OpenHands teaches us to separate an embeddable agent kernel, a remotely
operable workspace service, and user-facing clients. It also shows why an event
history needs explicit ownership: a stateless loop is recoverable only if the
conversation and workspace records agree.
