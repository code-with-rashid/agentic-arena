"""`results/REFRESHED.md` rolls the per-arena scorecards into one staleness table."""

import json

from arena import refreshed


def _card(tmp, arena, *, started, model, rows):
    d = tmp / arena
    d.mkdir(parents=True)
    (d / "scorecard.json").write_text(
        json.dumps(
            {
                "meta": {
                    "arena": arena,
                    "started_at": started,
                    "model": model,
                    "harness_version": "0.1.0",
                },
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )


def test_empty_results_dir_renders_a_placeholder(tmp_path):
    text = refreshed.render(tmp_path)
    assert text.startswith(refreshed._MARKER)
    assert "No live scorecard has been published yet" in text
    assert "| Arena |" not in text


def test_one_scorecard_per_arena_is_tabulated_with_versions(tmp_path):
    _card(
        tmp_path,
        "tool_use",
        started="2026-09-08T10:00:00Z",
        model="gpt-4.1-mini",
        rows=[
            {"framework": "vanilla", "available": True, "lib_version": "stdlib"},
            {"framework": "crewai", "available": False},
        ],
    )
    _card(
        tmp_path,
        "rag",
        started="2026-09-09T12:00:00Z",
        model="gpt-4.1-mini",
        rows=[{"framework": "vanilla", "available": True, "lib_version": "stdlib"}],
    )
    text = refreshed.render(tmp_path)

    assert "| `tool_use` |" in text and "| `rag` |" in text
    assert "vanilla stdlib" in text
    assert "crewai" not in text  # unavailable rows are not version-stamped
    # newest run across all arenas is surfaced
    assert "Most recent run: **2026-09-09T12:00:00Z**." in text


def test_write_index_creates_the_file_and_is_idempotent(tmp_path):
    first = refreshed.write_index(tmp_path)
    assert first.name == "REFRESHED.md"
    body = first.read_text(encoding="utf-8")
    refreshed.write_index(tmp_path)
    assert first.read_text(encoding="utf-8") == body


def test_a_corrupt_scorecard_json_is_skipped_not_fatal(tmp_path):
    (tmp_path / "tool_use").mkdir(parents=True)
    (tmp_path / "tool_use" / "scorecard.json").write_text("{not json", encoding="utf-8")
    text = refreshed.render(tmp_path)
    assert "No live scorecard" in text
