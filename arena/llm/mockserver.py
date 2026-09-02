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
import sys
import threading
import time
import uuid
from collections.abc import Sequence
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


def _advertised(req: dict[str, Any]) -> list[str]:
    """Tool names this client put on the wire, in order."""
    names = []
    for spec in req.get("tools") or []:
        name = spec.get("function", {}).get("name")
        if name:
            names.append(str(name))
    return names


def _already_called(
    req: dict[str, Any], tool: str, arguments: dict[str, Any] | None = None
) -> bool:
    """Has this conversation already made *this* call?

    Read off the transcript rather than tracked in the server, so the mock stays
    stateless and two runs cannot contaminate each other.

    Keyed on the arguments as well as the name, because the two handoff shapes
    put the target in different places. One tool per target
    (`transfer_to_writer`, `transfer_to_editor`) is distinguished by name; a
    single tool parameterised by target (`transfer_to_agent(agent_name=…)`, which
    is what Google ADK's `sub_agents` produces) is only distinguished by its
    arguments, and matching on the name alone would stop a chain after its first
    hop. Where a delegation carries the same arguments every time - a sub-agent
    invoked as a tool, handed the same task - this still blocks the repeat.

    Both encodings have to be checked. Most clients send a structured
    `tool_calls` field, but smolagents replays its own calls as assistant
    *content* — `Calling tools: [{'function': {'name': 'editor', ...}}]` — so
    looking only at the field finds nothing and the manager delegates again on
    every turn until its step budget is gone. Matched on the quoted `name` key
    rather than a bare substring, so an agent merely mentioning "editor" in prose
    is not mistaken for having called it.
    """
    wanted = json.dumps(arguments, sort_keys=True) if arguments else None

    def _same_arguments(raw: Any) -> bool:
        if wanted is None:
            return True
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                return False
        return json.dumps(raw, sort_keys=True) == wanted

    needles = (f"'name': '{tool}'", f'"name": "{tool}"')
    for message in req.get("messages", []):
        if message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls") or []:
            function = call.get("function", {})
            if function.get("name") == tool and _same_arguments(function.get("arguments")):
                return True
        content = message.get("content") or ""
        if not isinstance(content, str):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        # The text encoding carries the arguments too, but not in a form worth
        # parsing; a client that replays calls as prose only ever produces the
        # one-tool-per-target shape, where the name is already decisive.
        if any(needle in content for needle in needles):
            return True
    return False


def _holds_no_task_tools(advertised: list[str], arena_tools: list[str] | None) -> bool:
    """Does this client hold *none* of the arena's tools?

    True only for an agent whose whole role is to write or delegate — a
    smolagents managed sub-agent carries `final_answer` and maybe another
    sub-agent, and nothing else. A normal adapter always holds at least one
    arena tool and is never in this state.

    Without a declared tool list to compare against, fall back to "advertises
    nothing but control tools", which is the same question asked more weakly.
    """
    if arena_tools is None:
        return all(
            name == FINAL_ANSWER_TOOL or name.startswith(HANDOFF_PREFIX) for name in advertised
        )
    return not (set(advertised) & set(arena_tools))


def turn_for_client(
    script: MockScript,
    scenario: dict[str, Any],
    turns_so_far: int,
    advertised: list[str],
    arena_tools: list[str] | None,
) -> dict[str, Any]:
    """The first turn at or after `turns_so_far` that this client could perform.

    Normally this is exactly `MockScript.turn_for`. It differs in one narrow
    case: an agent holding none of the arena's tools skips forward past scripted
    tool-call turns to the first content turn.

    That case exists for nested sub-agents. A smolagents managed sub-agent gets
    a *fresh* conversation, so it is served turn 1 — the researcher's `search`
    call — even though the whole point of the writer role is that it has no
    tools. Skipping is what lets one script drive every stage of a pipeline.

    Deliberately **not** the more obvious rule "skip any turn whose tool this
    client did not advertise". That rule breaks the `resilience` arena outright:
    `res-02` scripts a call to a tool that *deliberately* does not exist, and
    skipping it would quietly delete the fault instead of measuring how the
    framework handles it. Requiring the client to hold no arena tools at all
    keeps every normal adapter, and every scripted fault, exactly as it was.
    """
    turns = scenario.get("turns", [])
    if not turns or not _holds_no_task_tools(advertised, arena_tools):
        return script.turn_for(scenario, turns_so_far)
    index = min(turns_so_far, len(turns) - 1)
    while index < len(turns) - 1 and turns[index].get("tool_calls"):
        index += 1
    return turns[index]


