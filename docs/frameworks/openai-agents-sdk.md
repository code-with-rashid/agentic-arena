# OpenAI Agents SDK — deep dive

## At a glance

- Package / repo: `openai-agents` (pinned `0.22.0`) ·
  <https://github.com/openai/openai-agents-python>
- Licence: MIT
- Adapter: [`frameworks/openai_agents/adapter.py`](../../frameworks/openai_agents/adapter.py)
- Status: mock-green (15/15 on `tool_use` and `structured_output`, Python 3.14)

## Wiring notes

- **LLM:** `AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)` wrapped in
  `OpenAIChatCompletionsModel(model=config.model, openai_client=client)`. Temperature
  is set with `ModelSettings(temperature=0.0)`.
- **Tools:** `@function_tool` wrappers over the shared `arena.tools` functions.
- **Metrics:** `result = Runner.run_sync(agent, item.input, max_turns=...)`.
  - final answer: `result.final_output`
  - tokens: `result.context_wrapper.usage` → `.input_tokens`, `.output_tokens`,
    `.requests`
  - tool calls: iterate `result.new_items`, keep `ToolCallItem`, read
    `raw_item.name` / `raw_item.arguments`

## Gotchas

- **Tracing must be disabled** (`set_tracing_disabled(True)`), otherwise the SDK
  tries to POST traces to `api.openai.com` — fails against the mock and leaks
  prompts against a third-party gateway.
- `Runner.run_sync` calls `asyncio.run` internally, so it must not be invoked from
  inside a running event loop. The harness runner thread has none, so it is fine.
- Usage lives on `result.context_wrapper.usage`, not `result.usage`.

## Results

| Arena | Mode | Pass rate | Mean tokens | Mean latency | Link |
|---|---|--:|--:|--:|---|
| tool_use | mock | 15/15 | — | — | plumbing only |
| structured_output | mock | 15/15 | — | — | plumbing only |

_Live numbers land here once a key is wired into the `full-run` workflow._
