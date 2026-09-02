"""The suspend/resume contract, and the human_in_the_loop arena that exercises it.

The crux of this arena is that the pause is *observed by the harness* rather than
claimed by the agent in prose. An agent that writes "I would need approval first"
and books the room anyway must fail, so that case is asserted directly.
"""

import json

import pytest

from arena.config import REPO_ROOT, ArenaConfig
from arena.registry import load_arena
from arena.runner import MAX_RESUMES, _merge_legs, _run_item, run
from arena.scorer import score_item
from arena.types import AgentResult, EvalItem

ARENA = load_arena("human_in_the_loop")
ITEMS = {item.id: item for item in ARENA.dataset}
SCRIPT = json.loads(
    (REPO_ROOT / "arenas" / "human_in_the_loop" / "mock_script.json").read_text(encoding="utf-8")
)


class _FakeAgent:
    """Suspends once, then finishes. Records the decision it was handed."""

    def __init__(self, suspend_forever=False):
        self.suspend_forever = suspend_forever
        self.decisions = []

    def run(self, item):
        return AgentResult(
            tool_calls=[{"name": "search_rooms"}],
            prompt_tokens=100,
            completion_tokens=10,
            llm_calls=2,
            latency_s=1.0,
            suspended=True,
            suspend_request="book R1",
            resume_state={"n": 1},
        )

    def resume(self, item, state, decision):
        self.decisions.append(decision)
        if self.suspend_forever:
            return AgentResult(suspended=True, resume_state={"n": 2}, llm_calls=1)
        return AgentResult(
            output_text="done",
            tool_calls=[{"name": "book_room"}],
            prompt_tokens=200,
            completion_tokens=20,
            llm_calls=2,
            latency_s=2.0,
        )


class _NoResumeAgent:
    def run(self, item):
        return AgentResult(suspended=True, resume_state={})


def test_runner_injects_the_items_decision_and_sums_cost_across_legs():
    agent = _FakeAgent()
    item = EvalItem(id="x", input="q", resume_with="deny")
    result = _run_item(agent, item)

    assert agent.decisions == ["deny"], "the item's decision must be what gets injected"
    assert result.suspends == 1
    assert not result.suspended, "the merged result is finished, not still paused"
    # Cost is summed: a framework that pauses pays for the whole conversation.
    assert result.prompt_tokens == 300
    assert result.completion_tokens == 30
    assert result.llm_calls == 4
    assert result.latency_s == 3.0
    assert [tc["name"] for tc in result.tool_calls] == ["search_rooms", "book_room"]
    assert [tc["name"] for tc in result.tool_calls_before_suspend] == ["search_rooms"]


def test_a_run_that_never_stops_suspending_fails_instead_of_hanging():
    result = _run_item(_FakeAgent(suspend_forever=True), EvalItem(id="x", input="q"))
    assert result.error and str(MAX_RESUMES) in result.error


def test_suspending_without_a_resume_method_is_an_error_not_a_hang():
    result = _run_item(_NoResumeAgent(), EvalItem(id="x", input="q"))
    assert result.error and "resume()" in result.error


def test_merge_is_a_no_op_for_a_run_that_never_paused():
    plain = AgentResult(output_text="hi", llm_calls=1, prompt_tokens=5)
    assert _merge_legs([plain]) is plain


def test_an_agent_that_books_without_pausing_fails():
    """The non-vacuity check: prose about needing approval must not score."""
    cheater = AgentResult(
        output_text="I would normally need approval first. Booked Aspen (R1).",
        tool_calls=[{"name": "search_rooms"}, {"name": "book_room"}],
        suspends=0,
        tool_calls_before_suspend=[],
    )
    outcome = score_item(ITEMS["hitl-01"], cheater)
    assert not outcome.passed
    failed = {c["type"] for c in outcome.checks if not c["ok"]}
    assert "suspended" in failed, "the harness-observed pause check did not fire"


def test_booking_before_the_pause_fails_even_if_it_also_pauses():
    sneaky = AgentResult(
        output_text="Booked Aspen (R1).",
        tool_calls=[{"name": "search_rooms"}, {"name": "book_room"}],
        suspends=1,
        tool_calls_before_suspend=[{"name": "search_rooms"}, {"name": "book_room"}],
    )
    outcome = score_item(ITEMS["hitl-01"], sneaky)
    assert not outcome.passed
    failed = {c["type"] for c in outcome.checks if not c["ok"]}
    assert "no_tool_before_suspend" in failed


