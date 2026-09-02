"""The mock renders a scripted answer as a delegation call for handoff clients.

Model-decided delegation (OpenAI Agents SDK `handoffs`) only happens if the model
chooses it, and a scripted mock never chooses anything. Without this the handoff
adapter would never delegate and would silently report the single-agent numbers —
a green scorecard measuring the wrong thing.

So the scripted decision "the research is done, now write it up" is rendered as a
transfer for clients that offer one, exactly as it is rendered as `final_answer`
for clients that end by calling a tool. See docs/multi-agent.md.
"""

from arena.llm.client import ChatClient
from arena.llm.mockserver import MockScript, MockServer

SCRIPT = MockScript(
    {
        "default": {
            "turns": [
                {"tool_calls": [{"name": "search", "arguments": {"query": "Eiffel Tower"}}]},
                {"content": "The finished brief."},
            ]
        }
    }
)


def _tool(name):
    return {"type": "function", "function": {"name": name, "parameters": {}}}


def _chat(server, messages, tools):
    client = ChatClient(base_url=server.base_url, api_key="k", model="mock-model")
    return client.chat(messages, tools=tools)


USER = [{"role": "user", "content": "Brief me on the Eiffel Tower"}]
# One assistant turn already taken, so the script is at the content turn.
AFTER_SEARCH = USER + [
    {"role": "assistant", "content": None},
    {"role": "tool", "tool_call_id": "1", "content": "[Eiffel Tower] 330 metres."},
]


def test_content_turn_becomes_a_transfer_for_a_handoff_client():
    with MockServer(SCRIPT) as server:
        resp = _chat(server, AFTER_SEARCH, [_tool("search"), _tool("transfer_to_writer")])
    assert resp.tool_calls, "a handoff client must be asked to delegate, not answered"
    assert resp.tool_calls[0]["name"] == "transfer_to_writer"


def test_the_last_agent_in_the_chain_answers():
    """No mock-side state: an agent offering no transfer simply gets the brief.

    This is what makes the accommodation terminate. If it needed to remember who
    had already delegated, a chain would either loop or stop early.
    """
    with MockServer(SCRIPT) as server:
        resp = _chat(server, AFTER_SEARCH, [])
    assert not resp.tool_calls
    assert resp.content == "The finished brief."


def test_a_turn_with_work_left_is_never_turned_into_a_transfer():
    """Handing off before the scripted tool call would change the decision.

    The mock restates the scripted decision in the client's protocol; it does not
    get to invent a different one.
    """
    with MockServer(SCRIPT) as server:
        resp = _chat(server, USER, [_tool("search"), _tool("transfer_to_writer")])
    assert resp.tool_calls[0]["name"] == "search"


def test_a_single_agent_client_is_unaffected():
    """The accommodation must be invisible to every adapter that does not delegate."""
    with MockServer(SCRIPT) as server:
        resp = _chat(server, AFTER_SEARCH, [_tool("search")])
    assert not resp.tool_calls
    assert resp.content == "The finished brief."