HANDOFF_PREFIX = "transfer_to_"

FINAL_ANSWER_TOOLS = (FINAL_ANSWER_TOOL,)


def _delegation_tool(
    req: dict[str, Any], arena_tools: list[str] | None, task: str = ""
) -> tuple[str, dict[str, Any]] | None:
    """A delegate this client is offering that it has not already used, and its arguments.

    Three ways a framework expresses model-decided delegation, and the mock
    recognises all of them:

      * **one tool per target** — `transfer_to_<agent>` swaps the speaker (OpenAI
        Agents SDK `handoffs`). Matched by prefix, always, and takes no arguments.
      * **one tool parameterised by target** — `transfer_to_agent(agent_name=…)`
        (Google ADK `sub_agents`). Also matched by the prefix, but the target
        lives in an `enum` on the parameter, so the call is only distinguishable
        from the previous hop by its arguments.
      * **a sub-agent advertised as an ordinary tool named after itself**
        (smolagents `managed_agents`, ADK `AgentTool`) — which can only be told
        apart from a task tool by knowing what the arena declared, so this half is
        active only when the harness has told the server the arena's tool list.

    "Not already used" is what terminates a nested pipeline. A one-tool-per-target
    handoff chain terminates on its own, because after a transfer the receiving
    agent is the one talking and it offers its own handoffs or none. The other two
    shapes keep advertising the same tool name forever, so without this they would
    delegate on every turn and never answer. Reading it off the transcript keeps
    the server stateless.
    """

    def _candidate(name: str) -> tuple[str, dict[str, Any]] | None:
        arguments = _delegation_arguments(req, name, task)
        if _already_called(req, name, arguments):
            return None
        return name, arguments

    for name in _advertised(req):
        if name.startswith(HANDOFF_PREFIX):
            found = _candidate(name)
            if found:
                return found
    if arena_tools is None:
        return None
    known = set(arena_tools) | set(FINAL_ANSWER_TOOLS)
    for name in _advertised(req):
        if name not in known:
            found = _candidate(name)
            if found:
                return found
    return None


def _delegation_arguments(req: dict[str, Any], tool: str, task: str) -> dict[str, Any]:
    """Fill whatever the delegation tool requires, with the task being delegated.

    A `transfer_to_<agent>` tool takes no arguments — the conversation goes with
    it. A sub-agent advertised as a tool takes the task as a string, because it
    is about to start a *fresh* conversation and this is the only thing it will
    be told.

    Passing the original user message is what a manager delegating this task
    would actually send, and it has a second effect worth naming: the sub-agent's
    new conversation opens with the same question, so the mock picks the same
    scenario for it and the pipeline stays on the same item. Anything else — the
    brief, a summary — would either hand the sub-agent the answer or lose the
    item.
    """
    schema: dict[str, Any] = {}
    for spec in req.get("tools") or []:
        function = spec.get("function", {})
        if function.get("name") == tool:
            schema = function.get("parameters", {}) or {}
            break
    required = schema.get("required") or []
    properties = schema.get("properties") or {}
    arguments: dict[str, Any] = {}
    for name in required:
        spec = properties.get(name, {})
        choices = spec.get("enum")
        if choices:
            # A constrained parameter names the *target*, not the task. Google
            # ADK's `sub_agents` produces a single `transfer_to_agent` tool whose
            # `agent_name` enumerates the agents this stage may hand to, so the
            # only correct value is one of them - filling it with the task text
            # fails with "Transfer target agent '<the whole question>' not found".
            arguments[name] = choices[0]
        elif spec.get("type") == "string":
            arguments[name] = task
        else:
            arguments[name] = {}
    return arguments


