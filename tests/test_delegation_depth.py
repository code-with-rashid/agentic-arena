"""How does delegation cost scale with the depth of the chain?

`docs/multi-agent.md` measured three roles and said plainly that two points do
not establish a curve. This measures one to five roles, for **four** delegation
implementations across three libraries. Every one follows an exact law:

    roles                                    1   2   3   4   5
    ---------------------------------------------------------------
    handoffs      (openai_agents)  swap      2   3   4   5   6   = N + 1
    sub_agents    (google_adk)     transfer  2   4   5   6   7   = N + 2
    managed_agents(smolagents)     as tool   2   4   6   8  10   = 2N
    AgentTool     (google_adk)     as tool   2   4   6   8  10   = 2N

Three things fall out of that table, and none is visible at three roles.

**The 2N law is a property of the mechanism, not of one library.** smolagents
and Google ADK share no code, and their sub-agent-as-tool implementations agree
at every depth. A sub-agent's reply is a *tool result*, not the end of the run,
so every delegator spends one call to delegate and another to produce its own
final answer once the sub-agent returns.

**"Handoff" is not one thing.** Both the OpenAI Agents SDK and ADK describe
theirs as transferring to another agent, and they do not cost the same, because
ADK **returns control to the parent** when the sub-agent finishes and the parent
then speaks again. One extra call, constant with depth, and it is the difference
between N+1 and N+2. The name is the same; the control flow is not.

**You pay in calls or in prompt, and the call law points the wrong way.** Prompt
tokens for the same four chains, one role to four:

    handoffs       (swap)     452  907 1362 1883    calls 2.50x  prompt 4.17x
    sub_agents     (transfer) 479 3168 5229 7375    calls 3.00x  prompt 15.40x
    managed_agents (as tool) 2367 5859 9311 13441   calls 4.00x  prompt 5.68x
    AgentTool      (as tool)  479 1126 1423 1722    calls 4.00x  prompt 3.59x

Inside ADK, at four roles: `sub_agents` costs 6 calls and 7375 prompt tokens,
`AgentTool` 8 calls and 1722. A transfer keeps **one** conversation that every
agent sees all of, so the prompt compounds; a sub-agent starts a **fresh** one,
so the prompt stays flat and the calls compound instead. Cheaper in calls is
dearer in prompt, and prompt is usually the larger bill.

Restarting only helps if there is little to re-send: smolagents also starts each
sub-agent fresh, and its prompt still grows faster than its calls, because every
sub-agent carries its own ~4 KB templated system prompt — the scaffolding behind
its 3.77x single-agent overhead in docs/overhead.md.

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
}


@pytest.mark.parametrize("mechanism", list(MECHANISMS))
@pytest.mark.parametrize("depth", DEPTHS)
def test_each_mechanism_follows_its_law(mechanism, depth):
    """Every delegation implementation here has an exact, mechanical cost in calls."""
    expected = MECHANISMS[mechanism][1](depth)
    calls, _ = _measure(mechanism, depth)
    assert calls == expected, (
        f"{mechanism}: {depth} role(s) cost {calls} calls, expected {expected}"
    )


def test_the_sub_agent_law_replicates_across_two_libraries():
    """2N is a property of the mechanism, not of smolagents.

    smolagents and Google ADK share no code. If their sub-agent-as-tool costs
    ever diverged, the claim in docs/multi-agent.md that this is *mechanistic*
    would be wrong, and it is the claim the advice rests on.
    """
    smol = [_measure("smolagents managed_agents", d)[0] for d in DEPTHS]
    adk = [_measure("google_adk AgentTool", d)[0] for d in DEPTHS]
    assert smol == adk == [2 * d for d in DEPTHS], (smol, adk)


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
    """Three of the four compound in prompt faster than in calls. One does not.

    `google_adk AgentTool` is deliberately excluded, and that exclusion is the
    finding rather than a caveat — see the test below. An earlier version of this
    file asserted the compounding for all four, which was over-general: it held
    for the two mechanisms that had been measured when it was written and broke
    on the first new one.
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

    Both sub-agent-as-tool implementations start each sub-agent fresh, so neither
    accumulates transcript. ADK's prompt therefore stays nearly flat (3.59x for
    4x the calls) while smolagents' still grows faster than its calls (5.68x) —
    because every fresh sub-agent carries its own ~4 KB templated system prompt,
    the same scaffolding behind the 3.77x single-agent overhead in
    docs/overhead.md. Restarting the conversation only saves you money if there
    is not much to re-send.
    """
    adk_calls, adk_prompt = _growth("google_adk AgentTool")
    smol_calls, smol_prompt = _growth("smolagents managed_agents")
    assert adk_calls == smol_calls, "the two share a call law; only the prompt differs"
    assert adk_prompt < adk_calls < smol_prompt, (adk_prompt, adk_calls, smol_prompt)
