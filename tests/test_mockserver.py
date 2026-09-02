from arena.config import REPO_ROOT
from arena.llm.client import ChatClient
from arena.llm.mockserver import MockServer

SCRIPT = REPO_ROOT / "arenas" / "tool_use" / "mock_script.json"


def test_mock_serves_scripted_tool_call_then_answer():
    with MockServer(str(SCRIPT)) as server:
        client = ChatClient(base_url=server.base_url, api_key="mock-key", model="mock-model")

        first = client.chat(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "What is 17 * 23 + 4?"},
            ],
            tools=[{"type": "function", "function": {"name": "calculator", "parameters": {}}}],
        )
        assert first.tool_calls and first.tool_calls[0]["name"] == "calculator"

        second = client.chat(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "What is 17 * 23 + 4?"},
                {"role": "assistant", "content": None, "tool_calls": []},
                {"role": "tool", "tool_call_id": "call_0", "content": "395"},
            ]
        )
        assert "395" in second.content
        assert client.prompt_tokens > 0


_BIG_TOOL = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Evaluate an arithmetic expression and return the result.",
        "parameters": {
            "type": "object",
            "properties": {"expr": {"type": "string", "description": "The expression."}},
            "required": ["expr"],
        },
    },
}


def test_prompt_tokens_include_the_tool_schemas():
    """A provider bills for the tool definitions, so the mock must count them.

    Counting only `messages` also erased the one framework difference mock mode
    can legitimately measure: every adapter is handed the same two tools and
    serialises them differently.
    """
    messages = [{"role": "user", "content": "What is 17 * 23 + 4?"}]
    with MockServer(str(SCRIPT)) as server:
        bare = ChatClient(base_url=server.base_url, api_key="mock-key", model="mock-model")
        bare.chat(messages)

        armed = ChatClient(base_url=server.base_url, api_key="mock-key", model="mock-model")
        armed.chat(messages, tools=[_BIG_TOOL])

    assert armed.prompt_tokens > bare.prompt_tokens, (
        "the tool schema was not counted; mock token and cost numbers would "
        "understate every run and hide per-framework serialisation overhead"
    )
