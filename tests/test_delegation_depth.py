"""How does delegation cost scale with the depth of the chain?

`docs/multi-agent.md` measured three roles and said plainly that two points do
not establish a curve. This measures one to five roles, for **five** delegation
implementations across four libraries. Every one follows an exact law:

    roles                                    1   2   3   4   5
    ---------------------------------------------------------------
    handoffs      (openai_agents)  swap      2   3   4   5   6   = N + 1
    sub_agents    (google_adk)     transfer  2   4   5   6   7   = N + 2
    managed_agents(smolagents)     as tool   2   4   6   8  10   = 2N
    AgentTool     (google_adk)     as tool   2   4   6   8  10   = 2N
    delegation    (pydantic_ai)    as tool   2   4   6   8  10   = 2N

Three things fall out of that table, and none is visible at three roles.

**The 2N law is a property of the mechanism, not of one library.** smolagents,
Google ADK and Pydantic AI share no code, and they express the shape three
different ways — a `managed_agents` list, an `AgentTool` wrapper, and an ordinary
async tool whose body happens to `await sub.run(...)`. All three agree at every
depth. A sub-agent's reply is a *tool result*, not the end of the run, so every
delegator spends one call to delegate and another to produce its own final answer
once the sub-agent returns. The third implementation matters because it is not a
delegation *feature* at all — nothing in the library knows a sub-agent is
involved — and it still costs exactly 2N.

**"Handoff" is not one thing.** Both the OpenAI Agents SDK and ADK describe
theirs as transferring to another agent, and they do not cost the same, because
ADK **returns control to the parent** when the sub-agent finishes and the parent
then speaks again. One extra call, constant with depth, and it is the difference
between N+1 and N+2. The name is the same; the control flow is not.

**You pay in calls or in prompt, and the call law points the wrong way.** Prompt
tokens for the same five chains, one role to four:

    handoffs       (swap)     452  907 1362 1883    calls 2.50x  prompt 4.17x
    sub_agents     (transfer) 479 3168 5229 7375    calls 3.00x  prompt 15.40x
    managed_agents (as tool) 2367 5859 9311 13441   calls 4.00x  prompt 5.68x
    AgentTool      (as tool)  479 1126 1423 1722    calls 4.00x  prompt 3.59x
    delegation     (as tool)  430 1056 1318 1581    calls 4.00x  prompt 3.68x

Inside ADK, at four roles: `sub_agents` costs 6 calls and 7375 prompt tokens,
`AgentTool` 8 calls and 1722. A transfer keeps **one** conversation that every
agent sees all of, so the prompt compounds; a sub-agent starts a **fresh** one,
so the prompt stays flat and the calls compound instead. Cheaper in calls is
dearer in prompt, and prompt is usually the larger bill.

Restarting only helps if there is little to re-send, and the third
sub-agent-as-tool implementation is what proves that is the *library* rather than
the mechanism. Pydantic AI restarts each sub-agent exactly as smolagents does and
lands on ADK's numbers, not smolagents' — 1581 tokens against 1722 and 13441.
smolagents' 5.68x is its own ~4 KB templated system prompt, re-sent by every
fresh sub-agent — the scaffolding behind its 3.90x single-agent overhead in
docs/overhead.md — and nothing about starting fresh.

Note also which implementation is cheapest in prompt at four roles: the one that
costs the **most** calls. `pydantic_ai delegation` spends 8 calls to `handoffs`'
5, and 1581 prompt tokens to its 1883.

What is gated here are the laws, not the byte counts.
"""

import pytest

from arena.llm.mockserver import MockScript, MockServer

SCRIPT = MockScript(
    {
        "default": {
            "turns": [
                {"tool_calls": [{"name": "search", "arguments": {"query": "Eiffel Tower"}}]},
                {"content": "A brief about the Eiffel Tower: completed 1889, 330 metres tall."},
            ]
        }
    }
)

# Deliberately generic. The shape of the chain is the subject here; the real
# three-role pipelines carrying the arena's own role wording live in
# frameworks/*_multi.
STAGES = ["writer", "editor", "checker", "approver"]
TASK = "Write a brief about the Eiffel Tower."
DEPTHS = [1, 2, 3, 4]

