# `claude_agent_sdk` adapter — still a stub, on purpose

`claude-agent-sdk` installs fine on Python 3.14, but it does not fit the arena
harness the way the other adapters do, and forcing it in would break the
methodology rather than measure anything useful.

## The blocker

Every other adapter talks to **one** OpenAI-compatible `/chat/completions`
endpoint (`config.base_url`). That single gateway is what lets the stdlib mock
server stand in for a real provider in CI, and what keeps provider-side variables
out of the comparison.

`claude-agent-sdk` is built around a different execution model:

- It spawns the **`claude` CLI (Node.js)** as a subprocess and drives it over a
  local protocol — so a run needs Node installed, not just a Python package.
- It speaks the **Anthropic Messages API** shape, not OpenAI Chat Completions.
  Pointing it at `ANTHROPIC_BASE_URL` still expects an Anthropic-shaped server.
- Its tool loop, system-prompt handling, and token accounting are the CLI's, not a
  plain chat client's.

So it can't hit the OpenAI-shaped mock server, and in live mode it would be
running a materially different loop from everyone else.

## Ways a contributor could close this

1. **Anthropic-shaped mock.** Add an `/v1/messages` handler to
   `arena.llm.mockserver` (or a second mock) that replays the same scripted turns
   in Anthropic's format, and gate it behind a capability flag on the adapter.
   Live mode would then require a real Anthropic key.
2. **Translating proxy.** Put LiteLLM (or similar) in front, exposing an
   OpenAI-compatible endpoint that it translates to/from Anthropic. The adapter
   still needs Node for the CLI, so CI would need a Node step.
3. **Direct Messages API adapter.** Skip the SDK's CLI path and use
   `anthropic.Anthropic(base_url=...)` directly. That measures the Anthropic
   client, not the Agent SDK, so it should be named `anthropic_sdk`, not
   `claude_agent_sdk`.

Until one of those lands, `build()` raises `NotImplementedError` with a pointer to
this file.
