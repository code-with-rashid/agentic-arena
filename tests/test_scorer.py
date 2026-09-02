from arena.scorer import score_item
from arena.types import AgentResult, EvalItem


def _item(checks):
    return EvalItem(id="x", input="q", checks=checks)


def test_numeric_equals_with_tolerance():
    res = AgentResult(output_text="The answer is about 1082.7 feet.")
    out = score_item(_item([{"type": "numeric_equals", "value": 1082.7, "tol": 3}]), res)
    assert out.passed


def test_numeric_equals_reads_thousands_separator():
    res = AgentResult(output_text="It is 299,792,458 m/s.")
    out = score_item(_item([{"type": "numeric_equals", "value": 299792458, "tol": 1000}]), res)
    assert out.passed


def test_tool_used_and_no_tool():
    res = AgentResult(output_text="42", tool_calls=[{"name": "calculator"}])
    assert score_item(_item([{"type": "tool_used", "name": "calculator"}]), res).passed
    assert not score_item(_item([{"type": "no_tool"}]), res).passed


def test_error_result_fails_every_check():
    res = AgentResult(error="boom")
    out = score_item(_item([{"type": "contains", "value": "anything"}]), res)
    assert not out.passed
    assert out.checks[0]["ok"] is False


def test_iregex_case_insensitive():
    res = AgentResult(output_text="Edmund HILLARY reached the summit.")
    assert score_item(_item([{"type": "iregex", "value": "hillary"}]), res).passed


def test_not_contains():
    res = AgentResult(output_text="I could not find a confident answer.")
    assert score_item(_item([{"type": "not_contains", "value": "1889"}]), res).passed
    res2 = AgentResult(output_text="It was completed in 1889.")
    assert not score_item(_item([{"type": "not_contains", "value": "1889"}]), res2).passed


def test_sentence_count_bounds_and_decimal_points():
    brief = (
        "The Eiffel Tower is a wrought-iron lattice tower in Paris. "
        "It was completed in 1889. It stands 330.5 metres tall."
    )
    res = AgentResult(output_text=brief)
    # 3 sentences; the 330.5 decimal point must not be read as a fourth.
    assert score_item(_item([{"type": "sentence_count", "min": 3, "max": 5}]), res).passed
    assert not score_item(_item([{"type": "sentence_count", "min": 4, "max": 5}]), res).passed
    assert not score_item(_item([{"type": "sentence_count", "min": 1, "max": 2}]), res).passed


def test_sentence_count_defaults_are_permissive():
    res = AgentResult(output_text="One. Two. Three. Four. Five. Six.")
    assert score_item(_item([{"type": "sentence_count"}]), res).passed


_SCHEMA = {
    "type": "object",
    "required": ["name", "year", "height_m", "sources"],
    "properties": {
        "name": {"type": "string"},
        "year": {"type": "integer"},
        "height_m": {"type": "number"},
        "sources": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    },
    "additionalProperties": False,
}


def test_json_schema_accepts_valid_record_in_prose_and_fence():
    good = '{"name": "Eiffel Tower", "year": 1889, "height_m": 330, "sources": ["corpus"]}'
    assert score_item(
        _item([{"type": "json_schema", "schema": _SCHEMA}]), AgentResult(output_text=good)
    ).passed
    fenced = f"Here you go:\n```json\n{good}\n```\n"
    assert score_item(
        _item([{"type": "json_schema", "schema": _SCHEMA}]), AgentResult(output_text=fenced)
    ).passed


def test_json_schema_rejects_missing_key_wrong_type_and_extra_key():
    bad_missing = '{"name": "X", "height_m": 1, "sources": ["s"]}'
    bad_type = '{"name": "X", "year": "1889", "height_m": 1, "sources": ["s"]}'
    bad_extra = '{"name": "X", "year": 1, "height_m": 1, "sources": ["s"], "colour": "brown"}'
    bad_empty = '{"name": "X", "year": 1, "height_m": 1, "sources": []}'
    check = {"type": "json_schema", "schema": _SCHEMA}
    for blob in (bad_missing, bad_type, bad_extra, bad_empty):
        assert not score_item(_item([check]), AgentResult(output_text=blob)).passed, blob


def test_json_path_equals_string_and_numeric_tolerance():
    blob = '{"name": "Golden Gate Bridge", "year": 1937, "height_m": 227.4, "sources": ["c"]}'
    res = AgentResult(output_text=blob)
    assert score_item(
        _item([{"type": "json_path_equals", "path": "name", "value": "golden gate bridge"}]), res
    ).passed
    assert score_item(
        _item([{"type": "json_path_equals", "path": "height_m", "value": 227, "tol": 1}]), res
    ).passed
    assert score_item(
        _item([{"type": "json_path_equals", "path": "sources.0", "value": "c"}]), res
    ).passed
    assert not score_item(
        _item([{"type": "json_path_equals", "path": "year", "value": 1900}]), res
    ).passed


def test_json_valid_reports_failure_on_prose():
    assert not score_item(
        _item([{"type": "json_valid"}]), AgentResult(output_text="no json here")
    ).passed