# Building a chain and driving it is slow enough (ADK goes through LiteLLM) that
# re-measuring per assertion would dominate CI. Every measurement here is
# deterministic, so caching is safe.
_CACHE: dict[tuple[str, int], tuple[int, int]] = {}


def _measure(mechanism, depth):
    key = (mechanism, depth)
    if key not in _CACHE:
        _CACHE[key] = MECHANISMS[mechanism][0](depth)
    return _CACHE[key]


def _smolagents_managed(depth):
    """smolagents `managed_agents`: a sub-agent advertised as a tool named after itself."""
    smolagents = pytest.importorskip("smolagents")

    @smolagents.tool
    def search(query: str) -> str:
        """Search a small knowledge base of general facts.

        Args:
            query: What to look up.
        """
        from arena.tools import search as _search

        return _search(query)

    with MockServer(SCRIPT, arena_tools=["search"]) as server:
        model = smolagents.OpenAIServerModel(
            model_id="mock-model", api_base=server.base_url, api_key="mock-key"
        )
        # Built back to front: the deepest agent must exist before it is managed.
        sub = None
        for name in reversed(STAGES[: depth - 1]):
            managed = {"managed_agents": [sub]} if sub else {}
            sub = smolagents.ToolCallingAgent(
                tools=[],
                model=model,
                name=name,
                description=f"The {name} stage.",
                max_steps=6,
                **managed,
            )
        managed = {"managed_agents": [sub]} if sub else {}
        top = smolagents.ToolCallingAgent(tools=[search], model=model, max_steps=6, **managed)
        top.run(TASK)
        return len(server.requests), server.served_usage["prompt_tokens"]


def _openai_handoffs(depth):
    """OpenAI Agents SDK `handoffs`: one `transfer_to_<agent>` tool per target."""
    agents = pytest.importorskip("agents")

    agents.set_tracing_disabled(True)

    @agents.function_tool
    def search(query: str) -> str:
        """Search a small knowledge base of general facts."""
        from arena.tools import search as _search

        return _search(query)

    with MockServer(SCRIPT, arena_tools=["search"]) as server:
        client = agents.AsyncOpenAI(base_url=server.base_url, api_key="mock-key")
        model = agents.OpenAIChatCompletionsModel(model="mock-model", openai_client=client)
        settings = agents.ModelSettings(temperature=0.0)
        nxt = None
        for name in reversed(STAGES[: depth - 1]):
            handoffs = {"handoffs": [nxt]} if nxt else {}
            nxt = agents.Agent(
                name=name,
                instructions=f"The {name} stage.",
                model=model,
                model_settings=settings,
                **handoffs,
            )
        handoffs = {"handoffs": [nxt]} if nxt else {}
        top = agents.Agent(
            name="researcher",
            instructions="The researcher stage.",
            model=model,
            model_settings=settings,
            tools=[search],
            **handoffs,
        )
        agents.Runner.run_sync(top, TASK, max_turns=20)
        return len(server.requests), server.served_usage["prompt_tokens"]


