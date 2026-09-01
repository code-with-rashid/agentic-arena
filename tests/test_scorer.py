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
