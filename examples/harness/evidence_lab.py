"""Create and compare versioned evidence manifests without upgrading their claims."""

from __future__ import annotations

import argparse
import json

SCHEMA = "agentic-arena.run-record/v1"
CLAIMS = {
    "wiring": {
        "modes": {"mock", "offline-fixture", "codex", "live"},
        "question": "Does the path connect and return the expected shape?",
    },
    "recovery": {
        "modes": {"offline-fixture", "codex", "live"},
        "question": "Does the harness preserve the recovery contract under a controlled fault?",
    },
    "real_model": {
        "modes": {"codex", "live"},
        "question": "Can a real model complete the fixed functional path?",
    },
    "provider_comparison": {
        "modes": {"live"},
        "question": "How do repeated native-provider runs compare under shared controls?",
    },
}


def build_record(
    *,
    claim: str,
    mode: str,
    model: str = "fixed-responder",
    dataset: str = "developer-workbench/v1",
    scorer: str = "contract-check/v1",
    repetitions: int = 1,
    commit: str = "working-tree",
    config: str = "default",
    exclusions: tuple[str, ...] = (),
    observations: tuple[str, ...] = (),
) -> dict:
    if claim not in CLAIMS:
        raise ValueError(f"unknown claim: {claim}")
    if mode not in {"mock", "offline-fixture", "codex", "live"}:
        raise ValueError(f"unknown mode: {mode}")
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    supported = mode in CLAIMS[claim]["modes"]
    return {
        "schema": SCHEMA,
        "claim": {"id": claim, "question": CLAIMS[claim]["question"]},
        "evidence": {
            "mode": mode,
            "supports_claim": supported,
            "limitation": _limitation(claim, mode, repetitions),
        },
        "provenance": {
            "commit": commit,
            "config": config,
            "model": model,
            "dataset": dataset,
            "scorer": scorer,
            "repetitions": repetitions,
            "exclusions": list(exclusions),
        },
        "observations": list(observations),
        "design_guidance": [],
    }


def compare_records(left: dict, right: dict) -> dict:
    fields = ["claim", "mode", "dataset", "scorer"]
    if left["claim"]["id"] in {"real_model", "provider_comparison"}:
        fields.append("model")
    values = {
        "claim": (left["claim"]["id"], right["claim"]["id"]),
        "mode": (left["evidence"]["mode"], right["evidence"]["mode"]),
        **{
            key: (left["provenance"][key], right["provenance"][key])
            for key in ("dataset", "scorer", "model")
        },
    }
    differences = [field for field in fields if values[field][0] != values[field][1]]
    both_supported = left["evidence"]["supports_claim"] and right["evidence"]["supports_claim"]
    return {
        "schema": "agentic-arena.manifest-comparison/v1",
        "comparable": both_supported and not differences,
        "matched_fields": [field for field in fields if field not in differences],
        "blocking_differences": differences,
        "note": "A comparable contract still needs repeated runs and uncertainty reporting.",
    }


def _limitation(claim: str, mode: str, repetitions: int) -> str:
    if mode == "mock":
        return "Fixed responses establish wiring and mechanics, not model capability."
    if mode == "offline-fixture":
        return "The controlled fixture establishes local behavior, not provider performance."
    if mode == "codex":
        return "A translated subscription run is a functional check, not a native benchmark."
    if claim == "provider_comparison" and repetitions < 3:
        return "A native run is eligible, but one or two repetitions do not describe variability."
    return "A native run can support this claim when shared controls and uncertainty are reported."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim", choices=tuple(CLAIMS), default="recovery")
    parser.add_argument(
        "--mode", choices=("mock", "offline-fixture", "codex", "live"), default="offline-fixture"
    )
    parser.add_argument("--model", default="fixed-responder")
    parser.add_argument("--dataset", default="developer-workbench/v1")
    parser.add_argument("--scorer", default="contract-check/v1")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--commit", default="working-tree")
    parser.add_argument("--config", default="default")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--observation", action="append", default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            build_record(
                claim=args.claim,
                mode=args.mode,
                model=args.model,
                dataset=args.dataset,
                scorer=args.scorer,
                repetitions=args.repetitions,
                commit=args.commit,
                config=args.config,
                exclusions=tuple(args.exclude),
                observations=tuple(args.observation),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