def _adk_chain(depth, as_tool):
    """Google ADK, both shapes: `sub_agents` (transfer) or `AgentTool` (as a tool)."""
    import asyncio

    pytest.importorskip("google.adk")
    from google.adk.agents import LlmAgent
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools.agent_tool import AgentTool
    from google.genai import types

    def search(query: str) -> str:
        """Search a small knowledge base of general facts.

        Args:
            query: What to look up.
        """
        from arena.tools import search as _search

        return _search(query)

    async def drive():
        with MockServer(SCRIPT, arena_tools=["search"]) as server:

            def model():
                return LiteLlm(
                    model="openai/mock-model",
                    api_base=server.base_url,
                    api_key="mock-key",
                    temperature=0.0,
                )

            sub = None
            for name in reversed(STAGES[: depth - 1]):
                wiring = {}
                if sub is not None:
                    wiring = {"tools": [AgentTool(agent=sub)]} if as_tool else {"sub_agents": [sub]}
                sub = LlmAgent(
                    name=name,
                    model=model(),
                    description=f"The {name} stage.",
                    instruction=f"You are the {name}.",
                    **wiring,
                )
            wiring = {"tools": [search]}
            if sub is not None:
                if as_tool:
                    wiring = {"tools": [search, AgentTool(agent=sub)]}
                else:
                    wiring["sub_agents"] = [sub]
            top = LlmAgent(
                name="researcher",
                model=model(),
                instruction="You are the researcher.",
                **wiring,
            )
            runner = Runner(app_name="a", agent=top, session_service=InMemorySessionService())
            session = await runner.session_service.create_session(app_name="a", user_id="u")
            message = types.Content(role="user", parts=[types.Part(text=TASK)])
            async for _ in runner.run_async(
                user_id="u", session_id=session.id, new_message=message
            ):
                pass
            return len(server.requests), server.served_usage["prompt_tokens"]

    return asyncio.run(drive())


def _pydantic_ai_delegation(depth):
    """Pydantic AI *agent delegation*: a tool whose body awaits a nested agent run.

    A third, independent sub-agent-as-tool implementation. It shares no code with
    smolagents or ADK and is written differently again — there is no
    `managed_agents` or `AgentTool` wrapper, just an ordinary async tool that
    happens to call `await sub.run(...)` — which is what makes it a real test of
    whether 2N is the mechanism or a coincidence of two libraries.

    The nested runs share one `RunUsage`, which is the library's documented way to
    make a delegating agent's cost include its sub-agents'. The budget is
    deliberately generous: a shared `request_limit` trips partway down a deep
    chain, and what is being measured here is the law, not the cap.
    """
    pytest.importorskip("pydantic_ai")
    from openai import AsyncOpenAI
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
    from pydantic_ai.providers.openai import OpenAIProvider
    from pydantic_ai.usage import RunUsage, UsageLimits

    with MockServer(SCRIPT, arena_tools=["search"]) as server:
        model = OpenAIChatModel(
            "mock-model",
            provider=OpenAIProvider(
                openai_client=AsyncOpenAI(base_url=server.base_url, api_key="mock-key")
            ),
        )
        settings = OpenAIChatModelSettings(temperature=0.0)
        usage = RunUsage()

        def agent(role):
            return Agent(
                model,
                system_prompt=f"The {role} stage.",
                model_settings=settings,
                output_type=str,
            )

        roles = ["researcher", *STAGES[: depth - 1]]
        agents = [agent(role) for role in roles]

        @agents[0].tool_plain
        def search(query: str) -> str:
            """Search a small knowledge base of general facts."""
            from arena.tools import search as _search

            return _search(query)

        # Each agent gets a tool named after the next one down the chain, so the
        # mock recognises it as a delegate the same way it recognises smolagents'
        # managed agent and ADK's AgentTool: an advertised name the arena never
        # declared.
        for parent, child_agent, child in zip(agents[:-1], agents[1:], roles[1:], strict=True):

            def make(child_agent=child_agent):
                async def delegate(task: str) -> str:
                    return str((await child_agent.run(task, usage=usage)).output)

                return delegate

            parent.tool_plain(name=child, description=f"The {child} stage.")(make())

        agents[0].run_sync(TASK, usage=usage, usage_limits=UsageLimits(request_limit=40))
        return len(server.requests), server.served_usage["prompt_tokens"]


def _adk_sub_agents(depth):
    return _adk_chain(depth, as_tool=False)


def _adk_agent_tool(depth):
    return _adk_chain(depth, as_tool=True)


def _n_plus_one(n):
    return n + 1


def _n_plus_two(n):
    # At one role nobody delegates, so there is no return hop to pay for.
    return n + 1 if n == 1 else n + 2


def _two_n(n):
    return 2 * n


