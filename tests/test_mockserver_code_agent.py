"""The mock must serve the same scripted decisions to a smolagents `CodeAgent`.

`CodeAgent` also advertises no tools and also feeds results back as
`Observation:` text, so it looks like a text-ReAct client — but it wants a
**Python code blob** (`<code> … </code>` that calls the tool functions), not an
`Action: / Action Input:` pair, and its parser rejects the latter outright. The
mock renders the scripted turn as a `<code>` block for such a client, so a
`CodeAgent` faces the identical sequence of model choices as everyone else.
"""

import json
import urllib.request

from arena.llm.client import ChatClient
from arena.llm.mockserver import (
    MockScript,
    MockServer,
    _looks_like_code_agent,
    _looks_like_react,
)

SCRIPT = MockScript(
    {
        "scenarios": [
            {
                "match": "eiffel tower",
                "turns": [
                    {
                        "tool_calls": [
                            {"name": "search", "arguments": {"query": "Eiffel Tower", "k": 3}}
                        ]
                    },
                    {"content": "The Eiffel Tower was completed in 1889."},
                ],
            }
        ]
    }
)

CODE_STOP = ["Observation:", "Calling tools:", "</code>"]
REACT_STOP = ["\nObservation:"]


def test_code_agent_detection():
    assert _looks_like_code_agent({"stop": CODE_STOP})
    assert _looks_like_code_agent({"stop": "</code>"})
    # a plain text-ReAct stop list is not a CodeAgent
    assert not _looks_like_code_agent({"stop": REACT_STOP})
    assert not _looks_like_code_agent({})
    # advertising native tools wins
    assert not _looks_like_code_agent({"stop": CODE_STOP, "tools": [{"function": {"name": "x"}}]})
    # and a CodeAgent must not also be routed down the bare ReAct path — it is
    # checked first in do_POST, but the stop list overlaps, so pin the intent
    assert _looks_like_react({"stop": CODE_STOP})  # overlap is real...
    assert _looks_like_code_agent({"stop": CODE_STOP})  # ...code check must win


def _post(server, messages, **extra):
    body = {"model": "mock-model", "messages": messages, **extra}
    req = urllib.request.Request(
        f"{server.base_url}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def test_code_agent_gets_a_code_blob_then_final_answer():
    with MockServer(SCRIPT) as server:
        first = _post(
            server,
            [{"role": "user", "content": "When was the Eiffel Tower built?"}],
            stop=CODE_STOP,
        )
        assert "<code>" in first and "</code>" in first
        # the scripted search call, as Python kwargs — not a dict, per CodeAgent rule 3
        assert "search(query='Eiffel Tower', k=3)" in first
        assert "Action:" not in first

        second = _post(
            server,
            [
                {"role": "user", "content": "When was the Eiffel Tower built?"},
                {"role": "assistant", "content": first},
                {"role": "user", "content": "Observation: [Eiffel Tower] completed 1889"},
            ],
            stop=CODE_STOP,
        )
        assert "final_answer('The Eiffel Tower was completed in 1889.')" in second


def test_react_client_still_gets_action_text():
    """A stop list without `</code>` is a text-ReAct client and gets `Action:`."""
    with MockServer(SCRIPT) as server:
        first = _post(
            server,
            [{"role": "user", "content": "When was the Eiffel Tower built?"}],
            stop=REACT_STOP,
        )
        assert "Action: search" in first
        assert "<code>" not in first


def test_native_client_unaffected():
    with MockServer(SCRIPT) as server:
        client = ChatClient(base_url=server.base_url, api_key="k", model="mock-model")
        resp = client.chat(
            [{"role": "user", "content": "When was the Eiffel Tower built?"}],
            tools=[{"type": "function", "function": {"name": "search", "parameters": {}}}],
        )
        assert resp.tool_calls and resp.tool_calls[0]["name"] == "search"
        assert "<code>" not in (resp.content or "")
