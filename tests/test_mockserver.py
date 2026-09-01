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
