"""Deterministic tool-failure lab for exploring harness recovery policies."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

FAILURES = {
    "malformed_arguments": {
        "label": "Malformed tool arguments",
        "kind": "model",
        "retryable": False,
        "effect": "none",
    },
    "unknown_tool": {
        "label": "Unknown tool name",
        "kind": "model",
        "retryable": False,
        "effect": "none",
    },
    "rate_limit": {
        "label": "Provider rate limit (429)",
        "kind": "transport",
        "retryable": True,
        "effect": "none",
    },
    "bad_request": {
        "label": "Provider bad request (400)",
        "kind": "transport",
        "retryable": False,
        "effect": "none",
    },
    "timeout_after_effect": {
        "label": "Timeout after the tool committed",
        "kind": "effect",
        "retryable": True,
        "effect": "committed",
    },
}


@dataclass(frozen=True)
class Step:
    actor: str
    state: str
    detail: str


def simulate(
    failure: str,
    *,
    retries: int = 1,
    stable_key: bool = True,
    reconcile: bool = True,
) -> dict:
    """Return an explainable run record; no provider or external effect is used."""
    if failure not in FAILURES:
        raise ValueError(f"unknown failure: {failure}")
    if retries < 0 or retries > 3:
        raise ValueError("retries must be between 0 and 3")

    fault = FAILURES[failure]
    timeline = [Step("model", "proposed", "The model proposes a tool call.")]
    attempts = 1
    effects = 1 if fault["effect"] == "committed" else 0

    if fault["kind"] == "model":
        timeline.append(Step("harness", "rejected", f"Validate and surface: {fault['label']}."))
        timeline.append(
            Step("model", "corrected", "A structured tool error enables a corrected call.")
        )
        timeline.append(Step("tool", "applied", "The corrected call executes once."))
        effects = 1
        outcome = "recovered"
        lesson = "Return one structured result for every accepted call, including failures."
    elif not fault["retryable"]:
        timeline.append(Step("provider", "failed", f"{fault['label']} is not retryable."))
        timeline.append(
            Step("harness", "stopped", "The harness fails loudly without amplification.")
        )
        outcome = "failed safely"
        lesson = (
            "Classify failures before retrying; invalid requests do not improve with repetition."
        )
    elif retries == 0:
        timeline.append(Step("provider", "failed", fault["label"]))
        timeline.append(Step("harness", "stopped", "The retry budget is exhausted."))
        outcome = "failed within budget"
        lesson = "A bounded failure is observable and preferable to an unbounded retry loop."
    elif fault["kind"] == "transport":
        timeline.append(
            Step("provider", "failed", "429 received; the first attempt has no effect.")
        )
        attempts += 1
        timeline.append(Step("harness", "retried", "Retry once within the shared task deadline."))
        timeline.append(Step("provider", "succeeded", "The retry succeeds."))
        outcome = "recovered"
        lesson = "Retry transient transport failures inside a total deadline and attempt budget."
    elif stable_key:
        timeline.append(
            Step("tool", "unknown", "The effect committed, but its acknowledgement was lost.")
        )
        attempts += 1
        timeline.append(Step("harness", "retried", "Retry with the same operation key."))
        timeline.append(
            Step("tool", "replayed", "The sink returns the original result without another effect.")
        )
        if reconcile:
            timeline.append(
                Step("harness", "verified", "Independent effect state confirms one commit.")
            )
        outcome = "recovered without duplication"
        lesson = (
            "Stable operation identity closes the retry window; reconciliation verifies the result."
        )
    else:
        timeline.append(
            Step("tool", "unknown", "The effect committed, but its acknowledgement was lost.")
        )
        attempts += 1
        effects += 1
        timeline.append(
            Step("harness", "retried", "A new operation key is generated for the retry.")
        )
        timeline.append(Step("tool", "duplicated", "The sink accepts a second effect."))
        if reconcile:
            timeline.append(Step("harness", "detected", "Independent state exposes the duplicate."))
            outcome = "duplicate detected"
            lesson = "Reconciliation detects damage, but a stable key prevents it."
        else:
            outcome = "silent duplicate"
            lesson = (
                "A successful response does not prove the intended effect happened exactly once."
            )

    return {
        "schema_version": 1,
        "mode": "deterministic-simulation",
        "failure": failure,
        "failure_label": fault["label"],
        "policy": {"retries": retries, "stable_key": stable_key, "reconcile": reconcile},
        "outcome": outcome,
        "attempts": attempts,
        "effects": effects,
        "lesson": lesson,
        "timeline": [asdict(step) for step in timeline],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failure", choices=FAILURES, default="timeout_after_effect")
    parser.add_argument("--retries", type=int, choices=range(4), default=1)
    parser.add_argument("--stable-key", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--reconcile", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    print(
        json.dumps(
            simulate(
                args.failure,
                retries=args.retries,
                stable_key=args.stable_key,
                reconcile=args.reconcile,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
