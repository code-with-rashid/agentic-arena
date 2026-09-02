"""Durability has to be demonstrated, not declared.

The arena's whole claim is that the runner is thrown away at the pause. If the
harness quietly handed the same object back, or handed a live reference across,
every adapter would pass while proving nothing — so both are asserted here.
"""

import json

import pytest

from arena.config import REPO_ROOT, ArenaConfig
from arena.registry import load_arena
from arena.runner import _across_the_gap, _run_item, run
from arena.scorer import score_item
from arena.types import AgentResult, EvalItem

ARENA = load_arena("durable_state")
ITEMS = {item.id: item for item in ARENA.dataset}
SCRIPT = json.loads(
    (REPO_ROOT / "arenas" / "durable_state" / "mock_script.json").read_text(encoding="utf-8")
)


def test_the_arena_declares_itself_durable():
    assert ARENA.durable, "without this flag the harness never discards the runner"
    assert not load_arena("human_in_the_loop").durable, "only durable_state rebuilds"


class _Recorder:
    """Suspends once; records which instance was asked to resume."""

    built = 0

    def __init__(self):
        type(self).built += 1
        self.instance = type(self).built
        self.resumed_on = None
        self.state_seen = None

    def run(self, item):
        return AgentResult(suspended=True, resume_state={"leg": 1}, llm_calls=1)

    def resume(self, item, state, decision):
        self.resumed_on = self.instance
        self.state_seen = state
        return AgentResult(output_text="done", llm_calls=1)


def test_a_durable_arena_resumes_on_a_freshly_built_runner():
    _Recorder.built = 0
    first = _Recorder()
    built: list[_Recorder] = []

    def rebuild():
        built.append(_Recorder())
        return built[-1]

    result = _run_item(first, EvalItem(id="x", input="q"), rebuild)
    assert not result.error, result.error
    assert first.resumed_on is None, "the original runner must not be the one resumed"
    assert built and built[-1].resumed_on == built[-1].instance


def test_without_a_rebuild_the_same_runner_resumes():
    """human_in_the_loop keeps the runner; only durable arenas discard it."""
    _Recorder.built = 0
    agent = _Recorder()
    _run_item(agent, EvalItem(id="x", input="q"))
    assert agent.resumed_on == agent.instance


class _SmugglerAgent:
    """Tries to resume through a live object no restarted process could hold."""

    def run(self, item):
        return AgentResult(suspended=True, resume_state={"conn": object()})

    def resume(self, item, state, decision):  # pragma: no cover - must not be reached
        raise AssertionError("resume should never be reached")


def test_state_that_could_not_survive_a_restart_is_an_error():
    result = _run_item(_SmugglerAgent(), EvalItem(id="x", input="q"), lambda: _SmugglerAgent())
    assert result.error and "survive a restart" in result.error


def test_the_gap_really_round_trips():
    assert _across_the_gap({"a": [1, {"b": "c"}]}) == {"a": [1, {"b": "c"}]}
    with pytest.raises(TypeError):
        _across_the_gap({"conn": object()})


def test_call_counts_catches_work_done_twice():
    """The check that separates 'resumed' from 'started over with the right answer'."""
    item = ITEMS["dur-01"]
    restarted = AgentResult(
        output_text="The Burj Khalifa is 498 metres taller than the Eiffel Tower.",
        tool_calls=[{"name": "search"}] * 4 + [{"name": "calculator"}],
        suspends=1,
    )
    outcome = score_item(item, restarted)
    assert not outcome.passed, "a correct answer reached by redoing the work must fail"
    failed = {c["type"] for c in outcome.checks if not c["ok"]}
    assert failed == {"call_counts"}, failed


@pytest.mark.parametrize("scenario", SCRIPT["scenarios"], ids=lambda s: s["match"])
def test_every_scenario_checkpoints_between_the_lookups_and_the_arithmetic(scenario):
    names = [c["name"] for t in scenario["turns"] for c in (t.get("tool_calls") or [])]
    assert names.count("search") == 2
    assert names.count("calculator") == 1
    assert names.index("save_progress") == 2, "the crash point sits after both lookups"
    assert names.index("save_progress") < names.index("calculator")
    assert scenario["turns"][-1].get("content")


def test_baseline_finishes_without_redoing_the_lookups():
    record = run("durable_state", ["vanilla"], config=ArenaConfig(mode="mock", repeat=1))
    fw = record["frameworks"][0]
    assert fw["available"], fw
    failed = [it["item_id"] for it in fw["items"] if not it["passed"]]
    assert not failed, f"baseline failed: {failed}"
    for it in fw["items"]:
        assert it["suspends"] == 1
        assert it["tool_calls"] == ["search", "search", "calculator"], it["tool_calls"]
