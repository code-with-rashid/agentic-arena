"""Repeats must be reported, not silently averaged away.

Mock mode is deterministic, so a flaky run cannot be produced by running the
harness — these build the run record directly.
"""

from arena.scorecard import _aggregate, _render_markdown


def _record(passed_by_item_and_repeat, *, repeat, mode="live"):
    """passed_by_item_and_repeat: {item_id: [passed_on_repeat_0, ...]}"""
    items = []
    for item_id, verdicts in passed_by_item_and_repeat.items():
        for rep, ok in enumerate(verdicts):
            items.append(
                {
                    "repeat": rep,
                    "item_id": item_id,
                    "passed": ok,
                    "checks": [],
                    "output_text": "",
                    "tool_calls": [],
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "latency_s": 0.1,
                    "llm_calls": 1,
                    "error": None,
                }
            )
    return {
        "arena": "demo",
        "arena_description": "demo",
        "mode": mode,
        "model": "m",
        "repeat": repeat,
        "dataset_size": len(passed_by_item_and_repeat),
        "started_at": "2026-09-01T00:00:00Z",
        "duration_s": 1.0,
        "harness_version": "0.1.0",
        "python": "3.13.0",
        "platform": "test",
        "pricing": {"input_per_m": 1.0, "output_per_m": 1.0},
        "frameworks": [{"framework": "fw", "available": True, "lib_version": "v1", "items": items}],
    }


def test_stable_run_reports_zero_deviation_and_no_flaky_items():
    rec = _record({"a": [True] * 3, "b": [True] * 3}, repeat=3)
    row = _aggregate(rec)[0]
    assert row["repeats"] == 3
    assert row["pass_rate_stddev"] == 0.0
    assert row["unstable_items"] == 0
    assert "Every item gave the same verdict" in _render_markdown(rec, [row])


def test_flaky_item_is_identified_by_id():
    # 'b' passes on repeat 0 only -> per-repeat rates 1.0, 0.5, 0.5
    rec = _record({"a": [True, True, True], "b": [True, False, False]}, repeat=3)
    row = _aggregate(rec)[0]

    assert row["pass_rate_by_repeat"] == [1.0, 0.5, 0.5]
    assert row["pass_rate_stddev"] > 0
    assert row["unstable_items"] == 1
    assert row["unstable_item_ids"] == ["b"]

    md = _render_markdown(rec, [row])
    assert "Unstable items" in md
    assert "`b`" in md
    assert "`a`" not in md.split("Unstable items")[1]


def test_an_item_failing_every_repeat_is_not_flaky_just_wrong():
    """Consistently failing is reproducible; it must not be reported as unstable."""
    rec = _record({"a": [True] * 3, "b": [False] * 3}, repeat=3)
    row = _aggregate(rec)[0]
    assert row["unstable_items"] == 0
    assert row["pass_rate_stddev"] == 0.0
    assert row["pass_rate"] == 0.5


def test_single_repeat_reports_no_deviation_and_no_stability_section():
    rec = _record({"a": [True], "b": [False]}, repeat=1)
    row = _aggregate(rec)[0]
    assert row["pass_rate_stddev"] is None
    md = _render_markdown(rec, [row])
    assert "±" not in md
    assert "Unstable items" not in md


def test_pass_rate_is_unchanged_by_the_stability_additions():
    rec = _record({"a": [True, False], "b": [True, True]}, repeat=2)
    row = _aggregate(rec)[0]
    assert row["passed"] == 3
    assert row["items"] == 4
    assert row["pass_rate"] == 0.75
