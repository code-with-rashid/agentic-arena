"""Grades an `AgentResult` against the checks attached to an `EvalItem`.

An item passes when every check passes. Keep check types small and mechanical —
anything requiring an LLM judge belongs in a separate, clearly-labelled arena.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .types import AgentResult, EvalItem, ItemOutcome

_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")
_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL | re.IGNORECASE)

# The check contract, as (required fields, optional fields) keyed by `type`.
# `arena validate` lints datasets against this, so a new check type must be
# registered here as well as handled in `_check` — the test suite enforces that.
CHECK_SPECS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "contains": (("value",), ()),
    "icontains": (("value",), ()),
    "not_contains": (("value",), ()),
    "iregex": (("value",), ()),
    "numeric_equals": (("value",), ("tol",)),
    "tool_used": (("name",), ()),
    "no_tool": ((), ()),
    "min_tool_calls": (("value",), ()),
    "max_tool_calls": (("value",), ()),
    "json_valid": ((), ()),
    "json_schema": (("schema",), ()),
    "json_path_equals": (("path", "value"), ("tol",)),
    "sentence_count": ((), ("min", "max")),
}


def _numbers(text: str) -> list[float]:
    out: list[float] = []
    for token in _NUMBER.findall(text):
        try:
            out.append(float(token.replace(",", "")))
        except ValueError:
            continue
    return out


def _balanced_span(text: str) -> str | None:
    """Return the first balanced {...} or [...] span in `text`, or None."""
    start = None
    opener = closer = ""
    for i, ch in enumerate(text):
        if start is None and ch in "{[":
            start, opener, closer = i, ch, "}" if ch == "{" else "]"
            depth = 0
        if start is None:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json(text: str) -> Any:
    """Best-effort parse of a JSON value out of possibly-chatty model output.

    Tries, in order: the whole string, a ```json fenced block, the first balanced
    bracket span. Raises `ValueError` if none parse.
    """
    text = (text or "").strip()
    candidates: list[str] = [text]
    fence = _JSON_FENCE.search(text)
    if fence:
        candidates.append(fence.group(1))
    span = _balanced_span(text)
    if span:
        candidates.append(span)
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (ValueError, TypeError):
            continue
    raise ValueError("no JSON value found in output")


_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def validate_schema(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """A deliberately tiny JSON-schema checker (no dependency).

    Supports the keywords the arenas actually use: type, required, properties,
    additionalProperties (bool), items, minItems, enum. Returns a list of human
    error strings (empty == valid).
    """
    errors: list[str] = []
    expected = schema.get("type")
    if expected:
        py = _JSON_TYPES.get(expected)
        # bool is a subclass of int — keep them distinct
        if expected == "integer" and isinstance(value, bool):
            errors.append(f"{path}: expected integer, got boolean")
        elif expected in ("integer", "number") and isinstance(value, bool):
            errors.append(f"{path}: expected {expected}, got boolean")
        elif py is not None and not isinstance(value, py):
            errors.append(f"{path}: expected {expected}, got {type(value).__name__}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")
    if expected == "object" and isinstance(value, dict):
        props: dict[str, Any] = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required key {key!r}")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}: unexpected key {key!r}")
        for key, sub in props.items():
            if key in value:
                errors.extend(validate_schema(value[key], sub, f"{path}.{key}"))
    if expected == "array" and isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: expected >= {schema['minItems']} items, got {len(value)}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, entry in enumerate(value):
                errors.extend(validate_schema(entry, item_schema, f"{path}[{i}]"))
    return errors


def _dig(value: Any, dotted: str) -> Any:
    cur = value
    for part in dotted.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


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
    if ctype == "not_contains":
        val = str(check["value"])
        return (val not in text, f"expected {val!r} to be absent")
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
    if ctype == "sentence_count":
        lo = int(check.get("min", 1))
        hi = int(check.get("max", 10_000))
        # A period between two digits is a decimal point, not a sentence end.
        cleaned = re.sub(r"(?<=\d)\.(?=\d)", "", text)
        sentences = [s for s in re.split(r"[.!?]+", cleaned) if any(c.isalpha() for c in s)]
        n = len(sentences)
        return (lo <= n <= hi, f"expected between {lo} and {hi} sentences, got {n}")
    if ctype == "json_valid":
        try:
            extract_json(text)
        except ValueError as exc:
            return (False, f"expected parseable JSON ({exc})")
        return (True, "expected parseable JSON")
    if ctype == "json_schema":
        try:
            value = extract_json(text)
        except ValueError as exc:
            return (False, f"expected JSON matching schema ({exc})")
        errs = validate_schema(value, check["schema"])
        return (not errs, "schema: " + ("; ".join(errs) if errs else "ok"))
    if ctype == "json_path_equals":
        path = str(check["path"])
        try:
            actual = _dig(extract_json(text), path)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return (False, f"could not read {path!r} ({exc})")
        if "tol" in check:
            try:
                ok = abs(float(actual) - float(check["value"])) <= float(check["tol"])
            except (TypeError, ValueError):
                ok = False
            return (
                ok,
                f"expected {path} within {check['tol']} of {check['value']}, got {actual!r}",
            )
        if isinstance(check["value"], str) and isinstance(actual, str):
            ok = actual.strip().lower() == check["value"].strip().lower()
        else:
            ok = actual == check["value"]
        return (ok, f"expected {path} == {check['value']!r}, got {actual!r}")
    return (False, f"unknown check type {ctype!r}")


def score_item(item: EvalItem, result: AgentResult) -> ItemOutcome:
    details: list[dict[str, Any]] = []
    all_ok = result.error is None
    for check in item.checks:
        ok, desc = (False, "skipped: adapter error") if result.error else _check(check, result)
        details.append({"type": check.get("type", ""), "ok": ok, "detail": desc, "spec": check})
        all_ok = all_ok and ok
    return ItemOutcome(item_id=item.id, passed=all_ok, checks=details, result=result)
