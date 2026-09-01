<!-- Thanks for contributing to agentic-arena! -->

## What & why



## Type

- [ ] New / completed framework adapter
- [ ] New / changed arena
- [ ] Harness change
- [ ] Results refresh
- [ ] Docs only

## Checklist

- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `pytest -q` passes
- [ ] For an adapter change: `python -m arena run --arena <arena> --framework <name> --mode mock` is green
- [ ] Fairness rules in `docs/methodology.md` still hold (same model, unmodified tools, prompt checked in)
- [ ] Committed `results/` only from `--mode live` runs, with date + versions in this description
- [ ] Updated `README.md` / `ROADMAP.md` tables if relevant
