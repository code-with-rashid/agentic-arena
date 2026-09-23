"""Deterministic context-budget explorer with explicit selection evidence."""

from __future__ import annotations

import argparse
import json

from examples.harness.context import Fact, build_context

FACTS = [
    Fact("approval", "Never deploy without explicit approval.", True),
    Fact("objective", "Migrate the checkout service to v3."),
    Fact("database-old", "The target database is orders-primary."),
    Fact("discussion", "The team discussed dashboard colors."),
    Fact("database-correction", "Correction: use orders-green, not orders-primary.", True),
    Fact("health", "The v3 staging health check passed."),
    Fact("request", "Prepare the migration plan; do not execute it."),
]

POLICIES = ("full", "recent", "protected", "retrieval", "summary")


def _recent(facts: list[Fact], budget_chars: int) -> list[Fact]:
    selected: list[Fact] = []
    used = 0
    for fact in reversed(facts):
        if used + len(fact.render()) <= budget_chars:
            selected.append(fact)
            used += len(fact.render())
    return list(reversed(selected))


def simulate(policy: str, *, budget_chars: int = 220, query: str = "database") -> dict:
    """Select a fixed workload's context and expose omissions and integrity risks."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    if budget_chars < 0:
        raise ValueError("budget must be nonnegative")

    overflow = False
    failure = None
    if policy == "full":
        selected = FACTS[:]
        overflow = sum(len(f.render()) for f in selected) > budget_chars
    elif policy == "recent":
        selected = _recent(FACTS, budget_chars)
    elif policy == "protected":
        try:
            ids = build_context(FACTS, budget_chars)["sources"]
            selected = [f for f in FACTS if f.source_id in ids]
        except ValueError as exc:
            selected = []
            failure = str(exc)
    elif policy == "retrieval":
        candidates = [f for f in FACTS if f.required or query.casefold() in f.text.casefold()]
        try:
            ids = build_context(candidates, budget_chars)["sources"]
            selected = [f for f in FACTS if f.source_id in ids]
        except ValueError as exc:
            selected = []
            failure = str(exc)
    else:
        compacted = [
            FACTS[0],
            FACTS[4],
            Fact("summary", "Checkout v3 migration planning; staging is healthy; do not execute."),
        ]
        try:
            ids = build_context(compacted, budget_chars)["sources"]
            selected = [f for f in compacted if f.source_id in ids]
        except ValueError as exc:
            selected = []
            failure = str(exc)

    selected_ids = [f.source_id for f in selected]
    omitted_ids = [f.source_id for f in FACTS if f.source_id not in selected_ids]
    used = sum(len(f.render()) for f in selected)
    required = [f.source_id for f in FACTS if f.required]
    missing_required = [source for source in required if source not in selected_ids]
    stale_without_correction = (
        "database-old" in selected_ids and "database-correction" not in selected_ids
    )

    if failure:
        outcome = "failed visibly"
        lesson = (
            "The required obligations do not fit. Increase the budget or shorten them explicitly."
        )
    elif overflow:
        outcome = "budget exceeded"
        lesson = "Full replay preserves evidence but does not obey the configured request budget."
    elif missing_required:
        outcome = "obligation lost"
        lesson = "A recent window can fit while silently dropping an early approval or correction."
    elif stale_without_correction:
        outcome = "stale context"
        lesson = "Selection retained an older fact without the correction that supersedes it."
    elif policy == "summary":
        outcome = "compacted with provenance loss"
        lesson = "Compaction saves space, but the synthetic summary no longer cites every source it replaced."
    else:
        outcome = "bounded context"
        lesson = "Required obligations survived and every omission remains visible by source ID."

    return {
        "schema_version": 1,
        "mode": "deterministic-simulation",
        "policy": policy,
        "budget_chars": budget_chars,
        "query": query,
        "used_chars": used,
        "overflow": overflow,
        "outcome": outcome,
        "selected": selected_ids,
        "omitted": omitted_ids,
        "missing_required": missing_required,
        "lesson": lesson,
        "context": "".join(f.render() for f in selected),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=POLICIES, default="protected")
    parser.add_argument("--budget", type=int, default=220)
    parser.add_argument("--query", default="database")
    args = parser.parse_args()
    print(json.dumps(simulate(args.policy, budget_chars=args.budget, query=args.query), indent=2))


if __name__ == "__main__":
    main()
