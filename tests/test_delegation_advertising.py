"""What does *offering* a delegate cost, before anyone delegates?

`docs/multi-agent.md` reports that 94% of what a native handoff costs is the
`transfer_to_*` schema riding on every request rather than the transfer itself —
you pay to advertise a handoff, not to take it. That was measured against one
mechanism. This file asks the same question of a structurally different one:
smolagents' `managed_agents`, where a sub-agent is invoked *as a tool* rather
than by a transfer that swaps the speaker.

It generalises, and it is much more expensive. Offering one sub-agent, with no
delegation happening at all:

    0 sub-agents offered   system 3311  tools  518   total 3829
    1                      system 4102  tools  982   total 5084   (+1255)
    2                      system 4498  tools 1455   total 5953   (+869)
    3                      system 4900  tools 1934   total 6834   (+881)

The first one costs ~1255 characters and each further one ~875, on *every*
request. The step down after the first is a ~385-char preamble ("You can also
give tasks to team members…") that enables delegation at all and is paid once.

The marginal ~875 splits into ~400 characters of prose in the system prompt and
~475 of JSON tool schema — **each sub-agent is described twice**, exactly as
smolagents describes its tools twice (see docs/overhead.md, where the same
double transmission is most of its 3.77× prompt overhead). Against the OpenAI
Agents SDK's 262-char `transfer_to_writer` schema, that is 3.3× more to offer
the same option.

What is gated here are the invariants, not the byte counts: the cost is paid on
every request rather than only the delegating one, it scales with how many
delegates are offered, and offering none costs nothing. The numbers themselves
are findings and live in the docs, following the same rule as `resilience`.
"""

import json

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

ROLES = [
    ("writer", "Writes a brief from research notes."),
    ("editor", "Tightens a draft to three to five sentences."),
    ("checker", "Verifies every number against the research notes."),
]


def _request_size(request):
    """Characters of system prompt plus tool schema — what is resent every turn."""
    system = ""
    for message in request.get("messages", []):
        if message.get("role") != "system":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            system += content
        elif isinstance(content, list):
            system += "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return len(system) + len(json.dumps(request.get("tools") or []))


def _run_with_managed_agents(count):
    """Run one item with `count` sub-agents offered. Returns every request made."""
    smolagents = pytest.importorskip("smolagents")

    @smolagents.tool
    def search(query: str) -> str:
        """Search a small knowledge base.

        Args:
            query: What to look up.
        """
        from arena.tools import search as _search

        return _search(query)

    with MockServer(SCRIPT) as server:
        model = smolagents.OpenAIServerModel(
            model_id="mock-model", api_base=server.base_url, api_key="mock-key"
        )
        managed = [
            smolagents.ToolCallingAgent(
                tools=[], model=model, name=name, description=description, max_steps=3
            )
            for name, description in ROLES[:count]
        ]
        smolagents.ToolCallingAgent(
            tools=[search], model=model, managed_agents=managed, max_steps=4
        ).run("Write a brief about the Eiffel Tower.")
        return list(server.requests)


def test_offering_a_delegate_is_paid_on_every_request():
    """Not just on the request where the model decides to delegate.

    This is the whole finding. If the sub-agent's description were sent only
    when it was about to be used, delegation would be nearly free to offer and
    the advice in docs/multi-agent.md would be wrong.
    """
    requests = _run_with_managed_agents(1)
    assert len(requests) >= 2, "probe never reached a second request"
    advertised = [
        i
        for i, r in enumerate(requests)
        if any(t.get("function", {}).get("name") == "writer" for t in r.get("tools") or [])
    ]
    assert len(advertised) == len(requests), (
        f"the sub-agent was advertised on {len(advertised)} of {len(requests)} requests — "
        f"if it is not on all of them, the cost is not what this file claims"
    )


def test_the_cost_scales_with_how_many_delegates_are_offered():
    """Offer more, pay more, on every request — and offering none costs nothing."""
    sizes = [_request_size(_run_with_managed_agents(n)[0]) for n in range(3)]
    assert sizes[0] < sizes[1] < sizes[2], f"not monotonic in delegates offered: {sizes}"
    # The marginal agent is what a supervisor pays per option it holds open. Wide
    # bounds on purpose: the exact figure is a finding, this only pins that a
    # further delegate is neither free nor wildly out of line with the first.
    marginal = sizes[2] - sizes[1]
    assert 200 < marginal < 3000, f"marginal cost of a second delegate looks wrong: {marginal}"


def test_a_sub_agent_is_described_twice():
    """Once as a JSON tool schema and once in prose, like smolagents' tools.

    This is *why* offering a delegate costs 3.3× more here than a handoff's
    schema alone, and it is the same double transmission that drives the 3.77×
    prompt overhead in docs/overhead.md. Asserted rather than described, because
    it is the mechanism the published number rests on.
    """
    first = _run_with_managed_agents(1)[0]
    schemas = json.dumps(first.get("tools") or [])
    system = ""
    for message in first.get("messages", []):
        if message.get("role") == "system":
            content = message.get("content", "")
            system += (
                content
                if isinstance(content, str)
                else "".join(p.get("text", "") for p in content if isinstance(p, dict))
            )
    assert "writer" in schemas, "the sub-agent was not advertised as a tool schema"
    assert "writer" in system, "the sub-agent was not also described in the system prompt"
    assert ROLES[0][1] in system, (
        "the sub-agent's description is not restated in prose — if upstream stopped "
        "doing this, the advertising cost reported in the docs has changed"
    )
