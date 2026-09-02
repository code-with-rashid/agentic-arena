import json
import urllib.request

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


def _stream(server, **extra):
    """Drive the streaming path directly and return the parsed SSE chunks.

    No adapter here streams — measured, and pinned below — so this path has no
    other coverage. Going over raw HTTP rather than through `ChatClient` is the
    point: the client does not stream either.
    """
    body = {
        "model": "mock-model",
        "messages": [{"role": "user", "content": "What is 17 * 23 + 4?"}],
        "stream": True,
        **extra,
    }
    request = urllib.request.Request(
        f"{server.base_url}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - localhost mock
        raw = response.read().decode()
    return [
        json.loads(line[6:])
        for line in raw.splitlines()
        if line.startswith("data: ") and line[6:] != "[DONE]"
    ]


def test_a_streamed_response_carries_usage_only_when_asked_for_it():
    """The provider contract this mock stands in for, and an instrument hazard.

    A real OpenAI-compatible endpoint sends no `usage` on a streamed response
    unless the client sets `stream_options: {"include_usage": true}`. The mock
    used to send none either way, which would have made an adapter that streamed
    *without* asking look correct here and report zero tokens against a real
    provider — with every correctness check still green, because the answer is
    unaffected.

    Both halves matter. Sending usage unconditionally would hide the missing
    option; sending it never makes the streaming path untestable.
    """
    with MockServer(str(SCRIPT)) as server:
        silent = _stream(server)
        asked = _stream(server, stream_options={"include_usage": True})

    assert not any(c.get("usage") for c in silent), (
        "usage arrived without `include_usage` — an adapter that forgot the "
        "option would pass here and report nothing against a real provider"
    )
    usage = [c["usage"] for c in asked if c.get("usage")]
    assert len(usage) == 1, f"expected exactly one usage chunk, got {len(usage)}"
    assert usage[0]["prompt_tokens"] > 0 and usage[0]["completion_tokens"] > 0, usage[0]
    # The same numbers the non-streaming path bills, so `served_usage` — which
    # tests/test_usage_accounting.py holds every adapter against — means the
    # same thing whichever path a framework takes.
    assert usage[0]["total_tokens"] == usage[0]["prompt_tokens"] + usage[0]["completion_tokens"]


def test_a_streamed_tool_call_survives_the_chunking():
    """The scripted decision must be the same whether it is streamed or not.

    Nothing exercises this today, which is exactly why it is worth pinning: the
    first adapter to turn streaming on would otherwise discover it.
    """
    with MockServer(str(SCRIPT)) as server:
        chunks = _stream(
            server,
            tools=[{"type": "function", "function": {"name": "calculator", "parameters": {}}}],
        )
    calls = [
        tc
        for chunk in chunks
        for choice in chunk.get("choices", [])
        for tc in (choice.get("delta", {}).get("tool_calls") or [])
    ]
    assert calls, "the scripted tool call vanished on the streaming path"
    assert calls[0]["function"]["name"] == "calculator"
    finishes = [
        c["finish_reason"]
        for chunk in chunks
        for c in chunk.get("choices", [])
        if c.get("finish_reason")
    ]
    assert finishes == ["tool_calls"], finishes
