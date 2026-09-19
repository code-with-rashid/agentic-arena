"""Compare retry identity designs using a shared task and an independent sink."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from arena.evidence import ActionEvent, audit, provenance
from examples.harness.reliability import Sink

DATASET = {"id": "lost-ack-v1", "task": "one synthetic booking", "attempts": 2}


def compare() -> dict:
    rows = []
    for stable in (True, False):
        with tempfile.TemporaryDirectory() as directory:
            sink = Sink(Path(directory) / "sink.sqlite")
            events, calls = [], []
            start = time.perf_counter()
            for attempt in range(DATASET["attempts"]):
                call = str(attempt)
                calls.append(call)
                operation = "booking" if stable else f"booking-{attempt}"

                def event(kind, value, events=events, call=call):
                    events.append(
                        ActionEvent(
                            "retry-comparison", DATASET["id"], call, "lesson", kind, value
                        ).record()
                    )

                event("attempt", operation)
                event("decision", {"decision": "allow", "reason": "synthetic approved task"})
                status = sink.execute(operation, DATASET["task"])
                if status == "applied":
                    event("effect", operation)
                # Simulate loss of first acknowledgement without erasing sink evidence.
                event("response", "acknowledgement lost" if attempt == 0 else status)
                if attempt == 0:
                    event("error", "synthetic acknowledgement loss")
            actual = [row[0] for row in sink.effects()]
            rows.append(
                {
                    "variant": "stable-key" if stable else "fresh-key",
                    "correctness": len(actual) == 1,
                    "useful_work_completed": bool(actual),
                    "actual_effects": actual,
                    "attempts": len(calls),
                    "latency_s": time.perf_counter() - start,
                    "tokens": None,
                    "cost": None,
                    "safety": "not assessed",
                    "audit": audit(events, actual, calls),
                    "events": events,
                }
            )
    return {
        "provenance": provenance(
            command=["python", "-m", "examples.harness.evaluate"],
            mode="offline-fixture",
            configuration=DATASET,
            files=[
                Path(__file__),
                Path("examples/harness/reliability.py"),
                Path("arena/evidence.py"),
            ],
            exclusions=[
                "model reasoning",
                "provider token cost",
                "distributed exactly-once",
                "general security",
            ],
        ),
        "results": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
