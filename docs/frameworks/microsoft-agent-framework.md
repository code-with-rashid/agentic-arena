# Microsoft Agent Framework — deep dive

## At a glance

- Package / repo: `agent-framework-core` + `agent-framework-openai` (pinned
  `1.16.0` / `1.14.1`) · <https://github.com/microsoft/agent-framework>
- Licence: MIT
- Adapter: [`frameworks/microsoft_af/adapter.py`](../../frameworks/microsoft_af/adapter.py)
- Status: mock-green on the five arenas that need no pause; reports
  *unsupported* on `human_in_the_loop` and `durable_state` (see below)

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
- **The tool loop is uncapped by default.** Measured against a mock that never
  stops requesting tools, a budget of 6 produced **41** LLM calls. The cap is
  `function_invocation_configuration={"max_iterations": N}`, and it counts tool
  *roundtrips* — the framework then emits one final text response on top, so
  `N - 1` roundtrips gives the same `N` total LLM calls the other adapters get.

## Why the pause is not wired up yet

This is the one adapter that reports *unsupported* on `human_in_the_loop` and
`durable_state`, and it is worth being precise about why, because "not wired up"
is not "cannot".

Agent Framework does ship a human-in-the-loop story — `ToolApprovalMiddleware`,
`ToolApprovalRule`, `ToolApprovalState`. It is a **different shape** from the
three mechanisms already adapted:

| framework | pause is... | resumes from... |
|---|---|---|
| LangGraph | `interrupt()` inside the tool | a checkpointer keyed by `thread_id` |
| OpenAI Agents | `needs_approval=True` on the tool | `RunState.to_json()` — the whole run |
| Pydantic AI | `CallDeferred` raised by the tool | the conversation, replayed as `message_history` |
| **Agent Framework** | a rule in **session state** | an `AgentSession`, whose contents live in a store |

The harness's contract (`arena.types.ResumableRunner`) is that an adapter hands
back a JSON-serialisable `resume_state` and nothing else — `durable_state` round-
trips it through `json.dumps` and rebuilds the runner. Agent Framework's approval
queue lives in session state rather than in anything the adapter is handed, and
`AgentSession` itself carries only ids (`session_id`, `service_session_id`), so
satisfying the contract means first choosing and wiring a session store. That is
a design decision, not a plumbing detail, so it is deliberately not guessed at.

What was checked, for whoever picks this up:

- `Agent.run(messages, *, session=..., middleware=..., ...)` accepts both.
- `AgentSession` has `to_dict()` / `from_dict()`, so the *handle* serialises —
  the question is where its contents are persisted.
- `FunctionInvocationContext` exposes `function`, `arguments`, `session`,
  `metadata` and a settable `result`, but no termination flag; overriding the
  result does not stop the loop, so the model would go on to call the
  consequential tool anyway. Stopping the run looks like agent-level middleware
  (`MiddlewareTermination`), not function-level.

Reporting this as *unsupported* rather than as twenty failed items is deliberate;
see `docs/methodology.md` §7.

## Results

Mock mode only. Pass rates in mock mode are ~100% by construction and are **not**
a quality signal. The comparable columns are marked.

| Arena | Mode | Pass rate | Note |
|---|---|--:|---|
| `tool_use` | mock | 15/15 | 732 prompt tok/item, 0.97× baseline *(comparable)* |
| `structured_output` | mock | 15/15 | |
| `rag` | mock | 15/15 | |
| `multi_agent` | mock | 10/10 | single-agent role-play entry |
| `resilience` | mock | **8/8** | *(comparable)* — recovers from every scripted fault |
| `human_in_the_loop` | mock | n/s | no `resume` method — see above |
| `durable_state` | mock | n/s | no `resume` method — see above |

_Live numbers land here once a key is wired into the `full-run` workflow._
