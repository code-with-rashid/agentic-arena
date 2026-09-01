# Microsoft Agent Framework — deep dive

## At a glance

- Package / repo: `agent-framework-core` + `agent-framework-openai` (pinned
  `1.16.0` / `1.14.1`) · <https://github.com/microsoft/agent-framework>
- Licence: MIT
- Adapter: [`frameworks/microsoft_af/adapter.py`](../../frameworks/microsoft_af/adapter.py)
- Status: mock-green (15/15 on `tool_use` and `structured_output`, Python 3.14)

## Wiring notes

- **LLM:** `OpenAIChatCompletionClient(model=config.model, async_client=AsyncOpenAI(
  base_url=config.base_url, api_key=config.api_key))`, then
  `Agent(client, instructions=..., tools=[...], default_options=ChatOptions(temperature=0.0))`.
- **Tools:** plain Python functions passed straight to `Agent(tools=[...])`; the
  framework introspects their signature and docstring.
- **Metrics:** `response = await agent.run(prompt)`.
  - final answer: `response.text`
  - tokens: `response.usage_details` → `input_token_count`, `output_token_count`
    (dict; no request counter, so `llm_calls` counts assistant messages)
  - tool calls: iterate `response.messages`, then `message.contents`, keep
    `content.type == "function_call"` (`.name`, `.arguments`)

## Gotchas

- **Client class matters.** `OpenAIChatClient` defaults to the OpenAI *Responses*
  API (`/v1/responses`), which the arena gateway / mock does not serve — use
  `OpenAIChatCompletionClient`.
- **Async-only.** The adapter builds a fresh `AsyncOpenAI` client, agent, and event
  loop per item (`asyncio.run`) so the httpx client never outlives its loop.
- Install the narrow `agent-framework-openai` (pulls `agent-framework-core`), not
  the `agent-framework` meta-package — that one pulls `agent-framework-core[all]`
  (azure, boto3, redis, qdrant, ollama, numpy, …).
- The `agent_framework` import is done in `_Runner.__init__` so a missing install
  degrades to "unavailable" at build time instead of erroring on every item.

## Results

| Arena | Mode | Pass rate | Mean tokens | Mean latency | Link |
|---|---|--:|--:|--:|---|
| tool_use | mock | 15/15 | — | — | plumbing only |
| structured_output | mock | 15/15 | — | — | plumbing only |

_Live numbers land here once a key is wired into the `full-run` workflow._
