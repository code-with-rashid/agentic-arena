"""Offline reliability lab: persistent effects, approval, retry and cancellation."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing, suppress
from pathlib import Path


class Sink:
    """Independent fixture service. Transaction binds operation ID to payload."""

    def __init__(self, path: Path):
        self.path = path
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS effects (id TEXT PRIMARY KEY, payload TEXT)")

    def execute(self, operation: str, payload: str) -> str:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM effects WHERE id=?", (operation,)).fetchone()
            if row:
                if row[0] != payload:
                    raise ValueError("operation ID reused with different payload")
                return "replayed"
            db.execute("INSERT INTO effects VALUES (?, ?)", (operation, payload))
        return "applied"

    def effects(self) -> list:
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute("SELECT id, payload FROM effects ORDER BY id").fetchall()


def worker(directory: Path, *, approved: bool, crash: bool = False) -> str:
    """Checkpoint is separate from the sink to expose the crash window."""
    sink = Sink(directory / "sink.sqlite")
    if not approved:
        return "rejected"
    checkpoint = directory / "checkpoint.json"
    if checkpoint.exists():
        return "completed"
    result = sink.execute("operation-1", "synthetic booking")
    if crash:
        os._exit(23)  # Actual process death AFTER the fixture committed.
    temporary = checkpoint.with_suffix(".tmp")
    temporary.write_text(json.dumps({"operation": "operation-1", "status": "completed"}))
    temporary.replace(checkpoint)
    return result


async def bounded(call, *, attempts=3, attempt_timeout=0.1, task_timeout=0.5):
    """Only transient failures retry; cancellation propagates through finally blocks."""
    if attempts < 1 or min(attempt_timeout, task_timeout) <= 0:
        raise ValueError("positive budgets required")
    async with asyncio.timeout(task_timeout):
        for attempt in range(attempts):
            try:
                async with asyncio.timeout(attempt_timeout):
                    return await call()
            except (TimeoutError, ConnectionError):
                if attempt + 1 == attempts:
                    raise
                await asyncio.sleep(min(0.01 * 2**attempt, 0.05))


async def cancellation_demo():
    started, cleaned = asyncio.Event(), asyncio.Event()

    async def work():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    task = asyncio.create_task(bounded(work))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    return cleaned.is_set()


def demo() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        assert worker(path, approved=False) == "rejected"
        assert Sink(path / "sink.sqlite").effects() == []
        command = [
            sys.executable,
            "-m",
            "examples.harness.reliability",
            "--worker",
            directory,
            "--approved",
        ]
        crashed = subprocess.run([*command, "--crash"], timeout=10, capture_output=True)
        assert crashed.returncode == 23
        assert not (path / "checkpoint.json").exists()
        restarted = subprocess.run(command, timeout=10, capture_output=True, text=True)
        assert restarted.returncode == 0, restarted.stderr
        effects = Sink(path / "sink.sqlite").effects()
        assert len(effects) == 1
        return {
            "mode": "offline-fixture",
            "crash_exit": crashed.returncode,
            "restart": restarted.stdout.strip(),
            "actual_effects": len(effects),
            "cancellation_cleanup": asyncio.run(cancellation_demo()),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--crash", action="store_true")
    args = parser.parse_args()
    print(
        worker(args.worker, approved=args.approved, crash=args.crash)
        if args.worker
        else json.dumps(demo(), indent=2)
    )
