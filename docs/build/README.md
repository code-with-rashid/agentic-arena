# Build your own harness

1. Read [architecture](../concepts/architecture.md).
2. Run [the model/tool loop](loop.md) and its failure experiments.
3. Explore [context, retrieval, and memory](context.md).

Start with [architecture](../concepts/architecture.md): a model proposes actions;
the harness owns state, dispatch, authority, budgets, observation, and stopping.

The learning sequence is model boundary → tool loop → context → protocols →
reliability → evaluation → execution/operations. The
[implementation backlog](../../knowledge/strategy/implementation-backlog.md)
tracks each lesson. Examples are educational contracts, not a production SDK.

For existing components, use [Choose](../journeys/choose.md). To interpret a
result, use [Evaluate](../journeys/evaluate.md).
