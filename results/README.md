# results/

Committed scorecards, one directory per arena. **Only `--mode live` runs belong
here** — mock-mode numbers are plumbing, not measurement (see
[../docs/methodology.md](../docs/methodology.md)).

That rule is enforced by the harness, not by memory: `arena.scorecard` routes a
mock run's scorecard to `runs/scorecards/<arena>/` (git-ignored) and only a live
run writes into `results/`. So a mock benchmark can never dirty this directory.

Each `results/<arena>/` holds:

- `scorecard.md` — human-readable table, with the model / date / versions header
- `scorecard.csv` — same rows, for spreadsheets / plotting
- `scorecard.json` — full aggregated rows + run metadata
- `charts/` — `pass-rate.svg`, `mean-tokens.svg`, `mean-llm-calls.svg`,
  `est-cost.svg` (hand-written SVG, no plotting dependency) plus an `index.md`
  that embeds them

`REFRESHED.md` at this level rolls all of the above up into one table — when each
arena was last run, with which model and adapter versions. It is generated
(`python -m arena refreshed`, and automatically by `arena scorecard --mode
live`), and CI fails if it drifts.

Regenerate from the most recent matching run:

```bash
python -m arena scorecard --arena <arena> --mode live
python -m arena chart --arena <arena> --mode live
```

Raw per-item run JSON lives in `../runs/` and is git-ignored (large, and
reproducible from a live re-run).

## Current state

**Empty — there is no live scorecard yet.** One needs an API key wired into the
`full-run` workflow; see [../STATUS.md](../STATUS.md).

To see what a generated scorecard looks like without waiting for that, read
[../docs/scorecard-example.md](../docs/scorecard-example.md) — a mock run kept
purely as a format sample, clearly labelled as not-real-numbers.
