"""End-to-end: the vanilla adapter must pass every tool_use item in mock mode.

If this breaks, either an adapter regressed or the mock script and dataset drifted
apart.
"""

from arena.config import ArenaConfig
from arena.runner import run
from arena.scorecard import write_scorecard


def test_vanilla_tool_use_mock_is_green(tmp_path, monkeypatch):
    config = ArenaConfig(mode="mock", repeat=1)
    record = run("tool_use", ["vanilla"], config=config)

    fw = record["frameworks"][0]
    assert fw["available"], fw
    passed = sum(1 for it in fw["items"] if it["passed"])
    assert passed == record["dataset_size"], [it for it in fw["items"] if not it["passed"]]

    # scorecard rendering should not raise
    path = write_scorecard(record)
    assert path.exists()


def test_vanilla_structured_output_mock_is_green(tmp_path, monkeypatch):
    config = ArenaConfig(mode="mock", repeat=1)
    record = run("structured_output", ["vanilla"], config=config)

    fw = record["frameworks"][0]
    assert fw["available"], fw
    passed = sum(1 for it in fw["items"] if it["passed"])
    assert passed == record["dataset_size"], [it for it in fw["items"] if not it["passed"]]

    path = write_scorecard(record)
    assert path.exists()


def test_unknown_framework_is_reported_not_raised():
    record = run("tool_use", ["does_not_exist"], config=ArenaConfig(mode="mock"))
    assert record["frameworks"][0]["available"] is False
