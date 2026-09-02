# `openai_agents` adapter

A single `agents.Agent` (OpenAI Agents SDK) with the shared search / calculator
tools.

- **Deps:** see [requirements.txt](requirements.txt) — `openai-agents`, which
  installs cleanly on Python 3.11–3.14 (wheels only).
- **LLM:** an `AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)` client
  wrapped in `OpenAIChatCompletionsModel(model=config.model, ...)`. The SDK is
  model-family-native but accepts any OpenAI-compatible client, which is what lets
  the mock server stand in. The client carries `timeout=config.request_timeout_s`
  so a hung gateway is bounded by the arena's budget rather than the OpenAI
  client's ten-minute default.
- **Tracing:** disabled via `set_tracing_disabled(True)` — the SDK otherwise tries
  to upload traces to OpenAI, which fails and leaks against the mock or a
  third-party gateway.
- **Tools:** `@function_tool` wrappers delegating to the unmodified `arena.tools`
  functions. Tool calls are read from `result.new_items` (`ToolCallItem` →
  `raw_item.name` / `raw_item.arguments`).
- **Metrics:** `result.context_wrapper.usage` → `input_tokens`, `output_tokens`,
  `requests`.
- **Temperature:** pinned to `0.0` via `ModelSettings`.

```bash
python -m pip install -e . -r frameworks/openai_agents/requirements.txt
python -m arena run --arena tool_use --framework openai_agents --mode mock
```

Status: smoke-verified 15/15 against the `tool_use` mock on Python 3.14.
