"""Context selection with explicit provenance and scoped durable memory."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Fact:
    source_id: str
    text: str
    required: bool = False

    def render(self) -> str:
        return f"[{self.source_id}] {self.text}\n"


def build_context(facts: list[Fact], budget_chars: int) -> dict:
    """Prioritize obligations, then recent evidence. Budget is characters, not tokens."""
    if budget_chars < 0 or len({f.source_id for f in facts}) != len(facts):
        raise ValueError("nonnegative budget and unique source IDs required")
    selected = [f for f in facts if f.required]
    used = sum(len(f.render()) for f in selected)
    if used > budget_chars:
        raise ValueError("required evidence exceeds budget; fail visibly instead of dropping it")
    for fact in reversed(facts):
        if not fact.required and used + len(fact.render()) <= budget_chars:
            selected.append(fact)
            used += len(fact.render())
    ids = {f.source_id for f in selected}
    return {
        "text": "".join(f.render() for f in facts if f.source_id in ids),
        "sources": [f.source_id for f in facts if f.source_id in ids],
        "omitted": [f.source_id for f in facts if f.source_id not in ids],
        "budget_chars": budget_chars,
    }


class Memory:
    """The caller supplies trusted scope. This store is not authentication middleware."""

    def __init__(self, path: Path):
        self.path = path
        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS facts (tenant TEXT, session TEXT, source TEXT, text TEXT, PRIMARY KEY (tenant,session,source))"
            )

    def put(self, tenant: str, session: str, fact: Fact) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO facts VALUES (?,?,?,?)",
                (tenant, session, fact.source_id, fact.text),
            )

    def retrieve(self, tenant: str, session: str, query: str) -> list[Fact]:
        with closing(sqlite3.connect(self.path)) as db, db:
            rows = db.execute(
                "SELECT source,text FROM facts WHERE tenant=? AND session=? ORDER BY source",
                (tenant, session),
            ).fetchall()
        return [Fact(source, text) for source, text in rows if query.casefold() in text.casefold()]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "memory.sqlite"
        memory = Memory(path)
        memory.put("alice", "task-1", Fact("manual-1", "Budget approval is required."))
        memory.put("bob", "task-1", Fact("private-1", "Budget belongs to Bob."))
        # Reopen from persistent storage, without relying on the original object.
        recovered = Memory(path).retrieve("alice", "task-1", "budget")
        context = build_context([Fact(f.source_id, f.text, True) for f in recovered], 80)
        print(
            json.dumps({"recovered": [asdict(f) for f in recovered], "context": context}, indent=2)
        )


if __name__ == "__main__":
    main()
