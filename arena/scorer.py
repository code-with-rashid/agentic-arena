"""Grades an `AgentResult` against the checks attached to an `EvalItem`.

An item passes when every check passes. Keep check types small and mechanical —
anything requiring an LLM judge belongs in a separate, clearly-labelled arena.
"""

from __future__ import annotations

import re
from typing import Any

from .types import AgentResult, EvalItem, ItemOutcome

_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def _numbers(text: str) -> list[float]:
    out: list[float] = []
    for token in _NUMBER.findall(text):
        try:
            out.append(float(token.replace(",", "")))
        except ValueError:
            continue
    return out


def _check(check: dict[str, Any], result: AgentResult) -> tuple[bool, str]:
    ctype = check.get("type", "")
    text = result.output_text or ""
    tool_names = [tc.get("name", "") for tc in result.tool_calls]

    if ctype == "contains":
        val = str(check["value"])
        return (val in text, f"expected substring {val!r}")
    if ctype == "icontains":
        val = str(check["value"]).lower()
        return (val in text.lower(), f"expected substring (ci) {val!r}")
    if ctype == "iregex":
        pat = str(check["value"])
        return (re.search(pat, text, re.IGNORECASE) is not None, f"expected regex /{pat}/i")
    if ctype == "numeric_equals":
        target = float(check["value"])
        tol = float(check.get("tol", 0.0))
        hit = any(abs(n - target) <= tol for n in _numbers(text))
        return (hit, f"expected a number within {tol} of {target}")
    if ctype == "tool_used":
        name = str(check["name"])
        return (name in tool_names, f"expected tool {name!r} to be called")
    if ctype == "no_tool":
        return (len(tool_names) == 0, "expected no tool calls")
    if ctype == "min_tool_calls":
        n = int(check["value"])
        return (len(tool_names) >= n, f"expected >= {n} tool calls")
    if ctype == "max_tool_calls":
        n = int(check["value"])
        return (len(tool_names) <= n, f"expected <= {n} tool calls")
    return (False, f"unknown check type {ctype!r}")


def score_item(item: EvalItem, result: AgentResult) -> ItemOutcome:
    details: list[dict[str, Any]] = []
    all_ok = result.error is None
    for check in item.checks:
        ok, desc = (False, "skipped: adapter error") if result.error else _check(check, result)
        details.append({"type": check.get("type", ""), "ok": ok, "detail": desc, "spec": check})
        all_ok = all_ok and ok
    return ItemOutcome(item_id=item.id, passed=all_ok, checks=details, result=result)
