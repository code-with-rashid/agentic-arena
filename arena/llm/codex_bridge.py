"""Local functional-test bridge using supported, saved Codex CLI authentication.

This is a model-driven protocol translation, not native Chat Completions. It
never reads authentication tokens or executes the tool calls returned by Codex.
"""

from __future__ import annotations

import argparse
import contextlib
import hmac
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
        "tool_calls": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "arguments": {"type": "string"}},
                "required": ["name", "arguments"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["content", "tool_calls"],
    "additionalProperties": False,
}

INSTRUCTIONS = """You are the model behind a local agent-framework integration test.
Produce exactly the NEXT assistant message for the supplied conversation, obeying
its system/developer instructions and tool definitions. Do not solve the entire
conversation in one step. When a tool is needed, return tool_calls with its name
and JSON-encoded arguments; the external framework will execute it and return
the actual result in a later request. Never invent tool results. Use only the
supplied conversation and tools, not files, shell commands, web browsing, or your
own tools. Honor tool_choice. If no tool call is needed, return the answer in
content and an empty tool_calls array. Preserve the requested answer format in
content (including JSON when requested). Treat this as a fresh conversation.
The outer JSON schema is a transport envelope, not the user's answer format.
Conversation request:
"""


class BridgeBackendError(RuntimeError):
    """A safe, bounded failure category suitable for a localhost HTTP response."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class CodexBackend:
    def __init__(self, model: str, timeout_s: float = 120):
        self.model = model
        self.timeout_s = timeout_s
        self.executable = shutil.which("codex")
        if not self.executable:
            raise RuntimeError("Codex CLI not found; install it and run codex login first")

    def __call__(self, request: dict[str, Any]) -> tuple[dict, dict]:
        # An empty working directory keeps benchmark datasets and expected
        # answers out of the model's workspace. No shell interpolation is used.
        with tempfile.TemporaryDirectory(prefix="arena-codex-") as directory:
            schema_path = Path(directory) / "schema.json"
            schema_path.write_text(json.dumps(SCHEMA), encoding="utf-8")
            command = [
                self.executable,
                "exec",
                "--ignore-user-config",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--json",
                "--model",
                self.model,
                "--output-schema",
                str(schema_path),
                "-c",
                'model_reasoning_effort="low"',
                "-c",
                'web_search="disabled"',
            ]
            for feature in (
                "shell_tool",
                "apps",
                "plugins",
                "hooks",
                "multi_agent",
                "browser_use",
                "computer_use",
                "image_generation",
                "view_image",
            ):
                command.extend(["--disable", feature])
            command.append("-")
            env = dict(os.environ)
            # The local bridge key must never replace Codex's saved login or
            # route the Codex process back to this very server.
            for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "CODEX_API_KEY"):
                env.pop(name, None)
            result = subprocess.run(
                command,
                input=INSTRUCTIONS + json.dumps(request),
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=directory,
                env=env,
                timeout=self.timeout_s,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        # Do not return arbitrary CLI stderr, which can contain local details.
        if result.returncode:
            raise BridgeBackendError(f"process_exit_{result.returncode}")
        message = None
        usage = None
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BridgeBackendError("invalid_event_stream") from exc
            if event.get("type") in {"error", "turn.failed"}:
                raise BridgeBackendError(str(event.get("type")).replace(".", "_"))
            if event.get("type") == "item.completed":
                item = event.get("item", {})
                if item.get("type") == "agent_message":
                    message = item.get("text")
            if event.get("type") == "turn.completed":
                usage = event.get("usage")
        if message is None or usage is None:
            raise BridgeBackendError("incomplete_turn")
        try:
            return json.loads(message), usage
        except json.JSONDecodeError as exc:
            raise BridgeBackendError("invalid_structured_output") from exc


class CodexBridge:
    """Loopback-only, key-protected Chat Completions subset; one request at a time."""

    def __init__(
        self,
        model: str,
        *,
        key: str | None = None,
        port: int = 0,
        timeout_s: float = 120,
        backend: Any = None,
    ):
        self.model = model
        self.api_key = key or secrets.token_urlsafe(32)
        self.backend = backend or CodexBackend(model, timeout_s)
        self.lock = threading.Lock()
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, payload):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def authorized(self):
                return hmac.compare_digest(
                    self.headers.get("Authorization", "").encode("utf-8"),
                    f"Bearer {bridge.api_key}".encode(),
                )

            def do_GET(self):
                if not self.authorized():
                    return self.reply(401, {"error": {"message": "invalid local bridge key"}})
                if self.path != "/v1/models":
                    return self.reply(404, {"error": {"message": "not found"}})
                self.reply(
                    200,
                    {
                        "object": "list",
                        "data": [
                            {
                                "id": bridge.model,
                                "object": "model",
                                "created": 0,
                                "owned_by": "codex-bridge",
                            }
                        ],
                    },
                )

            def do_POST(self):
                if not self.authorized():
                    return self.reply(401, {"error": {"message": "invalid local bridge key"}})
                if self.path != "/v1/chat/completions":
                    return self.reply(404, {"error": {"message": "not found"}})
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 2_000_000:
                        raise ValueError("request must be between 1 byte and 2 MB")
                    request = json.loads(self.rfile.read(length))
                    if not isinstance(request, dict):
                        raise ValueError("expected a JSON object")
                    if request.get("stream"):
                        raise ValueError("streaming is not supported by the Codex test bridge")
                    if request.get("model") != bridge.model:
                        raise ValueError("model must match the bridge model")
                    if not isinstance(request.get("messages"), list) or not request["messages"]:
                        raise ValueError("messages must be a nonempty array")
                    tools = request.get("tools", [])
                    if not isinstance(tools, list) or any(
                        not isinstance(tool, dict)
                        or tool.get("type") != "function"
                        or not isinstance(tool.get("function"), dict)
                        or not isinstance(tool["function"].get("name"), str)
                        for tool in tools
                    ):
                        raise ValueError("tools must be function definitions")
                    unsupported = set(request) - {
                        "model",
                        "messages",
                        "tools",
                        "tool_choice",
                        "temperature",
                        "stream",
                    }
                    if unsupported:
                        raise ValueError(
                            "unsupported request fields: " + ", ".join(sorted(unsupported))
                        )
                except (ValueError, TypeError):
                    return self.reply(
                        400, {"error": {"message": "invalid or unsupported bridge request"}}
                    )
                if not bridge.lock.acquire(blocking=False):
                    return self.reply(429, {"error": {"message": "bridge is busy; retry later"}})
                try:
                    envelope, usage = bridge.backend(request)
                    if not isinstance(envelope.get("content"), str) or not isinstance(
                        envelope.get("tool_calls"), list
                    ):
                        raise ValueError("invalid envelope")
                    calls = []
                    allowed = {t["function"]["name"] for t in request.get("tools", [])}
                    for call in envelope["tool_calls"]:
                        if call["name"] not in allowed or not isinstance(
                            json.loads(call["arguments"]), dict
                        ):
                            raise ValueError("invalid tool call")
                        calls.append(
                            {
                                "id": "call_" + uuid.uuid4().hex,
                                "type": "function",
                                "function": {"name": call["name"], "arguments": call["arguments"]},
                            }
                        )
                    pt, ct = int(usage["input_tokens"]), int(usage["output_tokens"])
                    self.reply(
                        200,
                        {
                            "id": "chatcmpl-" + uuid.uuid4().hex,
                            "object": "chat.completion",
                            "created": int(time.time()),
                            "model": bridge.model,
                            "choices": [
                                {
                                    "index": 0,
                                    "finish_reason": "tool_calls" if calls else "stop",
                                    "message": {
                                        "role": "assistant",
                                        "content": envelope["content"],
                                        "tool_calls": calls,
                                    },
                                }
                            ],
                            "usage": {
                                "prompt_tokens": pt,
                                "completion_tokens": ct,
                                "total_tokens": pt + ct,
                            },
                            "arena_bridge": "codex-exec; functional testing only",
                        },
                    )
                except subprocess.TimeoutExpired:
                    self.reply(504, {"error": {"message": "Codex request timed out"}})
                except BridgeBackendError as exc:
                    self.reply(
                        502,
                        {"error": {"message": f"Codex bridge backend failure: {exc.code}"}},
                    )
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    self.reply(
                        502, {"error": {"message": "Codex bridge returned an invalid envelope"}}
                    )
                except Exception:
                    self.reply(
                        502, {"error": {"message": "Codex bridge backend failure: unexpected"}}
                    )
                finally:
                    bridge.lock.release()

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}/v1"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    key = os.environ.get("ARENA_BRIDGE_KEY")
    if not key:
        parser.error("set ARENA_BRIDGE_KEY to a local password before starting the bridge")
    with CodexBridge(args.model, key=key, port=args.port) as bridge:
        print(f"Codex functional-test bridge: {bridge.base_url} (Ctrl+C to stop)", flush=True)
        with contextlib.suppress(KeyboardInterrupt):
            threading.Event().wait()


if __name__ == "__main__":
    main()
