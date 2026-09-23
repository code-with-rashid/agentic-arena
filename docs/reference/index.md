# Reference

Look up the mechanics of Agentic Arena: run modes, comparison controls, evaluation definitions, commands, and repository structure.

## Most-used references

| Need | Reference |
|---|---|
| Understand what a result can prove | [Run modes](run-modes.md) |
| Reproduce or audit a comparison | [Methodology](../methodology.md) |
| Check controlled inputs | [Fairness controls](../fairness-controls.md) |
| Run with a subscription-backed model | [Codex bridge](../codex-bridge.md) |
| Inspect adapter dependencies | [Dependencies](../dependencies.md) |
| Understand a scorecard artifact | [Scorecard example](../scorecard-example.md) |
| See planned project work | [Next phases](../next-phases.md) |

## Command map

```text
python -m arena validate
python -m arena run --arena tool_use --framework vanilla --mode mock
python -m arena scorecard --arena tool_use
python -m arena summary --print
python -m arena chart --arena tool_use
```

## Repository map

| Path | Responsibility |
|---|---|
| `arena/` | harness, configuration, runner, scorer, and reports |
| `arena/llm/` | OpenAI-compatible client, mock server, and Codex bridge |
| `arena/tools/` | shared tools and fixed local corpus |
| `arenas/<id>/` | workload specification, dataset, and mock script |
| `frameworks/<name>/` | one framework adapter and its dependencies |
| `results/` | committed native live scorecards |
| `runs/` | local and CI artifacts that are not published as results |
