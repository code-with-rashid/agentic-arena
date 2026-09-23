"""Deterministic approval and restart clinic with independent effect evidence."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Step:
    actor: str
    state: str
    detail: str


def simulate(
    *,
    decision: str = "approve",
    gated: bool = True,
    durable: bool = True,
    stable_operation: bool = True,
    crash: str = "after_effect",
) -> dict:
    if decision not in {"approve", "deny"}:
        raise ValueError("decision must be approve or deny")
    if crash not in {"none", "after_pause", "after_effect"}:
        raise ValueError("unknown crash point")

    timeline = [Step("model", "proposed", "Book room R1 for the requested meeting.")]
    effects = 0
    restarts = 0

    if not gated:
        effects = 1
        timeline.append(Step("tool", "applied", "Advisory approval allowed the booking to run."))
    timeline.append(
        Step("harness", "paused", "The pending operation and approval request are recorded.")
    )

    if crash == "after_pause":
        restarts = 1
        timeline.append(Step("process", "crashed", "The process exits while approval is pending."))
        if not durable:
            timeline.append(Step("harness", "lost", "In-memory pause state cannot be resumed."))
            return _record("lost pending operation", effects, restarts, timeline)
        timeline.append(
            Step("harness", "restored", "A fresh process loads serializable pause state.")
        )

    timeline.append(Step("human", decision, f"The trusted decision is {decision}."))
    if decision == "deny":
        if effects:
            timeline.append(
                Step("oracle", "detected", "The independent sink already contains a booking.")
            )
            return _record("unauthorized effect", effects, restarts, timeline)
        timeline.append(Step("harness", "stopped", "The denied operation is never dispatched."))
        return _record("denied safely", effects, restarts, timeline)

    if not gated:
        timeline.append(
            Step("harness", "completed", "Approval arrives after the effect already happened.")
        )
        return _record("completed without enforcement", effects, restarts, timeline)

    effects = 1
    timeline.append(Step("tool", "applied", "The approved operation commits once."))
    if crash == "after_effect":
        restarts = 1
        timeline.append(
            Step("process", "crashed", "The acknowledgement is lost before checkpointing.")
        )
        if not durable:
            timeline.append(Step("harness", "lost", "Resume state was not durable."))
            return _record("effect committed; run state lost", effects, restarts, timeline)
        timeline.append(
            Step("harness", "restored", "A fresh process retries the pending operation.")
        )
        if stable_operation:
            timeline.append(
                Step("tool", "replayed", "The stable operation ID returns the first receipt.")
            )
            outcome = "resumed without duplication"
        else:
            effects += 1
            timeline.append(
                Step("tool", "duplicated", "A new operation ID creates a second booking.")
            )
            outcome = "duplicate after restart"
    else:
        outcome = "approved once"
    timeline.append(Step("oracle", "verified", f"Independent effect count: {effects}."))
    return _record(outcome, effects, restarts, timeline)


def _record(outcome: str, effects: int, restarts: int, timeline: list[Step]) -> dict:
    return {
        "schema_version": 1,
        "mode": "deterministic-simulation",
        "outcome": outcome,
        "effects": effects,
        "restarts": restarts,
        "timeline": [asdict(step) for step in timeline],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", choices=("approve", "deny"), default="approve")
    parser.add_argument("--gated", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--durable", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--stable-operation", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--crash", choices=("none", "after_pause", "after_effect"), default="after_effect"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            simulate(
                decision=args.decision,
                gated=args.gated,
                durable=args.durable,
                stable_operation=args.stable_operation,
                crash=args.crash,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
