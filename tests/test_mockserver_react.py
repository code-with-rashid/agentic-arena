"""The mock must serve the same scripted decisions to a text-ReAct client.

Not every framework uses OpenAI function calling — CrewAI's agent executor
advertises no tools and asks for `Thought:/Action:/Action Input:` text instead.
The mock renders the same scripted turn in whichever protocol the client asked
for, so protocol choice does not decide who can be benchmarked.
"""

import json

from arena.llm.client import ChatClient
from arena.llm.mockserver import MockScript, MockServer, _looks_like_react

SCRIPT = MockScript(
    {
        "scenarios": [
            {
                "match": "17 * 23",
                "turns": [
                    {"tool_calls": [{"name": "calculator", "arguments": {"expr": "17 * 23 + 4"}}]},
                    {"content": "17 * 23 + 4 = 395."},
                ],
            }
        ]
    }
)

REACT_STOP = ["\nObservation:"]


def test_react_detection():
    assert _looks_like_react({"stop": REACT_STOP})
    assert _looks_like_react({"stop": "\nObservation:"})
    # advertising native tools wins, even alongside a stop sequence
    assert not _looks_like_react({"stop": REACT_STOP, "tools": [{"function": {"name": "x"}}]})
    assert not _looks_like_react({})


def _post(server, messages, **extra):
    import urllib.request

    body = {"model": "mock-model", "messages": messages, **extra}
    req = urllib.request.Request(
        f"{server.base_url}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def test_react_client_gets_the_action_as_text_then_the_final_answer():
    with MockServer(SCRIPT) as server:
        first = _post(
            server, [{"role": "user", "content": "What is 17 * 23 + 4?"}], stop=REACT_STOP
        )
        # A continuation of the prompt's dangling "Thought:" — re-emitting the
        # label would double it and the parser would miss the action.
        assert not first.lstrip().startswith("Thought:")
        assert "Action: calculator" in first
        assert '"expr": "17 * 23 + 4"' in first

        # Feeding the tool result back as an Observation advances the script.
        second = _post(
            server,
            [
                {"role": "user", "content": "What is 17 * 23 + 4?"},
                {"role": "assistant", "content": first},
                {"role": "user", "content": "Observation: 395"},
            ],
            stop=REACT_STOP,
        )
        assert "Final Answer: 17 * 23 + 4 = 395." in second


def test_native_client_still_gets_native_tool_calls():
    """The ReAct path must not change what a function-calling client receives."""
    with MockServer(SCRIPT) as server:
        client = ChatClient(base_url=server.base_url, api_key="k", model="mock-model")
        resp = client.chat(
            [{"role": "user", "content": "What is 17 * 23 + 4?"}],
            tools=[{"type": "function", "function": {"name": "calculator", "parameters": {}}}],
        )
        assert resp.tool_calls and resp.tool_calls[0]["name"] == "calculator"
        assert "Action:" not in (resp.content or "")
