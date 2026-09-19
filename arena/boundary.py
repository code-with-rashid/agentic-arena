"""Synthetic loopback fixture. No host files, credentials or remote targets are used."""

from __future__ import annotations

import json
import threading
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

_endpoint: str | None = None
_run_lock = threading.Lock()


def boundary_action(action: str) -> str:
    """Execute a synthetic action through the fixture policy service."""
    if _endpoint is None:
        return "ERROR: boundary fixture is not configured"
    request = Request(
        _endpoint,
        data=json.dumps({"action": action}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=5) as response:
        return response.read().decode()


@contextmanager
def fixture(case: dict):
    """Single active fixture per process; works across adapter worker threads.

    The endpoint is harness-owned, never accepted from model arguments. This is
    instrumentation, NOT a security boundary against arbitrary Python execution.
    """
    global _endpoint
    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("concurrent boundary runs in one process are unsupported")
    state = {"requests": [], "events": [], "effects": []}
    policy = {a["action"]: a for a in case["actions"]}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            action = request.get("action", "")
            rule = policy.get(action, {"decision": "deny", "reason": "unknown_action"})
            receipt = uuid.uuid4().hex
            response = {
                "receipt": receipt,
                "action": action,
                "decision": rule["decision"],
                "reason": rule["reason"],
            }
            with lock:
                state["requests"].append({"receipt": receipt, "action": action})
                state["events"].append(dict(response))
                if rule["decision"] == "allow":
                    # The synthetic sink is separate from policy event records.
                    state["effects"].append({"receipt": receipt, "action": action})
            body = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = None
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        _endpoint = f"http://127.0.0.1:{server.server_port}/action"
        yield state
    finally:
        _endpoint = None
        if server:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        _run_lock.release()
