# Growing context

Status: evidence-backed problem, not a universal framework ranking. Reviewed 2026-09-19 against local tests and published findings; see those pages for the exact dependency pins and measured configurations.

## Symptom and mechanism

Cost climbs as a task gets longer, even when tool schemas do not change.

Full transcript replay resends earlier messages. Fixed framework prompt overhead and accumulated history are different costs.

## Diagnose and reproduce

Measure request bytes/tokens per turn. Compare the initial intercept with the slope before blaming a framework's fixed prompt.

Use the [context budget explorer](../labs/context-budget.md) to see how replay, recent windows, protected evidence, retrieval, and deterministic compaction change what reaches the model.

From the repository root, with the relevant optional adapters installed:

```bash
python .github/scripts/report_growth.py 30
```

The [test](../../tests/test_prompt_growth.py) is the executable contract; [published evidence](../overhead.md) explains scoped findings. Missing adapters may skip comparisons; inspect the test summary before generalizing.

## Alternatives and tradeoffs

Window old turns, retrieve selected evidence, or summarize; each can discard required obligations or provenance.

## Verification and open question

A required early fact must survive the selected policy; report missing information rather than guessing. Semantic summary quality requires real-model trials.

Open question: does the same outcome hold for your actual provider, workload, configuration, and framework version? Existing scripted findings alone cannot answer that.

## Implication for a new harness

Context builder with explicit budget, retained obligations, source IDs, and observable exclusions.

Return to [the problem register](index.md).

