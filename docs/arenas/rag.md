# Arena design: `rag`

## Goal

Agentic retrieval over a fixed local corpus: the agent decides when to retrieve,
with what query, and how many hops. Tests retrieval integration and multi-hop
reasoning, not embedding quality (the retriever is fixed and shared).

## Corpus & retriever

Reuse and expand `arena/tools/corpus.json` to ~40 short passages with some
multi-hop chains (fact A in passage 1 points to entity B whose fact is in passage
2). The retriever is BM25-ish lexical overlap (already implemented in
`arena.tools.search`) exposed as a `retrieve(query, k)` tool. Deterministic.

## Task

~20 questions:

- single-hop lookups
- multi-hop ("What is the summit height of the mountain first climbed in 1953?")
- unanswerable-from-corpus (correct behaviour: say so; do not hallucinate)

## Scoring (mechanical)

- `contains` / `numeric_equals` for the gold answer
- for unanswerable items: `iregex` for a refusal phrase AND `no fabricated number`
  (a `not_contains` check type)
- `min_tool_calls` >= 2 for multi-hop items

## Notes

- No `calculator`.
- Mock script keys on question fragments; multi-hop items script two `retrieve`
  turns then the answer.
- Add check types: `not_contains`, and maybe `answer_from_passages` (answer tokens
  must overlap retrieved text) to catch parametric-memory answers.
