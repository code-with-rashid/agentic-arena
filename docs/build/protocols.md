# Tools and agent interoperability

A local tool contract specifies name, arguments, result, failure and authority.
A protocol transports that contract across a boundary. The receiving harness
still needs to validate meaning, apply policy, and correlate outcomes.

MCP exposes tools and context to hosts. A2A addresses communication between
agent applications whose internal implementation may remain opaque. These are
different abstraction boundaries, not competing implementations of one loop.
Sources reviewed 2026-09-19: [MCP tools specification, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
and [A2A overview](https://a2a-protocol.org/latest/topics/what-is-a2a/).

## A bounded MCP recipe

```bash
python -m pip install -r examples/mcp/requirements.txt
python -m examples.mcp.recipe
python -m pytest tests/test_learning_mcp.py -q
```

This optional dependency is pinned to [Python SDK v2.2.0](https://github.com/modelcontextprotocol/python-sdk/tree/v2.2.0),
whose tagged source is MIT licensed. No upstream code is vendored. The client
starts an owned stdio subprocess, discovers the tool and schema, compares a
successful call with the same direct fixture, and verifies missing arguments and
a deliberate service failure are returned as errors. It prints the negotiated
protocol version rather than assuming negotiation selected our documentation
version. No provider or credentials are needed. A 20-second scope bounds the
example and the SDK owns child cleanup on exit.

Tool errors are inspected through the result's error flag; a connection failure
raises and makes the command fail. They must not become a fabricated successful
tool result. For this synthetic server stdout is exclusively protocol traffic.

## Contracts to review before adopting a remote tool

| Contract | Question | Recipe coverage |
|---|---|---|
| Discovery/schema | Can the client describe the operation? | Tool name, required key |
| Result | Does direct and remote meaning agree? | One synthetic result |
| Failure | Is rejection distinguishable from success? | Missing input and service error |
| Lifecycle | Who starts and stops the server? | Owned local subprocess |
| Authorization | Which actor can call which resource? | Not assessed; no credentials |
| Cancellation | Does remote work stop, or only the wait? | Not assessed |
| Transport | What changes over HTTP or another client? | Not assessed; stdio only |

The [SDK client documentation](https://py.sdk.modelcontextprotocol.io/client/)
describes typed tool results and supported transports. This recipe establishes
a narrow round trip, not full MCP conformance or equivalent authorization across
clients. The A2A project revision observed was
`afda8316c64951a2ecb2a0d3d10867405d2b4095`; its overview was reviewed but no
A2A implementation was exercised. Next experiments should target cancellation,
identity propagation, and schema changes separately.

Return to [the build path](README.md).
