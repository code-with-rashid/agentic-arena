"""Versioned educational evidence. Raw observations remain distinct from claims."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import platform
import subprocess

SCHEMA = "arena.evidence/v1"


@dataclass
class ActionEvent:
    run_id: str
    item_id: str
    call_id: str
    actor: str
    kind: str  # attempt, decision, effect, response, error, usage
    value: object
    parent_id: str | None = None
    delegation_id: str | None = None
    schema: str = SCHEMA

    def record(self):
        if self.kind not in {"attempt", "decision", "effect", "response", "error", "usage"}:
            raise ValueError("unknown event kind")
        return asdict(self)


def provenance(
    *,
    command: list[str],
    mode: str,
    configuration: dict,
    files: list[Path],
    repetitions: int = 1,
    exclusions: list[str] | None = None,
):
    if mode not in {"offline-fixture", "mock", "subscription-functional", "native-api"}:
        raise ValueError("explicit evidence mode required")

    def git(*args):
        result = subprocess.run(["git", *args], capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else "unavailable"

    return {
        "schema": SCHEMA,
        "command": command,
        "commit": git("rev-parse", "HEAD"),
        "tracked_changes": git("diff", "--name-only", "HEAD"),
        "mode": mode,
        "configuration": configuration,
        "repetitions": repetitions,
        "python": platform.python_version(),
        "identities": {p.as_posix(): sha256(p.read_bytes()).hexdigest() for p in files},
        "exclusions": exclusions or [],
    }


def audit(events: list[dict], actual_effects: list[str], expected_calls: list[str]) -> dict:
    """Compare trace against separately read sink and issued call IDs."""
    kinds = {
        kind: [e for e in events if e["kind"] == kind]
        for kind in ("attempt", "decision", "effect", "response")
    }
    complete = all(
        sorted(e["call_id"] for e in kinds[k]) == sorted(expected_calls)
        for k in ("attempt", "decision", "response")
    )
    reported = sorted(str(e["value"]) for e in kinds["effect"])
    return {"trace_complete": complete, "effects_match": reported == sorted(actual_effects)}
