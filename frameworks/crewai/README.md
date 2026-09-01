# `crewai` adapter

A single-agent sequential `Crew` with the shared search / calculator tools.

- **Deps:** see [requirements.txt](requirements.txt). **Python 3.11 / 3.12 only** —
  CrewAI's transitive tree (chromadb, onnxruntime, numpy) has no wheels for 3.14 yet.
- **LLM:** `crewai.LLM(model=f"openai/{config.model}", base_url=config.base_url,
  api_key=config.api_key)` — CrewAI routes through LiteLLM, so the shared gateway is
  configured as an OpenAI-compatible provider.
- **Tools:** `crewai.tools.BaseTool` subclasses that record each call into a sink
  list (CrewAI does not expose tool-call history directly) and then delegate to the
  unmodified `arena.tools` functions.
- **Metrics:** `crew.usage_metrics` for tokens and request count.

```bash
python3.12 -m venv .venv-crewai && . .venv-crewai/bin/activate
pip install -e . -r frameworks/crewai/requirements.txt
python -m arena run --arena tool_use --framework crewai --mode mock
```

Status: adapter written, **not yet smoke-verified**. A first CI attempt on Python
3.12 installed CrewAI fine but scored 0/15 against the mock — an interactive
"view execution traces? [y/N]" prompt plus an internal
`'list' object has no attribute 'rstrip'`. The adapter now forces telemetry and
tracing off (`CREWAI_DISABLE_TELEMETRY`, `CREWAI_TRACING_ENABLED`,
`OTEL_SDK_DISABLED`), but it still needs a hands-on debug on a 3.12 venv. Until
that passes, the `crewai` job is deliberately kept out of the required
`mock-smoke` CI matrix in `.github/workflows/ci.yml`.

First contributor to get it green: pin the exact `crewai` version in
`requirements.txt`, re-add the CI job, and commit the `results/` refresh.
