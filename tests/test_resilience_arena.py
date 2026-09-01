"""The resilience arena must actually inject faults, and the baseline must survive them."""

import json

from arena.config import REPO_ROOT, ArenaConfig
from arena.registry import load_arena
from arena.runner import run
from arena.tools import TOOL_FUNCS

SCRIPT = json.loads(
    (REPO_ROOT / "arenas" / "resilience" / "mock_script.json").read_text(encoding="utf-8")
)


def test_every_scenario_declares_and_actually_injects_a_fault():
    for scenario in SCRIPT["scenarios"]:
        assert scenario.get("deliberate_fault"), f"{scenario['match']}: fault not documented"
        assert len(scenario["turns"]) == 2, "a fault turn, then the recovery answer"
        assert scenario["turns"][0].get("tool_calls"), "first turn must be the faulty tool call"
        assert scenario["turns"][-1].get("content"), "last turn must be the correct answer"


def test_the_faults_are_varied_not_the_same_one_eight_times():
    faults = {s["deliberate_fault"] for s in SCRIPT["scenarios"]}
    assert len(faults) == len(SCRIPT["scenarios"]), f"duplicate fault kinds: {faults}"


def test_faults_are_genuinely_malformed():
    """Guard against a 'fault' that is quietly valid and tests nothing."""
    broken = 0
    for scenario in SCRIPT["scenarios"]:
        call = scenario["turns"][0]["tool_calls"][0]
        args = call.get("arguments")
        if call["name"] not in TOOL_FUNCS:
            broken += 1  # unknown tool
            continue
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
            except json.JSONDecodeError:
                broken += 1  # unparseable arguments
                continue
            if not isinstance(parsed, dict):
                broken += 1  # not an argument object
            continue
        if not args or "expr" in args and not str(args.get("expr", "")).strip():
            broken += 1  # missing required argument
            continue
        broken += 1  # bad expression / unexpected extra argument
    assert broken == len(SCRIPT["scenarios"]), "some scenarios do not inject a real fault"


def test_baseline_recovers_from_every_fault():
    """If the stdlib loop cannot recover, the arena is broken, not the framework."""
    arena = load_arena("resilience")
    record = run("resilience", ["vanilla"], config=ArenaConfig(mode="mock", repeat=1))
    fw = record["frameworks"][0]
    assert fw["available"], fw
    failed = [it["item_id"] for it in fw["items"] if not it["passed"]]
    assert not failed, f"baseline failed to recover from: {failed}"
    assert len(fw["items"]) == len(arena.dataset)
