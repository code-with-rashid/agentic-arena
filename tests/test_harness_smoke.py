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


def test_run_can_filter_to_specific_items():
    record = run("tool_use", ["vanilla"], config=ArenaConfig(mode="mock"), only={"tu-03"})
    items = record["frameworks"][0]["items"]
    assert [it["item_id"] for it in items] == ["tu-03"]
    assert record["dataset_size"] == 1
    assert record["filtered_to"] == ["tu-03"]
    assert record["_path"].endswith("__partial.json")


def test_run_rejects_an_unknown_item_id():
    import pytest

    with pytest.raises(SystemExit) as exc:
        run("tool_use", ["vanilla"], config=ArenaConfig(mode="mock"), only={"tu-03", "nope-99"})
    # the message lists the real ids so `--item` is self-documenting
    assert "nope-99" in str(exc.value) and "tu-01" in str(exc.value)


def test_list_arena_prints_item_ids(capsys):
    from arena.__main__ import main

    assert main(["list", "--arena", "tool_use"]) == 0
    out = capsys.readouterr().out
    assert "tu-01" in out and "tu-15" in out


def test_latest_run_skips_a_partial_run(tmp_path, monkeypatch):
    import json

    from arena import scorecard

    monkeypatch.setattr(scorecard, "RUNS_DIR", tmp_path)
    full = {"arena": "demo", "dataset_size": 15, "frameworks": []}
    partial = {"arena": "demo", "dataset_size": 1, "filtered_to": ["d-01"], "frameworks": []}
    (tmp_path / "20260101T000000Z__demo__mock.json").write_text(json.dumps(full))
    # Lexically later, so it would win if it were not excluded.
    (tmp_path / "20260101T000001Z__demo__mock__partial.json").write_text(json.dumps(partial))

    assert scorecard.latest_run("demo", mode="mock")["dataset_size"] == 15
