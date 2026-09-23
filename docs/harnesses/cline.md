# Cline

Cline provides one agent core across its IDE extensions, terminal CLI, desktop
application, and Node SDK. The reviewed CLI supports interactive and headless
operation; the SDK exposes custom tools and agent construction.

**Evidence status:** source-reviewed on 2026-09-23 at `9c0e4aa`. Agentic Arena
has not run it locally.

- [Official repository](https://github.com/cline/cline)
- [CLI source documentation](https://github.com/cline/cline/blob/9c0e4aaee09f6593eb8d06ec4a35bf19b7dc33f1/apps/cli/README.md)
- [SDK and product map](https://github.com/cline/cline/blob/9c0e4aaee09f6593eb8d06ec4a35bf19b7dc33f1/README.md)

## Distinguishing design

Plan/act modes, provider configuration, MCP servers, rules, skills, approvals,
and checkpoints are shared across surfaces. Current SDK release notes describe
durable session context across aborts and host restarts. Git-backed checkpoints
can restore both conversation position and workspace state, including files
created after a checkpoint, while ignored paths are deliberately excluded.

This combination makes Cline useful for studying whether an IDE interaction
model and a headless automation path actually preserve the same semantics.

## What Agentic Arena should test

Run the same task through headless CLI and SDK. Interrupt a turn, restart the
host, and compare transcript state, workspace state, ignored files, and process
cleanup. Test tool rejection and auto-approval as separate configurations. A
checkpoint restore must be scored by an independent filesystem observer rather
than its success response.

Cline teaches us to define workspace rewind separately from conversation
rewind. It also demonstrates the value and cost of maintaining a shared core
across interactive and automated clients.
