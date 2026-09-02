# `pydantic_ai` adapter

A single `pydantic_ai.Agent` with the shared search / calculator tools.

- **Deps:** see [requirements.txt](requirements.txt) — `pydantic-ai-slim[openai]`,
  which installs cleanly on Python 3.11–3.14 (all wheels, no build step).
- **LLM:** `OpenAIChatModel(config.model, provider=OpenAIProvider(base_url=config.base_url,
  api_key=config.api_key))`. Pydantic AI treats any OpenAI-compatible endpoint as a
  first-class provider, so the shared gateway / mock server drives it directly.
  The provider is handed an explicit `AsyncOpenAI(..., timeout=config.request_timeout_s)`
  rather than a `base_url`: given a `base_url` it builds its own client with the
  library default timeout, and the arena's budget would be ignored.
- **Tools:** registered with `@agent.tool_plain`, each delegating to the unmodified
  `arena.tools` function. Tool calls are recovered from `result.all_messages()` by
  scanning for `ToolCallPart`.
- **Metrics:** `result.usage` → `input_tokens`, `output_tokens`, `requests`.
- **Temperature:** pinned to `0.0` via `OpenAIChatModelSettings`.

```bash
python -m pip install -e . -r frameworks/pydantic_ai/requirements.txt
python -m arena run --arena tool_use --framework pydantic_ai --mode mock
```

Status: smoke-verified 15/15 against the `tool_use` mock on Python 3.14.
