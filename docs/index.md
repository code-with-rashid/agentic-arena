# agentic-arena docs

- [Methodology](methodology.md) — the fairness and reproducibility rules. Read first.
- [Decision guide](decision-guide.md) — how to pick a framework (skeleton, fills in with evidence).
- [Feature matrix](feature-matrix.md) — capabilities that aren't scorecard numbers.
- Per-framework deep dives: [`frameworks/`](frameworks/)

## How a run works

```
arena run --arena tool_use --framework langgraph --mode mock
   │
   ├─ registry.load_arena("tool_use")      -> arena.toml + dataset.jsonl + mock_script.json
   ├─ mode=mock: start arena.llm.mockserver, override base_url
   ├─ registry.load_framework("langgraph") -> frameworks/langgraph/adapter.py :: Adapter()
   ├─ adapter.build(arena, config)         -> an AgentRunner
   ├─ for each dataset item (x repeat): runner.run(item) -> AgentResult
   ├─ scorer.score_item(item, result)      -> pass/fail per mechanical check
   └─ scorecard.write_scorecard(record)    -> live: results/tool_use/scorecard.{md,csv,json}
                                              mock: runs/scorecards/tool_use/ (git-ignored)
```

## Repo map

| Path | What |
|---|---|
| `arena/` | the harness: config, types, registry, runner, scorer, scorecard |
| `arena/llm/` | OpenAI-compatible client + the stdlib mock server |
| `arena/tools/` | shared `search` + `calculator` + corpus |
| `arenas/<id>/` | one arena: `arena.toml`, `dataset.jsonl`, `mock_script.json` |
| `frameworks/<name>/` | one adapter: `adapter.py`, `requirements.txt`, `README.md` |
| `results/<id>/` | committed **live** scorecards |
| `runs/` | raw run JSON (git-ignored) |
