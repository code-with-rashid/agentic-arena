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


def test_mock_scorecards_never_land_in_results():
    """methodology 5: results/ is live-only, enforced by construction."""
    from arena.config import REPO_ROOT
    from arena.scorecard import output_dir_for

    results = REPO_ROOT / "results"
    mock_out = output_dir_for({"mode": "mock", "arena": "tool_use"})
    live_out = output_dir_for({"mode": "live", "arena": "tool_use"})

    assert results not in mock_out.parents, mock_out
    assert results in live_out.parents, live_out


def test_unknown_framework_is_reported_not_raised():
    record = run("tool_use", ["does_not_exist"], config=ArenaConfig(mode="mock"))
    assert record["frameworks"][0]["available"] is False
