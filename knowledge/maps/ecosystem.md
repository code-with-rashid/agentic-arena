---
title: "Ecosystem Map"
type: map
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Ecosystem Map

Follow the development lifecycle. The coverage column describes Agentic Arena today, not the maturity of the wider field.

| Domain | Developer question | Current coverage | Next research or extension |
|---|---|---|---|
| Models and gateways | Which protocol and model does my stack support? | Shared OpenAI-compatible gateway; mock, Codex functional, native live modes | Capability negotiation, streaming, local models, protocol differences |
| Frameworks and orchestration | What does the framework add to my workflow? | Existing framework adapters and comparisons | Boundary handling; close documented adapter gaps |
| Tools and interoperability | Can tools and agents interoperate reliably? | Shared Python tools | [MCP](../projects/mcp.md), [A2A](../projects/a2a.md), schema and error contracts |
| Context, retrieval, and memory | What is retained, retrieved, or forgotten? | Fixed-corpus RAG and prompt-growth measurements | Persistent memory, compaction, retrieval provenance, cross-session contamination |
| Execution and sandboxes | What can code access and change? | No sandbox certification or runtime matrix | [AST](../projects/agent-sandbox-taxonomy.md), [Inspect](../projects/inspect-ai.md), explicit configuration evidence |
| Identity, approvals, and policy | Whose authority permits each action? | HITL and durable pause | [Boundary Response](../initiatives/boundary-response.md); [AgentGovBench](../projects/agentgovbench.md) |
| Security and adversarial behavior | What happens under untrusted input? | Scripted resilience faults | [AgentDojo](../projects/agentdojo.md), [OASB](../projects/oasb.md); utility and security measured separately |
| Evaluations and research | Can a result be independently reproduced? | Frozen datasets, mechanical scorers, repeat runs | [Harbor](../projects/harbor.md), [BoundaryBench](../projects/boundarybench.md), provenance manifests |
| Observability and debugging | Can I explain a failure or bill? | Run records and wire/accounting tests | [Langfuse](../projects/langfuse.md), trace export and event fidelity |
| Coding and interaction harnesses | How does an agent complete real development work? | [DeepSeek Harness](../projects/deepseek-harness.md) source review and separate comparison method | Isolated SDK experiment; [OpenHands](../projects/openhands.md), browser, and computer-use comparison scope |
| Deployment and operations | Can I serve, recover, upgrade, and bound costs? | Restart tests and dependency pins | Queues, concurrency, cancellation, idempotency, SLOs, cost controls |
| Developer experience and supply chain | Can contributors install and safely extend the stack? | Stdlib harness, pinned optional adapters, CI | Skills provenance, packaging, cross-platform recipes, licensing |

## Comparison axes

Keep model, framework, tool contract, execution environment, policy, and task versions explicit. Change one axis per controlled experiment. Compare default configuration and hardened/configured variants as separately named entries.

A reader should navigate **question → domain → project → evidence → recipe → result**. [Catalog](repositories.md) lists initial projects; [backlog](../research/backlog.md) tracks unreviewed areas.
