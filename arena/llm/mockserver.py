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


def _prompt_tokens(req: dict[str, Any]) -> int:
    """Estimate the billable prompt: the messages **and** the tool schemas.

    Counting only `messages` was a real distortion. A provider bills for the tool
    definitions too, and they are not small — for the two shared arena tools the
    schema block is larger than the whole conversation on the first turn. Worse,
    leaving it out erased the one framework difference mock mode can legitimately
    measure: every framework describes the *same* two tools, but they serialise
    them differently, and that spread is a real cost difference.

    Control fields (`model`, `temperature`, `stream`, `tool_choice`) are excluded
    because a provider does not bill for them.
    """
    billable = json.dumps(req.get("messages", [])) + json.dumps(req.get("tools", []) or [])
    return _estimate_tokens(billable)


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


def _looks_like_react(req: dict[str, Any]) -> bool:
    """Is this client driving a text ReAct loop rather than native tool calls?

    Not every framework uses OpenAI function calling. CrewAI's agent executor,
    for example, advertises no tools and instead asks the model for
    `Thought:/Action:/Action Input:` text, stopping at `Observation:`. Handing
    such a client a native `tool_calls` message gives it `content: None`, which
    it cannot parse.

    That is a fact about the framework worth recording in the feature matrix —
    but it must not decide who can be benchmarked. The mock therefore renders the
    *same scripted decision* in whichever protocol the client asked for, so every
    framework still faces an identical sequence of model choices.
    """
    if req.get("tools"):
        return False
    stop = req.get("stop") or []
    if isinstance(stop, str):
        stop = [stop]
    return any("observation" in str(s).lower() for s in stop)


def _build_react_message(turn: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Render a scripted turn as ReAct text.

    The prompt already ends with a dangling `Thought:`, so this is a
    *continuation* of that line — re-emitting the `Thought:` label would double
    it and the parser would not find the action.
    """
    tool_calls = turn.get("tool_calls")
    if tool_calls:
        call = tool_calls[0]
        args = call.get("arguments", {})
        args_json = args if isinstance(args, str) else json.dumps(args)
        text = (
            f" I should use the {call['name']} tool.\n"
            f"Action: {call['name']}\n"
            f"Action Input: {args_json}"
        )
    else:
        text = f" I now know the final answer\nFinal Answer: {turn.get('content', '')}"
    return {"role": "assistant", "content": text}, "stop"


FINAL_ANSWER_TOOL = "final_answer"


def _wants_final_answer_tool(req: dict[str, Any]) -> bool:
    """Does this client end its loop by *calling a tool* rather than by replying?

    smolagents advertises its own `final_answer` tool and treats a plain content
    reply as "the model did not finish" - it keeps looping until it runs out of
    steps. Serving it a bare content turn would burn the whole iteration budget
    on every item and make its token and LLM-call numbers meaningless, even
    though the text checks would still pass.

    Same principle as `_looks_like_react`: the scripted *decision* is identical
    for everyone, only its wire format follows the client.
    """
    for spec in req.get("tools") or []:
        if spec.get("function", {}).get("name") == FINAL_ANSWER_TOOL:
            return True
    return False


def _as_final_answer_call(turn: dict[str, Any]) -> dict[str, Any]:
    """Rewrite a content turn as a `final_answer` tool call."""
    if turn.get("tool_calls"):
        return turn
    return {
        "tool_calls": [
            {"name": FINAL_ANSWER_TOOL, "arguments": {"answer": turn.get("content", "")}}
        ]
    }


HANDOFF_PREFIX = "transfer_to_"


def _handoff_tool(req: dict[str, Any]) -> str | None:
    """The delegation tool this client is offering, if any.

    Handoff-style multi-agent (OpenAI Agents SDK `handoffs`) is *model-decided*:
    the framework exposes a `transfer_to_<agent>` tool and the model chooses to
    call it. A scripted mock never spontaneously chooses anything, so without
    this a handoff adapter simply never delegates and there is nothing to
    measure - it would silently report the single-agent numbers.

    So the scripted decision "the research is done, now produce the brief" is
    rendered as a transfer for clients that offer one, exactly as it is rendered
    as `final_answer` for clients that end by calling a tool. The decision is the
    same for everyone; only its wire format follows the client.

    This terminates on its own without the mock tracking any state: after a
    handoff the receiving agent is the one talking, and it advertises its own
    handoffs or none. The last agent in a chain offers no transfer, so it
    answers. A single-agent adapter never advertises one and is unaffected.
    """
    for spec in req.get("tools") or []:
        name = spec.get("function", {}).get("name", "")
        if name.startswith(HANDOFF_PREFIX):
            return str(name)
    return None


def _as_handoff_call(turn: dict[str, Any], tool: str) -> dict[str, Any]:
    """Rewrite a content turn as a delegation call to `tool`.

    Only content turns: a turn that still wants a tool has work left to do, and
    handing off before it would change the scripted decision rather than restate
    it. The brief itself is not thrown away - the next agent is served the same
    content turn once it stops offering a transfer.
    """
    if turn.get("tool_calls"):
        return turn
    return {"tool_calls": [{"name": tool, "arguments": {}}]}


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

        if _looks_like_react(req):
            # A ReAct client keeps the whole transcript in one growing prompt and
            # feeds tool results back as "Observation:" text rather than as
            # `role: tool` messages, so count those instead of assistant turns.
            served = sum(str(m.get("content", "")).lower().count("observation:") for m in messages)
            turn = script.turn_for(scenario, served)
            message, finish_reason = _build_react_message(turn)
        else:
            turn = script.turn_for(scenario, assistant_turns)
            # Delegation first: a handoff is a step *before* the answer, whereas
            # `final_answer` is how the answer itself is delivered. A client
            # offering both hands off now and answers after, which is the order a
            # real run would take.
            handoff = _handoff_tool(req)
            if handoff:
                turn = _as_handoff_call(turn, handoff)
            elif _wants_final_answer_tool(req):
                turn = _as_final_answer_call(turn)
            message, finish_reason = _build_message(turn)

        completion_text = message.get("content") or json.dumps(message.get("tool_calls", []))
        prompt_tokens = _prompt_tokens(req)
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
