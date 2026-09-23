# DeepSeek Harness

DeepSeek Harness is an experimental, plugin-composed coding harness from
DeepSeek. It is a complete working environment rather than another adapter for
an agent framework. The public repository describes model integration, tools,
sessions, execution, policy, skills, and subagents as replaceable plugins in a
Cordis application tree.

**Evidence status:** source-reviewed on 2026-09-23 at commit `46a7f68`
(`0.1.7-rc.1`). Agentic Arena has not run it against a real model or produced a
local quality, latency, cost, or safety score. The observations below describe
that pinned source; upstream can change.

- [Official repository](https://github.com/deepseek-ai/deepseek-harness)
- [Documentation](https://deepseek-harness.github.io/deepseek-harness/)
- [Safety notice](https://github.com/deepseek-ai/deepseek-harness/blob/46a7f68b0922371ce7144b668b90e377d8e799f4/SAFETY.md)

## How it is assembled

The harness treats the runtime as an ordered plugin tree. Profiles compose a
particular product surface: Web, headless, SDK, minimal SDK, or Agent Client
Protocol. Model adapters, tools, session storage, the agent loop, policy, and
other services can be replaced or patched through that composition.

Its durable center is an append-only session-event log. Model-visible facts are
written there and conversation history is derived from it. Separate live agent
events coordinate streaming, status, and interception. One step contains one
model request plus its tool calls; a turn can contain several steps.

The request path assembles the prompt, applies hooks, freezes the request,
streams a response, runs tool calls through policy and execution, and records
settlements. Tool calls use a bounded parallel pool with exclusive barriers.
Retry scheduling is logged before the wait begins, which makes recovery intent
visible after interruption.

Sessions use generation-versioned JSONL with explicit migrations. A crash can
lose an unsettled assistant stream, while committed events remain. A persisted
tool call without a result is classified as an unknown outcome instead of being
silently replayed. Side-effecting tools therefore need a stable call identifier
and their own idempotency or reconciliation policy.

## Where Agentic Arena can connect

The TypeScript and Python SDKs start a harness runtime as a subprocess and use
newline-delimited JSON-RPC over standard input/output. The high-level client can
submit a prompt, wait for the runtime to become idle, and return the session,
events, notifications, and final response.

The shipped `sdk-minimal` profile is the best experimental boundary. It has a
small explicit composition and supports patches and MCP configuration. It still
advertises a persistent shell by default, omits the full product's approval and
compaction services, and grants that shell every path the subprocess can reach.
It therefore needs a disposable workspace or container before any evaluation.

An executable Arena integration should:

1. pin the runtime and profile;
2. start it inside an isolated fixture workspace;
3. provide the shared task through a controlled patch or MCP server;
4. use one exact model route and nested budgets;
5. capture SDK events plus filesystem and effect observations independently;
6. score final state outside the harness; and
7. report unsupported controls instead of treating them as passes.

This is a new whole-harness runner contract. Adapting it to the existing
`AgentRunner` protocol would hide the prompts, execution environment, and tools
that make the harness meaningful.

## Current limitations that affect comparison

The upstream project labels itself developer-preview software that has not had
a security audit. Its safety notice says sandboxing and approvals reduce risk
but do not guarantee isolation.

The reviewed SDK protocol has no turn-cancel or session-close method. Closing
the runtime process is the available abandonment mechanism. Its prompt receipt
identifies the queued user message rather than a causally matched assistant
result, so a client currently waits for idle and reads the latest root response.
Server-to-client requests are not in use, which leaves interactive approval
flows outside this SDK path. Protocol version negotiation is also absent.

These are test-plan inputs, not automatic disqualifiers. A first run should
measure process cancellation, unknown tool outcomes, stdout corruption from a
plugin, and the difference between the minimal and full SDK profiles.

## What we can learn for a new harness

| Lesson | Design consequence |
|---|---|
| Durable facts and live signals serve different needs | Persist only facts needed for replay and audit; let transient status expire |
| Record intent before a delay or external effect | Recovery can distinguish planned work from an unexplained gap |
| An interrupted tool can have an unknown outcome | Carry stable operation IDs and reconcile before retrying |
| Profiles make composition inspectable | Ship a minimal explicit profile and name every capability added above it |
| Plugin installation expands executable authority | Treat provenance, review, permissions, and updates as security state |
| Child agents need scoped capabilities | Build delegation from explicit context and tool grants rather than copied ambient access |
| Automation protocols need causal completion and cancellation | Give every submitted turn an identity, terminal result, and cancel contract |
| Documentation can be verified like code | Check links, package contracts, generated formats, and profile composition in CI |

These lessons extend the [harness design dossier](../build/design-dossier.md).
They do not require copying DeepSeek Harness's plugin system or implementation
language.