def _as_handoff_call(
    turn: dict[str, Any], tool: str, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Rewrite a content turn as a delegation call to `tool`.

    Only content turns: a turn that still wants a tool has work left to do, and
    handing off before it would change the scripted decision rather than restate
    it. The brief itself is not thrown away - the next agent is served the same
    content turn once it stops offering a transfer.
    """
    if turn.get("tool_calls"):
        return turn
    return {"tool_calls": [{"name": tool, "arguments": arguments or {}}]}


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

    def _send_json(
        self, obj: dict[str, Any], status: int = 200, headers: dict[str, str] | None = None
    ) -> None:
        blob = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
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

        # Transport faults come first: a provider that returns 429 never reads
        # the prompt, so a failed attempt must not consume a scripted turn or
        # land in `requests`. `attempts` counts what actually reached the wire,
        # which is the difference between "the framework retried" and "the
        # framework gave up".
        attempt = len(self.server.attempts)  # type: ignore[attr-defined]
        self.server.attempts.append(time.perf_counter())  # type: ignore[attr-defined]
        faults: list[int] = self.server.faults  # type: ignore[attr-defined]
        status = faults[attempt] if attempt < len(faults) else 200
        # A hung provider, which is a different failure from a fast error: the
        # request is accepted and then nothing comes back. Whether the caller
        # gives up on its own is what `request_timeout_s` exists to decide.
        # Applied only to attempts that were going to be served, so `faults` and
        # `stall_seconds` stay independent knobs rather than compounding.
        stall: float = self.server.stall_seconds  # type: ignore[attr-defined]
        if stall and status == 200:
            time.sleep(stall)
        if status != 200:
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            kind = "rate_limit_error" if status == 429 else "server_error"
            # A real provider usually tells you how long to wait. Whether a
            # framework honours that, ignores it, or invents its own backoff is
            # the difference between a predictable delay and an unpredictable
            # one - see docs/transport.md.
            retry_after = self.server.retry_after  # type: ignore[attr-defined]
            headers = (
                {"Retry-After": str(retry_after)}
                if retry_after is not None and status in (429, 503)
                else None
            )
            self._send_json(
                {"error": {"message": f"injected {status}", "type": kind}},
                status=status,
                headers=headers,
            )
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
            advertised = _advertised(req)
            arena_tools = getattr(self.server, "arena_tools", None)
            # Normally just `turn_for`. A sub-agent holding none of the arena's
            # tools skips forward to the first content turn, so one script can
            # drive every stage of a nested pipeline.
            turn = turn_for_client(script, scenario, assistant_turns, advertised, arena_tools)
            # Delegation first: a handoff is a step *before* the answer, whereas
            # `final_answer` is how the answer itself is delivered. A client
            # offering both hands off now and answers after, which is the order a
            # real run would take.
            delegate = _delegation_tool(req, arena_tools, first_user)
            if delegate:
                turn = _as_handoff_call(turn, delegate[0], delegate[1])
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

        # Ground truth for usage. Every published comparison rests on adapters
        # reporting their own cost honestly, and nothing was checking that: an
        # adapter that under-reports posts a better number and still passes every
        # item. `MockServer.served_usage` is what the wire actually carried, so a
        # framework's self-report can be held against it.
        self.server.served.append(  # type: ignore[attr-defined]
            {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
        )

        if req.get("stream"):
            # A real provider sends usage on a streamed response only when the
            # client asks for it, so the mock must too - otherwise an adapter
            # that forgets `include_usage` looks correct here and reports zero
            # tokens against a real one.
            include_usage = bool((req.get("stream_options") or {}).get("include_usage"))
            self._send_stream(response, include_usage=include_usage)
        else:
            self._send_json(response)

    def _send_stream(self, response: dict[str, Any], include_usage: bool = False) -> None:
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
        if include_usage:
            # OpenAI's shape: one final chunk with an empty `choices` list and
            # the usage for the whole response. Same numbers the non-streaming
            # path bills, so `served_usage` means the same thing either way.
            self._write_chunk({**base, "choices": [], "usage": response["usage"]})
        self.wfile.write(b"data: [DONE]\n\n")

    def _write_chunk(self, obj: dict[str, Any]) -> None:
        self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())


class _Server(ThreadingHTTPServer):
    """Quiet about clients that walked away.

    `stall_seconds` exists so a caller can give up on us, which means the
    response is written to a socket the client already closed. That is the
    expected outcome of a timeout test, not an error, and the default handler
    prints a full traceback per occurrence.
    """

    daemon_threads = True

    def handle_error(self, request, client_address):  # noqa: D102 - stdlib override
        if not isinstance(sys.exc_info()[1], OSError):
            super().handle_error(request, client_address)


class MockServer:
    """Threaded context manager wrapping the mock HTTP server."""

    def __init__(
        self,
        script: MockScript | str | Path,
        host: str = "127.0.0.1",
        port: int = 0,
        arena_tools: Sequence[str] | None = None,
        faults: Sequence[int] = (),
        retry_after: int | None = None,
        stall_seconds: float = 0.0,
    ):
        """`arena_tools` is the arena's declared tool list, when the caller knows it.

        It is what lets the server tell a *delegate* advertised as an ordinary
        tool (smolagents `managed_agents` names the tool after the sub-agent)
        from a task tool the arena asked for. Without it only the explicit
        `transfer_to_*` shape is recognised, which is what a bare `MockServer` in
        a test gets and is deliberately the narrower behaviour.

        `faults` is one HTTP status per attempt — `[429, 429, 200]` fails the
        first two attempts and serves the third normally, and anything past the
        end of the list succeeds. It exists because `resilience` scripts the
        *model* misbehaving and nothing here scripted the *gateway* doing so,
        which is what real deployments actually hit. A faulted attempt never
        reads the prompt, so it consumes no scripted turn and does not appear in
        `requests`; `attempts` counts everything that reached the wire.

        `retry_after` sets a `Retry-After` header on injected 429s and 503s, the
        way a real provider tells you how long to wait. Left at `None` there is
        no header and every backoff is the client's own invention, which is the
        default because it is the harsher case.

        `stall_seconds` holds every request open for that long before answering -
        a hung provider rather than a failing one, which is what
        `ArenaConfig.request_timeout_s` exists to bound.
        """
        self.script = script if isinstance(script, MockScript) else MockScript.load(script)
        # `_Server` sets `daemon_threads`: a stalled request outlives the client
        # that abandoned it, and without that `stop()` joins those sleeping
        # threads and every timeout measurement pays the full stall on the way out.
        self._httpd = _Server((host, port), _Handler)
        self._httpd.script = self.script  # type: ignore[attr-defined]
        self._httpd.requests = []  # type: ignore[attr-defined]
        self._httpd.served = []  # type: ignore[attr-defined]
        self._httpd.arena_tools = list(arena_tools) if arena_tools is not None else None  # type: ignore[attr-defined]
        self._httpd.faults = list(faults)  # type: ignore[attr-defined]
        self._httpd.retry_after = retry_after  # type: ignore[attr-defined]
        self._httpd.stall_seconds = float(stall_seconds)  # type: ignore[attr-defined]
        self._httpd.attempts = []  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None

    @property
    def requests(self) -> list[dict[str, Any]]:
        """Every chat-completions request body *served*, in order.

        Attempts rejected by an injected fault are not here — the gateway never
        read them. Use `attempts` to count what reached the wire.
        """
        return self._httpd.requests  # type: ignore[attr-defined,no-any-return]

    @property
    def attempts(self) -> list[float]:
        """Monotonic timestamp of every attempt, faulted or served.

        The gaps between them are the framework's backoff, which is as much a
        finding as the retry count: a library that eventually succeeds by
        sleeping for two minutes has not really handled the rate limit.
        """
        return self._httpd.attempts  # type: ignore[attr-defined,no-any-return]

    @property
    def served_usage(self) -> dict[str, int]:
        """What this server actually billed, summed over every response.

        The ground truth for `tests/test_usage_accounting.py`. An adapter's own
        `AgentResult` numbers are a *claim*; this is what went over the wire.
        """
        served = self._httpd.served  # type: ignore[attr-defined]
        return {
            "prompt_tokens": sum(s["prompt_tokens"] for s in served),
            "completion_tokens": sum(s["completion_tokens"] for s in served),
            "llm_calls": len(served),
        }

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
