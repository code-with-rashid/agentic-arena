"""The scorecard charts must render valid SVG and never disagree with the table."""

import xml.dom.minidom

import pytest

from arena import charts, scorecard


def _record(frameworks, *, mode="live"):
    """frameworks: {name: {pass_rate, mean_tokens, mean_llm_calls} | None for unavailable}"""
    fw_records = []
    for name, stats in frameworks.items():
        if stats is None:
            fw_records.append({"framework": name, "available": False, "reason": "not installed"})
            continue
        n = 10
        passed = round(stats["pass_rate"] * n)
        items = [
            {
                "repeat": 0,
                "item_id": f"{name}-{i}",
                "passed": i < passed,
                "checks": [],
                "output_text": "",
                "tool_calls": [],
                "prompt_tokens": stats["mean_tokens"],
                "completion_tokens": 0,
                "latency_s": 0.1,
                "llm_calls": stats["mean_llm_calls"],
                "error": None,
            }
            for i in range(n)
        ]
        fw_records.append(
            {"framework": name, "available": True, "lib_version": "v1", "items": items}
        )
    return {
        "arena": "demo",
        "arena_description": "demo arena",
        "mode": mode,
        "model": "m",
        "repeat": 1,
        "dataset_size": 10,
        "started_at": "2026-09-01T00:00:00Z",
        "duration_s": 1.0,
        "harness_version": "0.1.0",
        "python": "3.13.0",
        "platform": "test",
        "pricing": {"input_per_m": 1.0, "output_per_m": 1.0},
        "frameworks": fw_records,
    }


@pytest.fixture
def out_root(tmp_path, monkeypatch):
    monkeypatch.setattr(scorecard, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(scorecard, "RUNS_DIR", tmp_path / "runs")
    return tmp_path


def test_writes_four_well_formed_svgs_plus_an_index(out_root):
    rec = _record(
        {
            "vanilla": {"pass_rate": 1.0, "mean_tokens": 800, "mean_llm_calls": 2.0},
            "langgraph": {"pass_rate": 0.5, "mean_tokens": 1600, "mean_llm_calls": 3.0},
        }
    )
    out = charts.write_charts(rec)

    names = sorted(p.name for p in out.iterdir())
    assert names == [
        "est-cost.svg",
        "index.md",
        "mean-llm-calls.svg",
        "mean-tokens.svg",
        "pass-rate.svg",
    ]
    for svg in out.glob("*.svg"):
        doc = xml.dom.minidom.parseString(svg.read_text(encoding="utf-8"))
        assert doc.documentElement.tagName == "svg"


def test_live_run_charts_land_under_results(out_root):
    rec = _record({"vanilla": {"pass_rate": 1.0, "mean_tokens": 800, "mean_llm_calls": 2.0}})
    out = charts.write_charts(rec)
    assert (out_root / "results" / "demo" / "charts") == out


def test_mock_run_charts_are_labelled_plumbing_only_and_kept_out_of_results(out_root):
    rec = _record(
        {"vanilla": {"pass_rate": 1.0, "mean_tokens": 800, "mean_llm_calls": 2.0}}, mode="mock"
    )
    out = charts.write_charts(rec)
    assert "results" not in out.parts
    assert "plumbing only" in (out / "pass-rate.svg").read_text(encoding="utf-8")


def test_bar_width_is_proportional_to_the_value(out_root):
    rec = _record(
        {
            "full": {"pass_rate": 1.0, "mean_tokens": 100, "mean_llm_calls": 1.0},
            "half": {"pass_rate": 0.5, "mean_tokens": 100, "mean_llm_calls": 1.0},
        }
    )
    out = charts.write_charts(rec)
    doc = xml.dom.minidom.parseString((out / "pass-rate.svg").read_text(encoding="utf-8"))
    bars = [
        float(r.getAttribute("width"))
        for r in doc.getElementsByTagName("rect")
        if r.getAttribute("class") == "bar"
    ]
    assert bars[0] == pytest.approx(2 * bars[1])  # rows are sorted by pass rate desc


def test_every_available_framework_appears_and_unavailable_ones_do_not(out_root):
    rec = _record(
        {
            "vanilla": {"pass_rate": 1.0, "mean_tokens": 800, "mean_llm_calls": 2.0},
            "crewai": None,
        }
    )
    text = (charts.write_charts(rec) / "mean-tokens.svg").read_text(encoding="utf-8")
    assert "vanilla" in text
    assert "crewai" not in text


def test_a_run_with_no_available_framework_is_an_error(out_root):
    rec = _record({"crewai": None})
    with pytest.raises(ValueError, match="nothing to chart"):
        charts.write_charts(rec)


def test_output_is_deterministic(out_root):
    rec = _record({"vanilla": {"pass_rate": 1.0, "mean_tokens": 800, "mean_llm_calls": 2.0}})
    first = {p.name: p.read_bytes() for p in charts.write_charts(rec).iterdir()}
    second = {p.name: p.read_bytes() for p in charts.write_charts(rec).iterdir()}
    assert first == second
