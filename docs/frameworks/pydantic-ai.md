# Pydantic AI — deep dive

## At a glance

- Package / repo: `pydantic-ai-slim[openai]` (pinned `2.37.0`) ·
  <https://github.com/pydantic/pydantic-ai>
- Licence: MIT
- Adapter: [`frameworks/pydantic_ai/adapter.py`](../../frameworks/pydantic_ai/adapter.py)
- Status: mock-green (15/15 on `tool_use` and `structured_output`, Python 3.14)

## Wiring notes

- **LLM:** `OpenAIChatModel(config.model, provider=OpenAIProvider(base_url=config.base_url,
  api_key=config.api_key))`. Pydantic AI treats any OpenAI-compatible endpoint as a
  first-class provider, so the mock server needs no special handling. Temperature is
  pinned with `OpenAIChatModelSettings(temperature=0.0)`.
- **Tools:** registered with `@agent.tool_plain`; each wrapper calls the unmodified
  `arena.tools` function. `tool_plain` (no `RunContext`) is enough here.
- **Metrics:** `result = agent.run_sync(item.input)`.
  - final answer: `result.output`
  - tokens: `result.usage` → `.input_tokens`, `.output_tokens`, `.requests`
    (`usage` is a property, not a call)
  - tool calls: scan `result.all_messages()` for `ToolCallPart` (`.tool_name`,
    `.args`)

## Gotchas

- `-slim` + the `openai` extra is all that's needed; the `pydantic-ai`
  meta-package adds provider SDKs the adapter never touches.
- `result.usage` vs `result.usage()` — it's an attribute in 2.37; calling it
  raises `TypeError`.
- Distribution name is `pydantic-ai-slim`, so `importlib.metadata.version` needs
  that string (the adapter tries both).

## Results

| Arena | Mode | Pass rate | Mean tokens | Mean latency | Link |
|---|---|--:|--:|--:|---|
| tool_use | mock | 15/15 | — | — | plumbing only |
| structured_output | mock | 15/15 | — | — | plumbing only |

_Live numbers land here once a key is wired into the `full-run` workflow._
