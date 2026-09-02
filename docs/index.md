# agentic-arena docs

- [Methodology](methodology.md) — the fairness and reproducibility rules. Read first.
- [Decision guide](decision-guide.md) — how to pick a framework (skeleton, fills in with evidence).
- [Feature matrix](feature-matrix.md) — capabilities that aren't scorecard numbers.
- [Framework overhead](overhead.md) — what each library adds to the wire for an
  identical task. One of only two things mock mode can compare honestly.
- [Dependencies](dependencies.md) — the pinning policy, why the harness has zero
  runtime deps, and the deprecation register.
- Per-framework deep dives: [`frameworks/`](frameworks/)

## Reports

- `python -m arena scorecard --arena <id>` — one arena, every adapter.
- `python -m arena summary --print` — **all** arenas in one view: a coverage grid
  plus the three things that compare honestly offline (fault recovery, prompt
  size, pause support). Written to `runs/summary.md` for mock runs and
  `results/summary.md` for live ones, so mock numbers never reach `results/`.

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
