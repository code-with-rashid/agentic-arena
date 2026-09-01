"""The validator must catch real mistakes, not just pass the arenas we ship.

Each test builds a deliberately broken arena on disk and asserts the specific
error surfaces.
"""

import json

import pytest

from arena import validate as V
from arena.registry import available_arenas
from arena.scorer import CHECK_SPECS

GOOD_SPEC = """
id = "demo"
description = "A demo arena."
tools = ["search", "calculator"]
system_prompt_intent = "Answer using the tools."
"""

GOOD_ITEM = {
    "id": "d-01",
    "input": "What is 2 plus 2?",
    "checks": [{"type": "numeric_equals", "value": 4, "tol": 0}],
}

GOOD_MOCK = {
    "scenarios": [
        {
            "match": "2 plus 2",
            "turns": [
                {"tool_calls": [{"name": "calculator", "arguments": {"expr": "2 + 2"}}]},
                {"content": "4"},
            ],
        }
    ],
    "default": {"turns": [{"content": "I don't know."}]},
}


def _write(tmp_path, monkeypatch, *, spec=GOOD_SPEC, items=None, mock=None):
    """Materialise an arena named 'demo' and point the validator at it."""
    base = tmp_path / "demo"
    base.mkdir(parents=True, exist_ok=True)
    (base / "arena.toml").write_text(spec, encoding="utf-8")
    rows = [GOOD_ITEM] if items is None else items
    (base / "dataset.jsonl").write_text(
        "\n".join(json.dumps(r) if isinstance(r, dict) else r for r in rows) + "\n",
        encoding="utf-8",
    )
    (base / "mock_script.json").write_text(
        json.dumps(GOOD_MOCK if mock is None else mock), encoding="utf-8"
    )
    monkeypatch.setattr(V, "ARENAS_DIR", tmp_path)
    return base


def _errors(tmp_path, monkeypatch, **kw):
    _write(tmp_path, monkeypatch, **kw)
    return V.validate_arena("demo").errors


def test_shipped_arenas_are_valid():
    for arena_id in available_arenas():
        report = V.validate_arena(arena_id)
        assert report.ok, f"{arena_id}: {report.errors}"


def test_happy_path_is_clean(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)
    report = V.validate_arena("demo")
    assert report.ok and not report.warnings, (report.errors, report.warnings)


def test_catches_item_with_no_matching_mock_scenario(tmp_path, monkeypatch):
    orphan = {**GOOD_ITEM, "id": "d-02", "input": "Something entirely unscripted."}
    errs = _errors(tmp_path, monkeypatch, items=[GOOD_ITEM, orphan])
    assert any("no mock scenario matches" in e and "d-02" in e for e in errs), errs


def test_catches_unknown_check_type(tmp_path, monkeypatch):
    bad = {**GOOD_ITEM, "checks": [{"type": "vibes_equals", "value": 1}]}
    errs = _errors(tmp_path, monkeypatch, items=[bad])
    assert any("unknown check type" in e for e in errs), errs


def test_catches_check_missing_required_field(tmp_path, monkeypatch):
    bad = {**GOOD_ITEM, "checks": [{"type": "tool_used"}]}
    errs = _errors(tmp_path, monkeypatch, items=[bad])
    assert any("requires 'name'" in e for e in errs), errs


def test_catches_duplicate_item_ids(tmp_path, monkeypatch):
    errs = _errors(tmp_path, monkeypatch, items=[GOOD_ITEM, dict(GOOD_ITEM)])
    assert any("duplicate id" in e for e in errs), errs


def test_catches_item_with_no_checks(tmp_path, monkeypatch):
    errs = _errors(tmp_path, monkeypatch, items=[{**GOOD_ITEM, "checks": []}])
    assert any("no checks" in e for e in errs), errs


def test_catches_undeclared_tool_in_mock_script(tmp_path, monkeypatch):
    mock = json.loads(json.dumps(GOOD_MOCK))
    mock["scenarios"][0]["turns"][0]["tool_calls"][0]["name"] = "teleport"
    errs = _errors(tmp_path, monkeypatch, mock=mock)
    assert any("teleport" in e and "does not declare" in e for e in errs), errs


def test_catches_arena_declaring_a_tool_that_does_not_exist(tmp_path, monkeypatch):
    spec = GOOD_SPEC.replace('tools = ["search", "calculator"]', 'tools = ["search", "telepathy"]')
    errs = _errors(tmp_path, monkeypatch, spec=spec)
    assert any("telepathy" in e for e in errs), errs


def test_catches_scenario_ending_on_a_tool_call(tmp_path, monkeypatch):
    mock = json.loads(json.dumps(GOOD_MOCK))
    mock["scenarios"][0]["turns"] = mock["scenarios"][0]["turns"][:1]
    errs = _errors(tmp_path, monkeypatch, mock=mock)
    assert any("last turn is a tool call" in e for e in errs), errs


def test_catches_id_mismatching_directory(tmp_path, monkeypatch):
    errs = _errors(tmp_path, monkeypatch, spec=GOOD_SPEC.replace('id = "demo"', 'id = "other"'))
    assert any("directory name" in e for e in errs), errs


def test_catches_malformed_dataset_line(tmp_path, monkeypatch):
    errs = _errors(tmp_path, monkeypatch, items=[GOOD_ITEM, "{not json"])
    assert any("invalid JSON" in e for e in errs), errs


def test_warns_on_ambiguous_multi_scenario_match(tmp_path, monkeypatch):
    mock = json.loads(json.dumps(GOOD_MOCK))
    mock["scenarios"].append({"match": "what is", "turns": [{"content": "4"}]})
    _write(tmp_path, monkeypatch, mock=mock)
    report = V.validate_arena("demo")
    assert report.ok, report.errors
    assert any("matches 2 scenarios" in w for w in report.warnings), report.warnings


@pytest.mark.parametrize("ctype", sorted(CHECK_SPECS))
def test_every_registered_check_type_is_implemented(ctype):
    """CHECK_SPECS and the scorer must not drift apart."""
    from arena.scorer import _check
    from arena.types import AgentResult

    required, _optional = CHECK_SPECS[ctype]
    stub = {"value": 0, "name": "search", "path": "a", "schema": {"type": "object"}}
    check = {"type": ctype, **{k: stub[k] for k in required}}
    _ok, detail = _check(check, AgentResult(output_text="{}"))
    assert "unknown check type" not in detail
