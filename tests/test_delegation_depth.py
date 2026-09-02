"""How does delegation cost scale with the depth of the chain?

`docs/multi-agent.md` measured three roles and said plainly that two points do
not establish a curve. This measures one to five, for the two model-decided
mechanisms, and both turn out to follow an exact law:

    roles                1     2     3     4     5
    ---------------------------------------------------
    handoff  (calls)     2     3     4     5     6      = N + 1
    sub-agent (calls)    2     4     6     8    10      = 2N

    handoff  (prompt)  452   907  1362  1883  2470
    sub-agent (prompt) 2350  5833  9285 13415 18343

Exact at every depth, and both laws fall straight out of the mechanism:

  * A **handoff** swaps the speaker. Each agent talks once, and the last one
    answers, so a chain of N costs N calls plus the researcher's tool call.
  * A **sub-agent invoked as a tool** hands a *value* back to a manager that is
    still running, so every delegator spends one call to delegate and another to
    produce its own final answer once the sub-agent returns. Each intermediate
    level costs 2, the top costs 3 (a tool call, a delegation, an answer), the
    leaf costs 1 — which is 2N.

**The gap is N - 1 extra model calls and it never stops growing.** At three roles
it is 6 against 4; at five, 10 against 6. Choosing sub-agents over handoffs is
not a fixed premium, it is a slope.

Prompt tokens grow faster than call count in *both* — normalised against each
framework's own single-agent cost, five roles cost 7.80x the prompt for a
sub-agent chain and 5.46x for a handoff chain, against 5x and 3x the calls. Each
stage re-sends its own scaffolding *and* carries more accumulated context than
the stage before it. That was the other open prediction in multi-agent.md.

Absolute prompt numbers are not comparable across the two columns — smolagents
starts from a 3.77x baseline (docs/overhead.md), which is why the growth is
normalised rather than compared raw.

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

# Deliberately generic. The point is the shape of the chain, not the roles - the
# real three-role pipelines live in frameworks/*_multi and carry the arena's
# wording.
STAGES = ["writer", "editor", "checker", "approver"]
TASK = "Write a brief about the Eiffel Tower."
DEPTHS = [1, 2, 3, 4]


def _managed_agent_calls(depth):
    """LLM calls for a chain of `depth` roles built with smolagents managed_agents."""
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


def _handoff_calls(depth):
    """LLM calls for a chain of `depth` roles built with OpenAI Agents handoffs."""
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


@pytest.mark.parametrize("depth", DEPTHS)
def test_a_sub_agent_chain_costs_two_calls_per_role(depth):
    """2N, exactly: every delegator answers as well as delegates."""
    calls, _ = _managed_agent_calls(depth)
    assert calls == 2 * depth, f"{depth} roles cost {calls} calls, expected {2 * depth}"


@pytest.mark.parametrize("depth", DEPTHS)
def test_a_handoff_chain_costs_one_call_per_role(depth):
    """N + 1: each agent talks once, and the last one answers."""
    calls, _ = _handoff_calls(depth)
    assert calls == depth + 1, f"{depth} roles cost {calls} calls, expected {depth + 1}"


def test_the_gap_between_the_two_mechanisms_widens_with_depth():
    """The premium for sub-agents is a slope, not a constant.

    The single most useful thing on this page for someone choosing between the
    two, and the reason it is asserted rather than described: if a future version
    of either library changed this, every depth-3 number in the docs would still
    look right while the advice built on it had quietly become wrong.
    """
    gaps = []
    for depth in DEPTHS:
        sub, _ = _managed_agent_calls(depth)
        swap, _ = _handoff_calls(depth)
        gaps.append(sub - swap)
    assert gaps == [depth - 1 for depth in DEPTHS], gaps
    assert gaps == sorted(gaps) and gaps[-1] > gaps[0], f"gap did not widen with depth: {gaps}"


@pytest.mark.parametrize(
    "measure",
    [
        pytest.param(_managed_agent_calls, id="sub-agent"),
        pytest.param(_handoff_calls, id="handoff"),
    ],
)
def test_prompt_cost_grows_faster_than_call_count(measure):
    """Later stages carry more context than earlier ones, so cost compounds.

    Normalised against each mechanism's own single-agent run, because smolagents
    starts from a 3.77x baseline and the raw totals are not comparable.
    """
    base_calls, base_prompt = measure(1)
    deep_calls, deep_prompt = measure(DEPTHS[-1])
    call_growth = deep_calls / base_calls
    prompt_growth = deep_prompt / base_prompt
    assert prompt_growth > call_growth, (
        f"prompt grew {prompt_growth:.2f}x against {call_growth:.2f}x the calls — "
        f"the compounding claim in docs/multi-agent.md would be wrong"
    )
