---
hide:
  - toc
---

# Context budget explorer

Choose a context policy and character budget. The explorer shows exactly which source records reach the model, what is omitted, and whether an obligation or correction disappeared. The fixed workload keeps the comparison about selection policy rather than model behavior.

<div class="context-lab" data-context-lab>
  <div class="context-lab__controls" aria-label="Context explorer controls">
    <label><span>Selection policy</span><select data-context-policy><option value="full">Full transcript</option><option value="recent">Recent window</option><option value="protected" selected>Required + recent</option><option value="retrieval">Required + retrieval</option><option value="summary">Deterministic compaction</option></select></label>
    <label><span>Budget: <strong data-context-budget-value>220</strong> characters</span><input data-context-budget type="range" min="40" max="420" step="10" value="220"></label>
    <label><span>Retrieval query</span><select data-context-query><option value="database" selected>database</option><option value="migration">migration</option><option value="health">health</option><option value="approval">approval</option></select></label>
  </div>
  <div class="context-lab__workspace">
    <div><span class="context-lab__label">Candidate sources · oldest to newest</span><ol data-context-sources></ol></div>
    <div class="context-lab__model"><span class="context-lab__label">What the model receives</span><div class="context-lab__meter"><span data-context-meter></span></div><div class="context-lab__metric"><strong data-context-used></strong><span data-context-outcome></span></div><pre data-context-text></pre></div>
  </div>
  <p class="context-lab__lesson" data-context-lesson aria-live="polite"></p>
</div>

## Read the result as a harness contract

- **Full transcript** preserves the records but can exceed the request budget. A budget that is not enforced is only a dashboard value.
- **Recent window** is cheap and deterministic, but an early approval or constraint can disappear while the prompt still looks valid.
- **Required + recent** keeps explicit obligations first and fills remaining space with recent evidence. If required evidence cannot fit, it fails visibly.
- **Required + retrieval** limits candidates by a query and retains source IDs. Retrieval relevance does not establish authority or truth.
- **Deterministic compaction** demonstrates the space tradeoff without claiming semantic summary quality. The summary is labeled as a new record because its source-level provenance has collapsed.

This explorer budgets characters rather than provider tokens. Tokenization depends on the provider and encoding; use actual request usage for cost claims.

## Produce the same selection locally

```bash
python -m examples.harness.context_lab --policy protected --budget 220
python -m examples.harness.context_lab --policy recent --budget 170
pytest tests/test_context_lab.py tests/test_learning_context.py -q
```

The command emits versioned JSON containing selected and omitted source IDs, missing obligations, used characters, outcome, and rendered context. The underlying [context lesson](../build/context.md) also verifies durable memory isolation by tenant and session.

## Compare growth separately

The repository's prompt-growth experiment measures bytes and estimated tokens across repeated turns. It answers how request cost grows; this lab answers which evidence a context builder chooses to retain.

```bash
python .github/scripts/report_growth.py 30
```

Read the [prompt-growth evidence](../overhead.md#what-happens-when-the-loop-gets-long) and the [growing-context problem note](../problems/context-growth.md). Mock token estimates are useful for controlled structure, not provider billing.

Next: [Context, retrieval, and memory](../build/context.md) · [Build your own harness](../build/README.md)
