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
   Register **only the ones `arena.tools` declares** — `arena.tools.names_for(arena.tools)`
   resolves the list for you.

3b. Take the system prompt from `arena.system_prompt`. Do **not** hard-code a task
   instruction: your adapter would then ask for the wrong thing on every other
   arena, and mock mode would not catch it. `tests/test_adapters_contract.py`
   asserts both of these against the request body the mock server actually
   received, so a hard-coded prompt or an undeclared tool fails CI.

4. Populate `AgentResult`: `output_text`, `tool_calls`, `prompt_tokens`,
   `completion_tokens`, `latency_s`, and `error` on failure. Token counts come back
   from the gateway response; if the framework hides them, read them from
   `runner.usage` which the shared client accumulates.

5. Add `frameworks/<name>/requirements.txt` (pinned) and a short
   `frameworks/<name>/README.md` noting anything non-obvious.

6. Confirm it runs, then confirm it plays fair:

   ```bash
   python -m arena run --arena tool_use --framework <name> --mode mock
   pytest tests/test_adapters_contract.py -q
   ```

   The second command is the one that matters. A green mock run only proves the
   adapter wires together; the contract tests assert on the actual request bodies
   that your adapter sends the arena's prompt, advertises only the arena's tools,
   stops at the shared iteration budget, hands the model the tool result
   byte-for-byte, runs the arguments the model asked for, and replays the whole
   transcript each turn. They run automatically in the `comparison` CI job, which
   is the only one that installs every framework — add your framework to that
   job's install loop and to its `ARENA_EXPECT_FRAMEWORKS` list.

7. Add a row to the framework table in the top-level `README.md` and a deep-dive
   stub in `docs/frameworks/<name>.md`.

## Adding an arena

1. `arenas/<name>/arena.toml` — id, description, which shared tools are available,
   and the system-prompt intent.
2. `arenas/<name>/dataset.jsonl` — one JSON object per line:
   `{"id": "...", "input": "...", "checks": [{"type": "...", ...}]}`.
3. `arenas/<name>/mock_script.json` — canned LLM turns so the arena runs in mock mode.
   Keyed by a substring match against the first user message.
4. If you need a new check type, add it to `arena/scorer.py` — both the `_check`
   body and the `CHECK_SPECS` registry — with a unit test in `tests/test_scorer.py`.
   A check type in one and not the other fails the test suite.
5. Run `python -m arena validate` (CI does too). It catches the mistakes that
   otherwise surface as an unexplained 0/N: an item no mock scenario matches, an
   unknown check type, a tool the arena never declared, duplicate item ids, a
   scenario that ends on a tool call.
6. Document it in the arenas table in `README.md` and in `ROADMAP.md`.

## Commit / PR conventions

- One framework-adapter or one arena per PR where possible.
- Conventional-commit style subject lines (`feat(langgraph): ...`, `docs: ...`).
- CI must be green: `ruff`, `pytest`, and the mock smoke run for any adapter you touched.
- The PR template has a checklist — fill it in.
