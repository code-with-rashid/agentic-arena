# `microsoft_af` adapter

A single `agent_framework.Agent` (Microsoft Agent Framework — the merged AutoGen +
Semantic Kernel line) with the shared search / calculator tools.

- **Deps:** see [requirements.txt](requirements.txt). Install
  `agent-framework-openai` (+ its `agent-framework-core` dep) — **not** the
  `agent-framework` meta-package, which drags in `agent-framework-core[all]`
  (azure, boto3, redis, qdrant, ollama, numpy, …). The narrow install is
  wheels-only and works on Python 3.11–3.14.
- **LLM:** `OpenAIChatCompletionClient(model=config.model, async_client=AsyncOpenAI(
  base_url=config.base_url, api_key=config.api_key))`. Note the client class:
  `OpenAIChatClient` defaults to the OpenAI **Responses** API (`/v1/responses`),
  which the arena gateway / mock server does not speak — `OpenAIChatCompletionClient`
  uses Chat Completions.
- **Async:** the framework is async-only. The adapter builds a fresh client, agent,
  and event loop per item (`asyncio.run`) so the httpx client never outlives its
  loop.
- **Tools:** plain functions passed to `Agent(tools=[...])`. Tool calls are read
  from `response.messages` — `content.type == "function_call"` → `name` /
  `arguments`.
- **Metrics:** `response.usage_details` → `input_token_count`, `output_token_count`.
  There is no request counter, so `llm_calls` is the count of assistant messages.
- **Temperature:** pinned to `0.0` via `ChatOptions`.

```bash
python -m pip install -e . -r frameworks/microsoft_af/requirements.txt
python -m arena run --arena tool_use --framework microsoft_af --mode mock
```

Status: smoke-verified 15/15 against the `tool_use` mock on Python 3.14.
