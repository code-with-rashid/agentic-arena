"""The multi_agent arena must be well-formed and green for the stdlib baseline.

The arena tests how a framework expresses a researcher -> writer -> editor
pipeline. The eval is shape-based (a bounded-length brief carrying the right year
and measurement), so a single agent that role-plays the pipeline is a valid
entry and must pass; real multi-agent adapters are compared on cost, not on
whether they can clear the bar.
"""

import json

from arena.config import REPO_ROOT, ArenaConfig
from arena.registry import load_arena
from arena.runner import run

SCRIPT = json.loads(
    (REPO_ROOT / "arenas" / "multi_agent" / "mock_script.json").read_text(encoding="utf-8")
)


def test_every_scenario_researches_then_writes_a_brief():
    for scenario in SCRIPT["scenarios"]:
        turns = scenario["turns"]
        assert len(turns) == 2, f"{scenario['match']}: expected a search turn then the brief"
        assert turns[0].get("tool_calls"), "first turn must call search (the researcher)"
        assert turns[0]["tool_calls"][0]["name"] == "search"
        brief = turns[-1].get("content", "")
        assert brief and not turns[-1].get("tool_calls"), "last turn is the finished brief"
        # 3 to 5 sentences, matching the dataset's own bound.
        sentences = [s for s in brief.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        assert 3 <= len(sentences) <= 5, (
            f"{scenario['match']}: brief has {len(sentences)} sentences"
        )


def test_baseline_passes_every_item():
    arena = load_arena("multi_agent")
    record = run("multi_agent", ["vanilla"], config=ArenaConfig(mode="mock", repeat=1))
    fw = record["frameworks"][0]
    assert fw["available"], fw
    failed = [it["item_id"] for it in fw["items"] if not it["passed"]]
    assert not failed, f"baseline failed: {failed}"
    assert len(fw["items"]) == len(arena.dataset) == 10
