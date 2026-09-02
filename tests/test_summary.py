"""The cross-arena summary must not put the wrong number in the table.

Two ways this report could quietly mislead, both asserted here: rendering an
unsupported adapter as a failure, and crediting an adapter for skipping an
expensive arena.
"""

import pytest

from arena import summary as S


def _fw(name, *, items=None, reason=None):
    if reason is not None:
        return {"framework": name, "available": False, "reason": reason, "items": []}
    return {"framework": name, "available": True, "items": items or []}


def _item(item_id, passed=True, prompt_tokens=100, **extra):
    return {
        "item_id": item_id,
        "passed": passed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": 10,
        "llm_calls": 2,
        "tool_calls": [],
        **extra,
    }


def _record(arena, frameworks):
    return {
        "arena": arena,
        "mode": "mock",
        "harness_version": "0.1.0",
        "python": "3.13.0",
        "frameworks": frameworks,
    }


def test_unsupported_renders_as_not_a_failure():
    fw = _fw("x", reason="arena requires a pause ... does not implement the resume API (...)")
    assert S._cell(fw) == "n/s"


def test_missing_library_and_stub_are_distinguished_from_failure():
    assert S._cell(_fw("x", reason="build failed: No module named 'x'")) == "·"
    assert S._cell(_fw("x", reason="stub adapter: does not fit the gateway")) == "stub"
    assert S._cell(_fw("x", reason="build failed: TypeError")) == "err"


def test_partial_and_clean_passes_render_differently():
    assert S._cell(_fw("x", items=[_item("a"), _item("b")])) == "✅"
    assert S._cell(_fw("x", items=[_item("a"), _item("b", passed=False)])) == "1/2"


def test_overhead_ratio_uses_only_arenas_both_adapters_ran():
    """An adapter that sits out an expensive arena must not look cheap for it."""
    records = [
        _record(
            "cheap",
            [
                _fw("vanilla", items=[_item("a", prompt_tokens=100)]),
                _fw("other", items=[_item("a", prompt_tokens=100)]),
            ],
        ),
        _record(
            "pricey",
            [
                _fw("vanilla", items=[_item("a", prompt_tokens=9000)]),
                _fw("other", reason="does not implement the resume API"),
            ],
        ),
    ]
    out: list[str] = []
    S._overhead(records, ["vanilla", "other"], out)
    row = next(line for line in out if line.startswith("| `other`"))
    # Shared arena only: 100/100. Counting the skipped one would give ~0.01x.
    assert row.rstrip().endswith("1.00× |"), row


def test_no_runs_renders_a_message_rather_than_an_empty_table():
    text = S.render([], "mock")
    assert "No `mock` runs found" in text


def test_mock_summary_never_lands_in_results(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(S, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(S, "collect", lambda mode, ids=None: [])
    monkeypatch.setattr(S, "REPO_ROOT", tmp_path)
    path, _ = S.write_summary("mock")
    assert path.parts[0] == "runs", path
    assert not (tmp_path / "results").exists()


@pytest.mark.parametrize("mode", ["mock", "live"])
def test_render_labels_what_the_numbers_mean(mode):
    records = [_record("tool_use", [_fw("vanilla", items=[_item("a")])])]
    text = S.render(records, mode)
    # A mock report must warn the reader; a live one must not carry that caveat.
    assert ("wiring check, not a leaderboard" in text) == (mode == "mock")
    assert "Coverage" in text
