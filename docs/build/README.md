# Build your own harness

Start with the [developer labs](../labs/index.md) when you want to learn by changing a policy and inspecting the result. Work through tool recovery, context budgets, and approval across restart; then compose those contracts in the [architecture builder](../labs/architecture-builder.md) and test your claims in the [evidence workspace](../labs/evidence-workspace.md).

Continue with [reliability, approval and restart](reliability.md).

The builder exports a versioned decision record for the [design dossier](design-dossier.md). The evidence workspace keeps mock, offline, Codex functional, and live-provider claims distinct before you compare results.

Then compare designs in the [evaluation workbench](evaluation.md), inspect
[boundary response](../arenas/boundary_response.md), choose
[security and operational boundaries](security-operations.md), and use the
[design dossier](design-dossier.md) to plan a separate harness implementation.

1. Read [architecture](../concepts/architecture.md).
2. Run [the model/tool loop](loop.md) and its failure experiments.
3. Explore [context, retrieval, and memory](context.md).
4. Exercise [tool interoperability over MCP](protocols.md).

Start with [architecture](../concepts/architecture.md): a model proposes actions;
the harness owns state, dispatch, authority, budgets, observation, and stopping.

The learning sequence is model boundary → tool loop → context → protocols →
reliability → evaluation → execution/operations. The
[implementation backlog](../../knowledge/strategy/implementation-backlog.md)
tracks each lesson. Examples are educational contracts, not a production SDK.

For existing components, use [Choose](../journeys/choose.md). To interpret a
result, use [Evaluate](../journeys/evaluate.md).
