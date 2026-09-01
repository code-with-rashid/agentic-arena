# results/

Committed scorecards, one directory per arena. **Only `--mode live` runs belong
here** — mock-mode numbers are plumbing, not measurement (see
[../docs/methodology.md](../docs/methodology.md)).

Each `results/<arena>/` holds:

- `scorecard.md` — human-readable table, with the model / date / versions header
- `scorecard.csv` — same rows, for spreadsheets / plotting
- `scorecard.json` — full aggregated rows + run metadata

Regenerate from the most recent matching run:

```bash
python -m arena scorecard --arena <arena> --mode live
```

Raw per-item run JSON lives in `../runs/` and is git-ignored (large, and
reproducible from a live re-run).

## Current state

`tool_use/` currently contains a **mock** scorecard committed as a format example
only. It will be replaced by a real live scorecard once a key is wired into the
`full-run` workflow. Do not cite the mock numbers.
