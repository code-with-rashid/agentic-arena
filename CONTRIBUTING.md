# Contributing to agentic-arena

The most valuable contribution right now is **filling in an empty framework × arena
cell**. This guide walks through that, plus adding a whole new framework or arena.

## Ground rules

- Keep the comparison fair. Read [docs/methodology.md](docs/methodology.md) first.
  An adapter must not swap the model, change what the shared tools do, or special-case
  individual eval items.
- Every adapter must run in **mock mode** in CI without network access or an API key.
- Published scorecards come only from `--mode live` runs. Don't commit mock-mode
  numbers into `results/`.
- Pin your framework's version in `frameworks/<name>/requirements.txt`.

## Dev setup

```bash
python -m pip install -e ".[dev]"
python -m pytest              # harness + baseline adapter tests, all offline
ruff check . && ruff format --check .
```

## Adding a framework adapter

1. Create `frameworks/<name>/adapter.py` implementing the `Framework` protocol from
   `arena.types`:

   ```python
   from arena.types import Framework, AgentRunner, AgentResult, ArenaSpec
   from arena.config import ArenaConfig


   class Adapter(Framework):
       name = "my_framework"

       @property
       def lib_version(self) -> str:
           import my_framework

           return my_framework.__version__

       def build(self, arena: ArenaSpec, config: ArenaConfig) -> AgentRunner:
           # construct the agent once; return an object with .run(item) -> AgentResult
           ...
   ```

2. Wire the framework's LLM client to the shared gateway. Every framework worth
   comparing accepts an OpenAI-compatible `base_url` + `api_key` + `model`; read them
   from `config` (`config.base_url`, `config.api_key`, `config.model`). This is what
   lets the mock server stand in for a real provider.

3. Use the shared tools from `arena.tools` (`search(query)` and `calculator(expr)`).
   Register them with the framework's own tool mechanism — do not reimplement them.

4. Populate `AgentResult`: `output_text`, `tool_calls`, `prompt_tokens`,
   `completion_tokens`, `latency_s`, and `error` on failure. Token counts come back
   from the gateway response; if the framework hides them, read them from
   `runner.usage` which the shared client accumulates.

5. Add `frameworks/<name>/requirements.txt` (pinned) and a short
   `frameworks/<name>/README.md` noting anything non-obvious.

6. Confirm it runs:

   ```bash
   python -m arena run --arena tool_use --framework <name> --mode mock
   ```

7. Add a row to the framework table in the top-level `README.md` and a deep-dive
   stub in `docs/frameworks/<name>.md`.

## Adding an arena

1. `arenas/<name>/arena.toml` — id, description, which shared tools are available,
   and the system-prompt intent.
2. `arenas/<name>/dataset.jsonl` — one JSON object per line:
   `{"id": "...", "input": "...", "checks": [{"type": "...", ...}]}`.
3. `arenas/<name>/mock_script.json` — canned LLM turns so the arena runs in mock mode.
   Keyed by a substring match against the first user message.
4. If you need a new check type, add it to `arena/scorer.py` with a unit test in
   `tests/test_scorer.py`.
5. Document it in the arenas table in `README.md` and in `ROADMAP.md`.

## Commit / PR conventions

- One framework-adapter or one arena per PR where possible.
- Conventional-commit style subject lines (`feat(langgraph): ...`, `docs: ...`).
- CI must be green: `ruff`, `pytest`, and the mock smoke run for any adapter you touched.
- The PR template has a checklist — fill it in.
