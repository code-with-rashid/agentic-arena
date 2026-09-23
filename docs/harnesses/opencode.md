# OpenCode

OpenCode is an open-source coding agent organized around a local client/server
architecture. Its headless server exposes OpenAPI operations for sessions,
messages, status, permissions, diffs, forks, abort, and revert. Its SDK can use
that network surface or host the server router inside an application.

**Evidence status:** source-reviewed on 2026-09-23 at `7cb044e`; latest release
context checked as `v1.18.32`. Agentic Arena has not run it locally.

- [Official repository](https://github.com/anomalyco/opencode)
- [Server API](https://opencode.ai/docs/server)
- [Permissions](https://opencode.ai/v2/docs/permissions)
- [In-process SDK](https://opencode.ai/v2/docs/build/sdk)

## Distinguishing design

Sessions are first-class addressable resources. The API exposes child sessions,
status, todos, diffs, fork, abort, summarize, revert, and permission responses.
That is a stronger automation contract than waiting for a whole process to
become idle.

Permissions are ordered action/resource rules with `allow`, `ask`, or `deny`
effects. They cover reads, edits, shell commands, external directories, skills,
and subagent launches. Child agents use their own configured policies; parent
launch permission does not automatically narrow child authority.

## What Agentic Arena should test

Drive a run through the server or in-process SDK and retain session events plus
an independent repository diff. Test concurrent prompts, abort, fork/revert,
permission denial, external-directory access, and a child whose own policy is
broader than the parent's. Record the exact V1 or V2 configuration schema because
their permission vocabulary differs.

OpenCode teaches us that a useful automation API gives submitted work causal
identity and explicit lifecycle operations. Its ordered policy model is also a
good test case for rule precedence and for the distinction between tool policy
and process containment.