# name -> (measure function, expected calls for N roles, how it delegates)
MECHANISMS = {
    "openai_agents handoffs": (_openai_handoffs, _n_plus_one, "speaker swap"),
    "google_adk sub_agents": (_adk_sub_agents, _n_plus_two, "transfer, returns to parent"),
    "smolagents managed_agents": (_smolagents_managed, _two_n, "sub-agent as a tool"),
    "google_adk AgentTool": (_adk_agent_tool, _two_n, "sub-agent as a tool"),
    "pydantic_ai delegation": (_pydantic_ai_delegation, _two_n, "sub-agent as a tool"),
}

# The three sub-agent-as-tool implementations, in three libraries that share no
# code. Kept as a list because every claim about "the mechanism" below is really
# a claim about all of these agreeing.
AS_TOOL = ["smolagents managed_agents", "google_adk AgentTool", "pydantic_ai delegation"]


@pytest.mark.parametrize("mechanism", list(MECHANISMS))
@pytest.mark.parametrize("depth", DEPTHS)
def test_each_mechanism_follows_its_law(mechanism, depth):
    """Every delegation implementation here has an exact, mechanical cost in calls."""
    expected = MECHANISMS[mechanism][1](depth)
    calls, _ = _measure(mechanism, depth)
    assert calls == expected, (
        f"{mechanism}: {depth} role(s) cost {calls} calls, expected {expected}"
    )


def test_the_sub_agent_law_replicates_across_three_libraries():
    """2N is a property of the mechanism, not of any one library.

    smolagents, Google ADK and Pydantic AI share no code, and they express this
    shape three different ways — a `managed_agents` list, an `AgentTool` wrapper,
    and an ordinary async tool whose body happens to `await sub.run(...)`. They
    agree at every depth.

    Two implementations were a pattern; three in three libraries, one of which is
    not a delegation *feature* at all, is the claim docs/multi-agent.md rests on:
    the cost comes from a sub-agent's reply being a **tool result** rather than
    the end of the run, so every delegator pays a second call to say something of
    its own afterwards. Nothing about that depends on the library.
    """
    measured = {name: [_measure(name, d)[0] for d in DEPTHS] for name in AS_TOOL}
    law = [2 * d for d in DEPTHS]
    assert all(calls == law for calls in measured.values()), measured


def test_handoff_is_not_one_thing():
    """Two libraries call it a transfer and they do not cost the same.

    ADK returns control to the parent when the sub-agent finishes, so the parent
    speaks again — one extra call the OpenAI Agents SDK never makes. Asserted
    because "we use handoffs" reads like a single design decision and is not.
    """
    swap = [_measure("openai_agents handoffs", d)[0] for d in DEPTHS]
    transfer = [_measure("google_adk sub_agents", d)[0] for d in DEPTHS]
    assert swap != transfer, "the two transfer implementations no longer differ"
    # Same at one role (nobody delegates), one call apart from two roles on.
    assert swap[0] == transfer[0]
    assert all(t - s == 1 for s, t in zip(swap[1:], transfer[1:], strict=True)), (swap, transfer)


def test_the_choice_inside_one_framework_outweighs_the_choice_between_frameworks():
    """ADK offers both shapes, and they diverge faster than the libraries do.

    This is the practical headline: at four roles ADK's own two mechanisms are
    further apart than its transfer is from the OpenAI SDK's.
    """
    deepest = DEPTHS[-1]
    within_adk = abs(
        _measure("google_adk AgentTool", deepest)[0] - _measure("google_adk sub_agents", deepest)[0]
    )
    between_libraries = abs(
        _measure("google_adk sub_agents", deepest)[0]
        - _measure("openai_agents handoffs", deepest)[0]
    )
    assert within_adk > between_libraries, (within_adk, between_libraries)


def _growth(mechanism):
    """(call growth, prompt growth) from one role to the deepest chain measured."""
    base_calls, base_prompt = _measure(mechanism, 1)
    deep_calls, deep_prompt = _measure(mechanism, DEPTHS[-1])
    return deep_calls / base_calls, deep_prompt / base_prompt


