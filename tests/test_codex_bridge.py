"""Bridge contract checks are offline; real Codex runs are explicit CLI actions."""

import json
import subprocess
import urllib.error
import urllib.request

import pytest

from arena.config import ArenaConfig
from arena.llm.client import ChatClient
from arena.llm.codex_bridge import BridgeBackendError, CodexBackend, CodexBridge
from arena.tools import specs_for


def _request(server, body, key=None):
    req = urllib.request.Request(
        server.base_url + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key or server.api_key}",
        },
    )
    return urllib.request.urlopen(req, timeout=5)


def test_models_endpoint_requires_key_and_identifies_bridge_model():
    with CodexBridge("test-model", backend=lambda request: pytest.fail("unused")) as server:
        req = urllib.request.Request(
            server.base_url + "/models",
            headers={"Authorization": f"Bearer {server.api_key}"},
        )
        payload = json.loads(urllib.request.urlopen(req, timeout=5).read())
        assert payload["data"] == [
            {"id": "test-model", "object": "model", "created": 0, "owned_by": "codex-bridge"}
        ]
        req = urllib.request.Request(server.base_url + "/models")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=5)
        assert exc.value.code == 401


def test_bridge_roundtrips_tool_calls_and_observed_usage():
    seen = []

    def backend(request):
        seen.append(request)
        return {
            "content": "",
            "tool_calls": [{"name": "calculator", "arguments": '{"expr":"17*23+4"}'}],
        }, {"input_tokens": 123, "output_tokens": 45}

    with CodexBridge("test-model", backend=backend) as server:
        client = ChatClient(server.base_url, server.api_key, "test-model")
        response = client.chat(
            [{"role": "user", "content": "Calculate 17*23+4"}], tools=specs_for(["calculator"])
        )
    assert response.tool_calls[0]["name"] == "calculator"
    assert json.loads(response.tool_calls[0]["arguments"]) == {"expr": "17*23+4"}
    assert response.tool_calls[0]["id"].startswith("call_")
    assert response.finish_reason == "tool_calls"
    assert (client.prompt_tokens, client.completion_tokens) == (123, 45)
    assert seen[0]["tools"] == specs_for(["calculator"])


@pytest.mark.parametrize(
    "extra",
    [
        {"stream": True},
        {"model": "different"},
        {"stop": ["END"]},
        {"messages": []},
        {"tools": [{"type": "not-a-function"}]},
    ],
)
def test_unsupported_requests_never_call_codex(extra):
    def backend(request):
        pytest.fail("invalid requests must not consume subscription usage")

    with (
        CodexBridge("test-model", backend=backend) as server,
        pytest.raises(urllib.error.HTTPError) as exc,
    ):
        _request(
            server,
            {"model": "test-model", "messages": [{"role": "user", "content": "hi"}], **extra},
        )
    assert exc.value.code == 400


def test_key_required_before_reading_request():
    with (
        CodexBridge("test-model", backend=lambda request: pytest.fail("unauthorized")) as server,
        pytest.raises(urllib.error.HTTPError) as exc,
    ):
        _request(server, {}, key="wrong")
    assert exc.value.code == 401


@pytest.mark.parametrize(
    "failure,status",
    [
        (BridgeBackendError("process_exit_1"), 502),
        (RuntimeError("private-details"), 502),
        (subprocess.TimeoutExpired("codex", 1), 504),
    ],
)
def test_backend_failures_are_bounded_and_do_not_leak(failure, status):
    def backend(request):
        raise failure

    with (
        CodexBridge("test-model", backend=backend) as server,
        pytest.raises(urllib.error.HTTPError) as exc,
    ):
        _request(server, {"model": "test-model", "messages": [{"role": "user", "content": "hi"}]})
    assert not server.lock.locked()
    assert exc.value.code == status
    body = exc.value.read()
    assert b"private-details" not in body
    if isinstance(failure, BridgeBackendError):
        assert failure.code.encode() in body


def test_codex_backend_uses_login_and_stdin_without_shell(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "codex")
    monkeypatch.setenv("OPENAI_API_KEY", "local-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:8765/v1")
    monkeypatch.setenv("CODEX_API_KEY", "unwanted-key")

    def execute(command, **kwargs):
        assert command[0:2] == ["codex", "exec"]
        assert "--ephemeral" in command and "read-only" in command
        assert "--ignore-user-config" in command
        assert command[-1] == "-"
        assert not kwargs.get("shell")
        assert "OPENAI_API_KEY" not in kwargs["env"]
        assert "OPENAI_BASE_URL" not in kwargs["env"]
        assert "CODEX_API_KEY" not in kwargs["env"]
        assert "hello" in kwargs["input"]
        events = [
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": '{"content":"hello","tool_calls":[]}'},
            },
            {"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 3}},
        ]
        return subprocess.CompletedProcess(command, 0, "\n".join(json.dumps(e) for e in events), "")

    monkeypatch.setattr(subprocess, "run", execute)
    result, usage = CodexBackend("test-model")({"messages": [{"role": "user", "content": "hello"}]})
    assert result["content"] == "hello"
    assert usage["input_tokens"] == 12


def test_codex_run_is_marked_and_cannot_publish_live_scorecard(tmp_path, monkeypatch):
    from arena import runner, scorecard

    def backend(self, request):
        return {"content": "395", "tool_calls": []}, {"input_tokens": 12, "output_tokens": 3}

    monkeypatch.setattr("shutil.which", lambda name: "codex")
    monkeypatch.setattr(CodexBackend, "__call__", backend)
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(scorecard, "RUNS_DIR", tmp_path)
    record = runner.run(
        "tool_use",
        ["vanilla"],
        config=ArenaConfig(mode="codex", model="test-model"),
        only={"tu-01"},
    )
    assert record["mode"] == "codex"
    assert record["model"] == "test-model"
    assert record["bridge"]["temperature_applied"] is False
    assert record["pricing"] == {"input_per_m": 0, "output_per_m": 0}
    assert not record["frameworks"][0]["items"][0]["passed"], (
        "the bridge must not invent tool evidence"
    )
    path = scorecard.write_scorecard(record)
    assert path.is_relative_to(tmp_path / "codex-scorecards")
    assert "functional testing only" in path.read_text(encoding="utf-8")
