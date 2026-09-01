---
name: Refresh results
about: Re-run live scorecards after a framework version bump
title: "results: refresh <arena> (<reason>)"
labels: ["results"]
---

## Why

<!-- e.g. langgraph 1.3.0 released; quarterly refresh; new adapter landed -->

## Checklist

- [ ] Bumped pinned versions in the relevant `frameworks/*/requirements.txt`
- [ ] Ran `full-run` workflow (or local `--mode live --repeat 3`) for each affected arena
- [ ] Committed updated `results/<arena>/scorecard.{md,csv,json}`
- [ ] Noted the run date + model + versions in the PR description
