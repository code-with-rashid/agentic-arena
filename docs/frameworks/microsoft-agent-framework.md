# Microsoft Agent Framework — deep dive

## At a glance

- Package / repo: `agent-framework-core` + `agent-framework-openai` (pinned
  `1.16.0` / `1.14.1`) · <https://github.com/microsoft/agent-framework>
- Licence: MIT
- Adapter: [`frameworks/microsoft_af/adapter.py`](../../frameworks/microsoft_af/adapter.py)
- Status: mock-green on six arenas including `human_in_the_loop` (12/12, native
  tool-approval middleware); reports *unsupported* on `durable_state` (see below)

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

## The pause: native tool approval

This adapter pauses with the framework's own **tool-approval middleware**, which
is a fifth distinct mechanism — no two of the five look alike:

| framework | pause is... | resumes from... |
|---|---|---|
| LangGraph | `interrupt()` inside the tool | a checkpointer keyed by `thread_id` |
| OpenAI Agents | `needs_approval=True` on the tool | `RunState.to_json()` — the whole run |
| Pydantic AI | `CallDeferred` raised by the tool | the conversation, replayed as `message_history` |
| **Agent Framework** | `approval_mode="always_require"` on the tool | an `AgentSession` carried forward in memory |

The wiring:

```python
@tool(approval_mode="always_require")
def request_approval(summary: str) -> str: ...


agent = Agent(client, tools=[...], middleware=[ToolApprovalMiddleware(), probe])
response = await agent.run(prompt, session=AgentSession())
if response.user_input_requests:  # paused
    request = response.user_input_requests[0]
    answer = request.to_function_approval_response(approved)
    await agent.run(
        [prompt, *response.messages, Message(role="user", contents=[answer])], session=session
    )  # the SAME session
```

Four things cost real debugging time.

**The middleware refuses to run without an `AgentSession`.** Approval bookkeeping
lives in `session.state`, not in the agent.

**`AgentSession` is a state container, not a conversation store — except that it
quietly is.** The docs describe it as holding "session IDs and a mutable state
dict", and `response.messages` comes back holding only the final turn. But the
transcript is in `session.state["in_memory"]["messages"]`, and **reusing the same
session object is the only thing that makes the resumed leg see any history at
all**. Build a fresh session and the resume re-asks the model from an empty
conversation and pauses again, forever.

**The opening turn must go back as a plain string.**
`Message(role="user", contents=["..."])` does not produce a user text turn, and
the resumed leg then arrives with its history silently missing.

**`response.messages` is not a usable ledger once the approval middleware is
installed.** It collapses to the final turn, hiding the tool round that preceded
the pause — counting assistant messages under-reported both `llm_calls` and
`tool_calls`, which the usage-accounting gate catches. The adapter now counts at
the chat layer with a small observe-only `ChatMiddleware`, which is accurate on
every arena whether or not the approval middleware is in play.

## Why `durable_state` is still unsupported

`durable_state` throws the runner away at the pause and rebuilds it, so only what
is in `resume_state` survives. This pause cannot cross that gap, and it was
measured both ways rather than assumed:

- The middleware's `session.state["tool_approval"]` **is** cleanly
  JSON-serialisable (a plain dict, ~400 chars). That part is not the problem.
- The conversation is not. `session.state["in_memory"]` comes back from a JSON
  round trip as raw strings, and the session middleware then fails with
  `'str' object has no attribute 'contents'`.
- Restoring the approval state into a rebuilt agent and replaying a serialised
  transcript **re-queues the same approval request** instead of consuming the
  answer — the run pauses again rather than finishing. With the state left out it
  is worse: the model is re-asked from scratch.

So the adapter deliberately does **not** expose `resume` on a durable arena
(`Adapter.build` returns a runner without it). An adapter that kept a `resume` it
could not honour would post 0/8 and read as a broken framework; not having the
method is the honest signal, and the harness reports *unsupported*. See
`docs/methodology.md` §7.

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
