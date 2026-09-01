"""A zero-dependency, OpenAI-compatible mock LLM server.

It replays a scripted conversation so the whole harness can run in CI with no API
key and no network. It is NOT a model: it does not reason about the prompt beyond a
substring match to pick a scenario, and it emits exactly the turns the arena's
`mock_script.json` tells it to. Mock-mode pass rates only prove that an adapter
wires the model, the tools, and the loop together correctly.

Run standalone:
    python -m arena.llm.mockserver --script arenas/tool_use/mock_script.json --port 8756
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class MockScript:
    def __init__(self, data: dict[str, Any]):
        self.scenarios: list[dict[str, Any]] = data.get("scenarios", [])
        self.default: dict[str, Any] = data.get(
            "default", {"turns": [{"content": "I don't know."}]}
        )

    @classmethod
    def load(cls, path: str | Path) -> MockScript:
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def pick(self, first_user_message: str) -> dict[str, Any]:
        haystack = first_user_message.lower()
        for scenario in self.scenarios:
            match = str(scenario.get("match", "")).lower()
            if match and match in haystack:
                return scenario
        return self.default

    @staticmethod
    def turn_for(scenario: dict[str, Any], assistant_turns_so_far: int) -> dict[str, Any]:
        turns = scenario.get("turns", [])
        if not turns:
            return {"content": "I don't know."}
        idx = min(assistant_turns_so_far, len(turns) - 1)
        return turns[idx]


def _build_message(turn: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Return (assistant message dict, finish_reason)."""
    tool_calls = turn.get("tool_calls")
    if tool_calls:
        formatted = []
        for call in tool_calls:
            args = call.get("arguments", {})
            formatted.append(
                {
                    "id": call.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": args if isinstance(args, str) else json.dumps(args),
                    },
                }
            )
        return {"role": "assistant", "content": None, "tool_calls": formatted}, "tool_calls"
    return {"role": "assistant", "content": turn.get("content", "")}, "stop"


class _Handler(BaseHTTPRequestHandler):
    server_version = "AgentArenaMock/0.1"

    # silence per-request logging; the harness prints its own progress
    def log_message(self, *_args: Any) -> None:  # noqa: D401
        return

    def _send_json(self, obj: dict[str, Any], status: int = 200) -> None:
        blob = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/models"):
            self._send_json({"object": "list", "data": [{"id": "mock-model", "object": "model"}]})
            return
        self._send_json({"status": "ok"})

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.endswith("/chat/completions"):
            self._send_json({"error": {"message": f"unhandled path {self.path}"}}, status=404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json({"error": {"message": "invalid JSON"}}, status=400)
            return

        # Keep every request so tests can assert what an adapter actually put on
        # the wire — which tools it advertised, what system prompt it sent.
        self.server.requests.append(req)  # type: ignore[attr-defined]

        messages = req.get("messages", [])
        first_user = next(
            (str(m.get("content", "")) for m in messages if m.get("role") == "user"), ""
        )
        assistant_turns = sum(1 for m in messages if m.get("role") == "assistant")

        script: MockScript = self.server.script  # type: ignore[attr-defined]
        scenario = script.pick(first_user)
        turn = script.turn_for(scenario, assistant_turns)
        message, finish_reason = _build_message(turn)

        completion_text = message.get("content") or json.dumps(message.get("tool_calls", []))
        prompt_tokens = _estimate_tokens(json.dumps(messages))
        completion_tokens = _estimate_tokens(completion_text)

        response = {
            "id": f"chatcmpl-mock-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.get("model", "mock-model"),
            "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

        if req.get("stream"):
            self._send_stream(response)
        else:
            self._send_json(response)

    def _send_stream(self, response: dict[str, Any]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        base = {
            "id": response["id"],
            "object": "chat.completion.chunk",
            "created": response["created"],
            "model": response["model"],
        }
        message = response["choices"][0]["message"]
        finish_reason = response["choices"][0]["finish_reason"]
        if message.get("tool_calls"):
            delta: dict[str, Any] = {"role": "assistant", "tool_calls": []}
            for i, tc in enumerate(message["tool_calls"]):
                delta["tool_calls"].append(
                    {
                        "index": i,
                        "id": tc["id"],
                        "type": "function",
                        "function": tc["function"],
                    }
                )
        else:
            delta = {"role": "assistant", "content": message.get("content", "")}
        self._write_chunk(
            {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]}
        )
        self._write_chunk(
            {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}]}
        )
        self.wfile.write(b"data: [DONE]\n\n")

    def _write_chunk(self, obj: dict[str, Any]) -> None:
        self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())


class MockServer:
    """Threaded context manager wrapping the mock HTTP server."""

    def __init__(self, script: MockScript | str | Path, host: str = "127.0.0.1", port: int = 0):
        self.script = script if isinstance(script, MockScript) else MockScript.load(script)
        self._httpd = ThreadingHTTPServer((host, port), _Handler)
        self._httpd.script = self.script  # type: ignore[attr-defined]
        self._httpd.requests = []  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None

    @property
    def requests(self) -> list[dict[str, Any]]:
        """Every chat-completions request body received, in order."""
        return self._httpd.requests  # type: ignore[attr-defined,no-any-return]

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    @property
    def base_url(self) -> str:
        host, port = self._httpd.server_address
        return f"http://{host}:{port}/v1"

    def start(self) -> MockServer:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)

    def __enter__(self) -> MockServer:
        return self.start()

    def __exit__(self, *_exc: Any) -> None:
        self.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agentic-arena mock LLM server.")
    parser.add_argument("--script", required=True, help="Path to a mock_script.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8756)
    args = parser.parse_args()
    server = MockServer(args.script, host=args.host, port=args.port).start()
    print(f"mock LLM listening on {server.base_url} (script: {args.script})")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