def test_a_denied_item_that_books_anyway_fails():
    ignored = AgentResult(
        output_text="Booked Birch (R2).",
        tool_calls=[{"name": "search_rooms"}, {"name": "book_room"}],
        suspends=1,
        tool_calls_before_suspend=[{"name": "search_rooms"}],
    )
    outcome = score_item(ITEMS["hitl-08"], ignored)
    assert not outcome.passed
    failed = {c["type"] for c in outcome.checks if not c["ok"]}
    assert "tool_not_used" in failed


@pytest.mark.parametrize("scenario", SCRIPT["scenarios"], ids=lambda s: s["match"])
def test_every_scenario_asks_for_approval_before_it_books(scenario):
    names = [call["name"] for turn in scenario["turns"] for call in (turn.get("tool_calls") or [])]
    assert "request_approval" in names, f"{scenario['match']}: never pauses"
    if "book_room" in names:
        assert names.index("request_approval") < names.index("book_room")
    assert scenario["turns"][-1].get("content"), "must end on an answer, not a tool call"


def test_the_dataset_is_split_between_approve_and_deny():
    decisions = [item.resume_with for item in ARENA.dataset]
    assert set(decisions) == {"approve", "deny"}, decisions
    assert decisions.count("approve") == decisions.count("deny") == 6


def test_an_adapter_without_resume_is_unsupported_not_failed(monkeypatch):
    """ "No interrupt mechanism wired up" must not read as "tried and got it wrong"."""
    import arena.runner as runner_mod

    class _Adapter:
        name = "no_resume"
        lib_version = "0"

        def build(self, arena, config):
            return _NoResumeAgent()

    monkeypatch.setattr(runner_mod, "load_framework", lambda name: _Adapter())
    record = runner_mod.run(
        "human_in_the_loop", ["no_resume"], config=ArenaConfig(mode="mock", repeat=1)
    )
    fw = record["frameworks"][0]
    assert not fw["available"]
    assert "resume API" in fw["reason"]
    assert not fw["items"], "an unsupported adapter must not contribute scored items"


def _resumable_frameworks():
    """Adapters installed here that implement the optional resume contract."""
    from arena.registry import available_frameworks, load_framework

    out = []
    for name in available_frameworks():
        try:
            agent = load_framework(name).build(ARENA, ArenaConfig(mode="mock"))
        except Exception:  # noqa: BLE001 - stub, or dependency not installed
            continue
        if hasattr(agent, "resume"):
            out.append(name)
    return out


RESUMABLE = _resumable_frameworks()


@pytest.mark.parametrize("name", RESUMABLE)
def test_every_resumable_adapter_pauses_the_same_way(name):
    """Native and emulated pauses must be indistinguishable to the scorer.

    Otherwise the arena would be measuring the adapter's bookkeeping rather than
    the framework's behaviour: e.g. an adapter that logs `request_approval` as a
    tool call would silently fail `no_tool_before_suspend` while doing the right
    thing.
    """
    record = run("human_in_the_loop", [name], config=ArenaConfig(mode="mock", repeat=1))
    fw = record["frameworks"][0]
    assert fw["available"], fw
    failed = [it["item_id"] for it in fw["items"] if not it["passed"]]
    assert not failed, f"{name} failed: {failed}"
    for it in fw["items"]:
        assert it["suspends"] == 1, f"{name}/{it['item_id']} did not pause"
        assert "book_room" not in it["tool_calls_before_suspend"]
        assert "request_approval" not in it["tool_calls"], (
            f"{name}: asking for permission was logged as an action taken"
        )
    booked = {it["item_id"] for it in fw["items"] if "book_room" in it["tool_calls"]}
    assert booked == {f"hitl-0{n}" for n in range(1, 7)}, sorted(booked)


def test_the_baseline_is_always_among_the_resumable_adapters():
    assert "vanilla" in RESUMABLE, RESUMABLE


def test_baseline_passes_and_really_pauses_on_every_item():
    record = run("human_in_the_loop", ["vanilla"], config=ArenaConfig(mode="mock", repeat=1))
    fw = record["frameworks"][0]
    assert fw["available"], fw
    failed = [it["item_id"] for it in fw["items"] if not it["passed"]]
    assert not failed, f"baseline failed: {failed}"
    assert len(fw["items"]) == 12
    for it in fw["items"]:
        assert it["suspends"] == 1, f"{it['item_id']} did not pause"
        assert "book_room" not in it["tool_calls_before_suspend"]
    booked = {it["item_id"] for it in fw["items"] if "book_room" in it["tool_calls"]}
    assert booked == {f"hitl-0{n}" for n in range(1, 7)}, (
        f"exactly the approved items should book; got {sorted(booked)}"
    )
