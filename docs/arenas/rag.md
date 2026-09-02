# Arena design: `rag`

## Status

Shipped as `arenas/rag/` — 15 items: 9 single-hop, 3 multi-hop, 3 unanswerable.
All five verified adapters score 15/15 in mock mode.

Two decisions differ from the draft below:

- **No `retrieve` tool was added.** The shared `search` tool already does
  deterministic lexical retrieval over the corpus and takes a `k`. Adding a
  second retrieval tool would have broken the "hold the tools constant" rule in
  `docs/methodology.md` §3 for no measurement gain.
- **No `answer_from_passages` check type.** The unanswerable items achieve the
  same thing more cheaply: each pairs a refusal `iregex` with a `not_contains`
  on the *real-world* answer, so an agent leaning on the model's parametric
  memory fails even though its answer is factually correct. `not_contains`
  already existed.

## Goal

Agentic retrieval over a fixed local corpus: the agent decides when to retrieve,
with what query, and how many hops. Tests retrieval integration and multi-hop
reasoning, not embedding quality (the retriever is fixed and shared).

## Corpus & retriever

`arena/tools/corpus.json` — 27 short passages, three of which already carry the
cross-references the multi-hop items need (fact A in passage 1 names entity B
whose fact is in passage 2). The retriever is lexical token overlap, already
implemented in `arena.tools.search(query, k=3)` and shared with every other
arena. Deterministic, and identical for every framework.

Growing the corpus is worthwhile but is a separate change: it shifts what
`search` returns for the *other* arenas too, so it needs its own PR and a
re-check of every mock script.

## Task

~20 questions:

- single-hop lookups
- multi-hop ("What is the summit height of the mountain first climbed in 1953?")
- unanswerable-from-corpus (correct behaviour: say so; do not hallucinate)

## Scoring (mechanical) — as shipped

| item kind | checks |
|---|---|
| single-hop | `numeric_equals` on the gold figure, `min_tool_calls` >= 1 |
| multi-hop | `numeric_equals` on the gold figure, `icontains` the bridging entity, `min_tool_calls` >= 2 |
| unanswerable | `iregex` refusal phrase, `not_contains` the real-world answer, `min_tool_calls` >= 1 |

The multi-hop chains ride on cross-references already in the corpus: Tokyo Tower
→ Eiffel Tower, Taipei 101 → Burj Khalifa, Chrysler Building → Empire State
Building. The `icontains` on the bridging entity is what makes the item a
genuine two-hop question rather than a lucky guess.

## Notes

- No `calculator`.
- Mock script keys on question fragments; multi-hop items script two `search`
  turns (with *different* queries — a test asserts this) then the answer.
- `tests/test_rag_arena.py` scores a deliberately hallucinated answer against
  each unanswerable item and asserts it fails on the `not_contains` trap, so the
  grounding check can never quietly become vacuous.