@pytest.mark.parametrize(
    "mechanism", ["openai_agents handoffs", "google_adk sub_agents", "smolagents managed_agents"]
)
def test_prompt_compounds_where_the_conversation_keeps_growing(mechanism):
    """Three of the five compound in prompt faster than in calls. Two do not.

    `google_adk AgentTool` and `pydantic_ai delegation` are deliberately
    excluded, and that exclusion is the finding rather than a caveat — see the
    test below. An earlier version of this file asserted the compounding for all
    four mechanisms it then knew, which was over-general: it held for the two
    measured when it was written and broke on the first new one. It is stated
    this way now so a sixth mechanism has somewhere honest to land.
    """
    call_growth, prompt_growth = _growth(mechanism)
    assert prompt_growth > call_growth, (
        f"{mechanism}: prompt grew {prompt_growth:.2f}x against {call_growth:.2f}x the calls"
    )


def test_you_pay_in_calls_or_in_prompt_but_not_the_same_one():
    """The two ADK mechanisms trade off in *opposite* directions.

    Same library, same model, same task, so nothing else can explain it:

        sub_agents (transfer)   6 calls, 7375 prompt tokens
        AgentTool  (as a tool)  8 calls, 1722 prompt tokens

    A transfer keeps one conversation and every agent sees all of it, so the
    prompt compounds — 15.4x from one role to four, against 3x the calls. A
    sub-agent starts a *fresh* conversation, so the prompt stays nearly flat and
    the calls compound instead — the only mechanism here where prompt grows
    *slower* than call count.

    Which matters more depends on your provider's pricing, and the call-count law
    alone would point you the wrong way: `AgentTool` costs a third more calls and
    a quarter of the prompt.
    """
    transfer_calls, transfer_prompt = _measure("google_adk sub_agents", DEPTHS[-1])
    tool_calls, tool_prompt = _measure("google_adk AgentTool", DEPTHS[-1])
    assert tool_calls > transfer_calls, (tool_calls, transfer_calls)
    assert tool_prompt < transfer_prompt, (tool_prompt, transfer_prompt)
    # And the direction of compounding is opposite, not merely the totals.
    assert _growth("google_adk sub_agents")[1] > _growth("google_adk sub_agents")[0]
    tool_call_growth, tool_prompt_growth = _growth("google_adk AgentTool")
    assert tool_prompt_growth < tool_call_growth, (tool_prompt_growth, tool_call_growth)


def test_a_fresh_conversation_only_helps_if_the_per_agent_prompt_is_small():
    """smolagents restarts context too, and still compounds. Why is worth stating.

    All three sub-agent-as-tool implementations start each sub-agent fresh, so
    none accumulates transcript, and they share a call law exactly. Their prompts
    do not behave the same:

        google_adk AgentTool     479 1126 1423 1722   prompt 3.59x / calls 4.00x
        pydantic_ai delegation   430 1056 1318 1581   prompt 3.68x / calls 4.00x
        smolagents managed_agents 2367 5859 9311 13441 prompt 5.68x / calls 4.00x

    Two of the three land in the same place. smolagents is the outlier by a
    factor of eight in absolute prompt, and it is not the mechanism doing it:
    every fresh sub-agent carries its own ~4 KB templated system prompt, the same
    scaffolding behind the 3.90x single-agent overhead in docs/overhead.md.
    Restarting the conversation only saves you money if there is not much to
    re-send.

    With one comparison this was suggestive. With a second independent
    implementation agreeing with ADK it is the library, isolated.
    """
    flat = ["google_adk AgentTool", "pydantic_ai delegation"]
    smol_calls, smol_prompt = _growth("smolagents managed_agents")
    for mechanism in flat:
        calls, prompt = _growth(mechanism)
        assert calls == smol_calls, f"{mechanism} no longer shares the 2N call law"
        assert prompt < calls, f"{mechanism}: prompt {prompt:.2f}x is no longer flatter than calls"
        assert prompt < smol_prompt, (
            f"{mechanism} prompt growth {prompt:.2f}x is no longer below smolagents' "
            f"{smol_prompt:.2f}x — the outlier was supposed to be the template, not the mechanism"
        )
    assert smol_prompt > smol_calls, (smol_prompt, smol_calls)
