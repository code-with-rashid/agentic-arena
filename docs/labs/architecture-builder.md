---
hide:
  - toc
---

# Harness architecture builder

Choose the workload and the contracts it needs. The builder assigns each responsibility to a neutral component, traces the design back to the dossier requirements, and exports a versioned record you can carry into a new harness repository.

<div class="design-lab" data-design-lab>
  <div class="design-lab__controls" aria-label="Harness design controls">
    <label><span>Workload</span><select data-design-workload><option value="research">Research</option><option value="coding" selected>Coding</option><option value="operations">Operations</option></select></label>
    <label><span>Effect risk</span><select data-design-risk><option value="read_only">Read only</option><option value="reversible" selected>Reversible</option><option value="irreversible">Irreversible</option></select></label>
    <label><span>Restart contract</span><select data-design-restart><option value="stateless">Start over</option><option value="resumable" selected>Resume work</option><option value="effect_safe">Resume without duplicate effects</option></select></label>
    <label><span>Approval policy</span><select data-design-approval><option value="none">No approval gate</option><option value="risky" selected>Gate risky effects</option><option value="every_effect">Gate every effect</option></select></label>
    <label class="design-lab__check"><input data-design-delegation type="checkbox"><span>Delegate to child agents</span></label>
  </div>
  <div class="design-lab__workspace">
    <section><span class="workbench-label">Responsibility map</span><ol class="design-lab__components" data-design-components></ol></section>
    <section class="design-lab__export"><span class="workbench-label">Versioned design record</span><pre data-design-record></pre><div class="workbench-actions"><button type="button" data-design-copy>Copy JSON</button><button type="button" data-design-download>Download</button><button type="button" data-design-share>Copy share link</button></div><p data-design-action role="status" aria-live="polite"></p></section>
  </div>
  <div class="design-lab__footer"><div><span>Requirements</span><strong data-design-requirements></strong></div><p data-design-boundary></p></div>
</div>

## What the builder decides

The same six responsibilities always exist: model access, context selection, scheduling, tool dispatch, execution, and independent evidence. Your choices add contracts only when the workload needs them:

- resumable work adds a checkpoint store;
- approval or effects add a policy and approval gate;
- irreversible or replay-sensitive effects add an effect journal and reconciliation;
- delegation adds a supervisor that owns child budgets, provenance, and cancellation;
- coding adds an explicit workspace boundary.

The boxes are responsibilities, not required deployment units. One small process may implement several of them, but their contracts should remain visible so authority, state, and evidence do not collapse into a framework callback.

## Export the same design locally

```bash
python -m examples.harness.design_lab --workload coding --effect-risk irreversible --restart effect_safe --approval risky --delegation
python -m examples.harness.design_lab --workload research --effect-risk read_only --restart stateless --approval none --format markdown
pytest tests/test_design_lab.py -q
```

The JSON and Markdown exports use `agentic-arena.harness-design/v1`. They contain decisions, components, traced requirements, acceptance experiments, and an explicit evidence boundary. Paste the Markdown into the [full design dossier](../build/design-dossier.md) as a starting decision record, then replace assumptions with experiment results.

This builder produces design guidance. It does not prove that an implementation is secure, durable, or effective.

Next: [Evidence workspace](evidence-workspace.md) · [Design dossier](../build/design-dossier.md)
