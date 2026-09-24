---
hide:
  - toc
---

# Evidence workspace

Start with a claim, then compare two run manifests. The workspace tells you whether the evidence mode can support the claim and whether both runs share the controls required for a direct comparison.

<div class="evidence-lab" data-evidence-lab>
  <div class="evidence-lab__claim">
    <label><span>Claim to evaluate</span><select data-evidence-claim><option value="wiring">The integration is wired correctly</option><option value="recovery" selected>The recovery contract holds</option><option value="real_model">A real model completes the path</option><option value="provider_comparison">Framework/provider performance differs</option></select></label>
    <label><span>Shared dataset</span><select data-evidence-dataset><option value="developer-workbench/v1" selected>developer-workbench/v1</option><option value="tool-recovery/v1">tool-recovery/v1</option></select></label>
    <label><span>Shared scorer</span><select data-evidence-scorer><option value="contract-check/v1" selected>contract-check/v1</option><option value="independent-effects/v1">independent-effects/v1</option></select></label>
  </div>
  <div class="evidence-lab__runs">
    <fieldset><legend>Run A</legend><label><span>Mode</span><select data-evidence-a-mode><option value="mock">Mock</option><option value="offline-fixture" selected>Offline fixture</option><option value="codex">Codex functional</option><option value="live">Live provider</option></select></label><label><span>Model</span><input data-evidence-a-model value="fixed-responder"></label><label><span>Repetitions</span><input data-evidence-a-repetitions type="number" min="1" value="1"></label><div class="evidence-lab__support" data-evidence-a-support></div></fieldset>
    <fieldset><legend>Run B</legend><label><span>Mode</span><select data-evidence-b-mode><option value="mock">Mock</option><option value="offline-fixture" selected>Offline fixture</option><option value="codex">Codex functional</option><option value="live">Live provider</option></select></label><label><span>Model</span><input data-evidence-b-model value="fixed-responder"></label><label><span>Repetitions</span><input data-evidence-b-repetitions type="number" min="1" value="1"></label><div class="evidence-lab__support" data-evidence-b-support></div></fieldset>
  </div>
  <div class="evidence-lab__comparison"><div><span class="workbench-label">Comparison verdict</span><strong data-evidence-verdict></strong><p data-evidence-reason></p></div><ul data-evidence-fields></ul></div>
  <details class="evidence-lab__record"><summary>Inspect the versioned records</summary><pre data-evidence-record></pre><div class="workbench-actions"><button type="button" data-evidence-copy>Copy records</button><button type="button" data-evidence-download>Download</button><button type="button" data-evidence-share>Copy share link</button></div><p data-evidence-action role="status" aria-live="polite"></p></details>
</div>

## Read the verdict carefully

- **Mock** establishes wiring and mechanics under fixed responses.
- **Offline fixture** establishes a local contract under controlled faults and an independent oracle.
- **Codex functional** exercises a real model through the subscription bridge. Translation prevents native latency, token, and cost comparisons.
- **Live provider** can support provider and framework comparisons when the model, task, tools, configuration, scorer, and exclusions are held constant and repeated.

“Comparable” means the manifests describe the same evidence contract. It does not mean the result is statistically stable or the causal explanation is known. A provider comparison with fewer than three repetitions remains visibly weak even when its fields match.

## Create a run record locally

```bash
python -m examples.harness.evidence_lab --claim recovery --mode offline-fixture --observation "one effect after retry"
python -m examples.harness.evidence_lab --claim provider_comparison --mode live --model MODEL --repetitions 5
pytest tests/test_evidence_lab.py -q
```

The record uses `agentic-arena.run-record/v1` and keeps observations separate from `design_guidance`. It records commit, configuration, model, dataset, scorer, repetitions, and exclusions. The browser download adds both records and their comparison under a versioned envelope; its share link encodes the choices, not unpublished results.

Use [run modes](../reference/run-modes.md) to choose evidence and [methodology](../methodology.md) before publishing a comparison.

Next: [Developer labs](index.md) · [Evaluate a claim](../journeys/evaluate.md)
