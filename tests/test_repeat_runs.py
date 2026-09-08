"""`--repeat N` must actually multiply the run and feed the stability report.

Mock mode is deterministic, so the interesting variance numbers only show up on a
live run — but the plumbing (N legs, per-leg tagging, the scorecard's reliability
section) has to work offline or a live `--repeat` run has nothing to fill in.
`tests/test_scorecard_stability.py` checks the aggregation on hand-built records;
this drives it through the real harness.
"""

from collections import Counter

from arena.config import ArenaConfig
from arena.runner import run
from arena.scorecard import _aggregate, _render_markdown, write_scorecard


def test_repeat_multiplies_the_items_and_tags_each_leg():
    record = run("tool_use", ["vanilla"], config=ArenaConfig(mode="mock", repeat=3))

    assert record["repeat"] == 3
    items = record["frameworks"][0]["items"]
    assert len(items) == 3 * record["dataset_size"]
    assert sorted({it["repeat"] for it in items}) == [0, 1, 2]
    # every dataset item runs once per leg
    assert set(Counter(it["item_id"] for it in items).values()) == {3}


def test_deterministic_mock_repeats_report_zero_variance_and_no_flaky_items():
    record = run("tool_use", ["vanilla"], config=ArenaConfig(mode="mock", repeat=3))

    row = _aggregate(record)[0]
    assert row["repeats"] == 3
    assert row["pass_rate_by_repeat"] == [1.0, 1.0, 1.0]
    assert row["pass_rate_stddev"] == 0.0
    assert row["unstable_items"] == 0

    md = _render_markdown(record, [row])
    assert "across 3 repeats" in md
    assert "Every item gave the same verdict on every repeat." in md


def test_repeat_scorecard_writes_and_reports_the_repeat_count(tmp_path, monkeypatch):
    from arena import scorecard

    monkeypatch.setattr(scorecard, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(scorecard, "RESULTS_DIR", tmp_path / "results")

    record = run("tool_use", ["vanilla"], config=ArenaConfig(mode="mock", repeat=2))
    text = write_scorecard(record).read_text(encoding="utf-8")
    assert "× 2 repeat(s)" in text
    assert "across 2 repeats" in text
