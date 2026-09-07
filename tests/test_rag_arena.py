"""The rag arena must actually require retrieval, and its traps must actually bite.

Two things are easy to get wrong here and neither shows up as a failing run:
a multi-hop item that a single search answers, and an "unanswerable" item whose
checks a confidently hallucinated answer would still pass. Both are asserted
directly.

There is also a negative result worth pinning. In mock mode every framework
walks `rag` identically — 15/15, two hops on each multi-hop item, a refusal on
each unanswerable one — because the script decides when the second search
happens and what the answer is. No framework retrieves *better* here; the
arena's entire discriminating power is in the dataset design and the scorer,
and both of those are gated above. Anything a framework could vary — the prompt
cost of carrying a multi-document context — is the same overhead already
measured on `tool_use` in docs/overhead.md. So the cross-framework check below
is a floor ("everyone still clears it, the same way"), not a comparison.
"""

import json

import pytest

from arena.config import REPO_ROOT, ArenaConfig
from arena.registry import frameworks_for_arena, load_arena
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


@pytest.mark.parametrize("name", sorted(frameworks_for_arena("rag")))
def test_every_framework_walks_rag_the_same_way(name):
    """Not a comparison — a floor. The script drives the second hop and the
    answer, so a framework cannot retrieve better or worse here; it can only
    fail to run the arena at all. Every one that runs it lands on the identical
    trace: 15/15, exactly two hops on each multi-hop item, and a passing refusal
    on each unanswerable one.

    Pinned because `rag` has no per-framework finding and so nothing else would
    notice if an adapter quietly stopped making the second search (answering the
    multi-hop items from the first result) or started answering the
    unanswerable ones — both of which pass mock mode's ~100% by construction and
    would only surface as a wrong number in a live run.
    """
    record = run("rag", [name], config=ArenaConfig(mode="mock", repeat=1))
    fw = record["frameworks"][0]
    if not fw.get("available"):
        pytest.skip(f"{name} not installed in this environment")

    failed = [it["item_id"] for it in fw["items"] if not it["passed"]]
    assert not failed, f"{name} failed rag items: {failed}"
    assert len(fw["items"]) == len(ARENA.dataset) == 15

    by_id = {it["item_id"]: it for it in fw["items"]}
    for item_id in MULTI_HOP:
        hops = len(by_id[item_id]["tool_calls"])
        assert hops == 2, f"{name}: {item_id} took {hops} hop(s), the multi-hop script has two"
    for item_id in UNANSWERABLE:
        assert by_id[item_id]["passed"], (
            f"{name}: {item_id} did not pass — an unanswerable item was answered rather "
            f"than refused"
        )
