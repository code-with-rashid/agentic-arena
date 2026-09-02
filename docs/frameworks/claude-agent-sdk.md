# Claude Agent SDK — deep dive

## At a glance

- Package / repo: [`claude-agent-sdk`](https://github.com/anthropics/claude-agent-sdk-python)
- Adapter: [`frameworks/claude_agent_sdk/adapter.py`](../../frameworks/claude_agent_sdk/adapter.py)
- Status: **deliberate stub.** `build()` raises `NotImplementedError`.

This is the one adapter that is a stub on purpose rather than for lack of time,
and the reason is a methodology constraint rather than a bug. The full write-up,
including three concrete ways a contributor could close it, is in
[`frameworks/claude_agent_sdk/README.md`](../../frameworks/claude_agent_sdk/README.md).

## Why it does not fit

Every other adapter talks to **one** OpenAI-compatible `/chat/completions`
endpoint (`config.base_url`). That single gateway is what lets the stdlib mock
server stand in for a real provider in CI, and what keeps provider-side variables
out of the comparison — see [methodology.md](../methodology.md) §2.

`claude-agent-sdk` is built around a different execution model:

- it spawns the **`claude` CLI (Node.js)** as a subprocess and drives it over a
  local protocol, so a run needs Node installed, not just a Python package;
- it speaks the **Anthropic Messages API** shape, not OpenAI Chat Completions —
  pointing it at `ANTHROPIC_BASE_URL` still expects an Anthropic-shaped server;
- its tool loop, system-prompt handling and token accounting belong to the CLI,
  not to a plain chat client.

So it cannot reach the OpenAI-shaped mock server at all, and in live mode it would
be running a materially different loop from every other entry. Scoring that
alongside the others would break rule 2 of the methodology while looking like a
result.

The package itself installs cleanly on Python 3.14 — the blocker is architectural,
not packaging.

## How it is reported

`build()` raises `NotImplementedError` with a pointer to the adapter README, so
the harness marks it `stub adapter` and it appears as `stub` in the cross-arena
summary — distinct from a failure, from a missing install, and from *unsupported*
(an adapter that runs but lacks a capability the arena needs).

## Closing it

Three routes, in
[`frameworks/claude_agent_sdk/README.md`](../../frameworks/claude_agent_sdk/README.md):
an Anthropic-shaped mock behind a capability flag; a translating proxy such as
LiteLLM (still needs Node in CI); or a direct Messages API adapter — which would
measure the Anthropic *client* rather than the Agent SDK, and should therefore be
named `anthropic_sdk`.

## Results

None, by design. It contributes no items to any arena.
