# Context, retrieval, and memory

State is what the runtime needs to continue. Context is what the model receives
on one request. Memory is information selected for retention across requests or
sessions. Retrieval chooses evidence; it does not make that evidence authoritative.

```bash
python -m examples.harness.context
python -m pytest tests/test_learning_context.py -q
```

The [example](../../examples/harness/context.py) stores synthetic facts in SQLite
under tenant and session keys, reconstructs the store, retrieves evidence, and
builds a bounded context with source IDs. Tests reopen it in another interpreter
and attempt cross-session/tenant retrieval. The demo prints only Alice's fact,
with source `manual-1`; Bob's fact must not appear.

## Choose a context policy

| Policy | Useful when | Tradeoff and verification |
|---|---|---|
| Full transcript | Short tasks need exact history | Cost grows; inspect the wire, including schemas |
| Recent window | Old details are dispensable | Can lose approvals/constraints; retain obligations explicitly |
| Summary | History is large and semantic compression helps | Can alter facts; evaluate with real models and original evidence |
| Selective retrieval | Relevant evidence can be identified | Retrieval can miss facts; track source IDs and absence |
| Persistent memory | Future work needs selected facts | Needs isolation, expiry, correction, and consent/authority rules |

This example budgets **characters**, not tokens, and selects standalone facts,
not raw tool-message history. A production transcript window must preserve valid
tool request/result pairs. Required evidence is selected first; if it cannot fit,
the builder fails visibly. Omitted source IDs are reported. The tests do not
establish semantic summary quality or real-model retrieval accuracy.

The store assumes tenant/session values came from trusted request context. Passing
model-supplied tenant IDs to it would defeat isolation. Storage persistence is not
an authentication system, and the demo's SQLite lifecycle is not a distributed
memory service.

Use [prompt-growth evidence](../overhead.md) to understand costs and the
[RAG arena](../arenas/rag.md) for fixed-corpus task mechanics. Extend this lesson
with an early required fact, irrelevant recent evidence, a corrected source, and
two users with identical search terms. Track what is omitted and why.

Return to [the build path](README.md).
