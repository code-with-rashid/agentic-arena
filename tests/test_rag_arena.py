"""The rag arena must actually require retrieval, and its traps must actually bite.

Two things are easy to get wrong here and neither shows up as a failing run:
a multi-hop item that a single search answers, and an "unanswerable" item whose
checks a confidently hallucinated answer would still pass. Both are asserted
directly.
"""

import json

from arena.config import REPO_ROOT, ArenaConfig
from arena.registry import load_arena
from arena.runner import run
from arena.scorer import score_item
from arena.types import AgentResult

ARENA = load_arena("rag")
ITEMS = {item.id: item for item in ARENA.dataset}
SCRIPT = json.loads((REPO_ROOT / "arenas" / "rag" / "mock_script.json").read_text(encoding="utf-8"))

MULTI_HOP = ["rag-10", "rag-11", "rag-12"]
UNANSWERABLE = {"rag-13": "1832", "rag-14": "Bartholdi", "rag-15": "1933"}


def _min_tool_calls(item_id: str) -> int:
    checks = ITEMS[item_id].checks
    return next(int(c["value"]) for c in checks if c["type"] == "min_tool_calls")


def test_multi_hop_items_demand_a_second_search():
    for item_id in MULTI_HOP:
        assert _min_tool_calls(item_id) >= 2, f"{item_id} would pass on a single lookup"


def test_multi_hop_scenarios_script_two_searches_then_an_answer():
    wanted = {"inspired tokyo tower", "taipei 101", "chrysler building"}
    seen = set()
    for scenario in SCRIPT["scenarios"]:
        if scenario["match"] not in wanted:
            continue
        seen.add(scenario["match"])
        turns = scenario["turns"]
        assert len(turns) == 3, f"{scenario['match']}: search, search, answer"
        assert all(t.get("tool_calls") for t in turns[:2]), "both hops must search"
        assert turns[-1].get("content") and not turns[-1].get("tool_calls")
        # The second query must be new information, not a repeat of the first.
        first, second = (t["tool_calls"][0]["arguments"]["query"] for t in turns[:2])
        assert first != second, f"{scenario['match']}: second hop repeats the first query"
    assert seen == wanted, f"missing multi-hop scenarios: {wanted - seen}"


def test_a_hallucinated_answer_fails_the_unanswerable_items():
    """The whole point of these items: parametric memory must not score."""
    hallucinated = {
        "rag-13": "Gustave Eiffel was born in 1832 in Dijon, France.",
        "rag-14": "The Statue of Liberty was designed by Frederic Auguste Bartholdi.",
        "rag-15": "Construction of the Golden Gate Bridge began in 1933.",
    }
    for item_id, text in hallucinated.items():
        result = AgentResult(output_text=text, tool_calls=[{"name": "search"}])
        outcome = score_item(ITEMS[item_id], result)
        assert not outcome.passed, f"{item_id}: a hallucinated answer scored as correct"
        # It must fail on the trap, not merely on the refusal phrasing.
        trap = UNANSWERABLE[item_id]
        failed = [c for c in outcome.checks if not c["ok"] and c["type"] == "not_contains"]
        assert failed, f"{item_id}: the {trap!r} trap did not fire"


def test_an_honest_refusal_passes_the_unanswerable_items():
    for item_id in UNANSWERABLE:
        result = AgentResult(
            output_text="The corpus does not contain that, so I cannot answer it.",
            tool_calls=[{"name": "search"}],
        )
        assert score_item(ITEMS[item_id], result).passed, f"{item_id}: honest refusal rejected"


def test_baseline_passes_every_item_and_really_hops():
    record = run("rag", ["vanilla"], config=ArenaConfig(mode="mock", repeat=1))
    fw = record["frameworks"][0]
    assert fw["available"], fw
    failed = [it["item_id"] for it in fw["items"] if not it["passed"]]
    assert not failed, f"baseline failed: {failed}"
    assert len(fw["items"]) == len(ARENA.dataset) == 15
    by_id = {it["item_id"]: it for it in fw["items"]}
    for item_id in MULTI_HOP:
        assert len(by_id[item_id]["tool_calls"]) >= 2, f"{item_id} answered without a second hop"
