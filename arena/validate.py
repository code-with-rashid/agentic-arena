"""Static validation of arena definitions — no LLM, no adapters, no network.

Catches the class of mistake that otherwise only shows up as a mysterious 0/15:
a dataset item whose question matches no mock scenario, a check type that does
not exist, a tool the arena never declared, a duplicate item id.

    python -m arena validate                # every arena
    python -m arena validate --arena rag    # just one
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .registry import ARENAS_DIR, available_arenas
from .scorer import CHECK_SPECS
from .tools import TOOL_FUNCS


@dataclass
class Report:
    arena: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _validate_checks(item_id: str, checks: list[Any], report: Report) -> None:
    if not checks:
        report.errors.append(f"{item_id}: has no checks (it can never fail)")
        return
    for i, check in enumerate(checks):
        where = f"{item_id}.checks[{i}]"
        if not isinstance(check, dict):
            report.errors.append(f"{where}: must be an object, got {type(check).__name__}")
            continue
        ctype = check.get("type")
        if ctype not in CHECK_SPECS:
            known = ", ".join(sorted(CHECK_SPECS))
            report.errors.append(f"{where}: unknown check type {ctype!r} (known: {known})")
            continue
        required, optional = CHECK_SPECS[ctype]
        for key in required:
            if key not in check:
                report.errors.append(f"{where}: {ctype!r} requires {key!r}")
        allowed = {"type", *required, *optional}
        for key in check:
            if key not in allowed:
                report.warnings.append(f"{where}: {ctype!r} ignores unknown field {key!r}")


def _load_dataset(base: Path, report: Report) -> list[dict[str, Any]]:
    path = base / "dataset.jsonl"
    if not path.exists():
        report.errors.append("missing dataset.jsonl")
        return []
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            report.errors.append(f"dataset.jsonl:{lineno}: invalid JSON ({exc.msg})")
            continue
        item_id = str(obj.get("id", "")) or f"<line {lineno}>"
        if not obj.get("id"):
            report.errors.append(f"dataset.jsonl:{lineno}: missing 'id'")
        elif item_id in seen:
            report.errors.append(f"dataset.jsonl:{lineno}: duplicate id {item_id!r}")
        seen.add(item_id)
        if not str(obj.get("input", "")).strip():
            report.errors.append(f"{item_id}: empty 'input'")
        _validate_checks(item_id, obj.get("checks", []), report)
        items.append(obj)
    if not items:
        report.errors.append("dataset.jsonl has no items")
    return items


def _validate_mock(
    base: Path, items: list[dict[str, Any]], tools: set[str], report: Report
) -> None:
    path = base / "mock_script.json"
    if not path.exists():
        report.errors.append("missing mock_script.json")
        return
    try:
        script = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.errors.append(f"mock_script.json: invalid JSON ({exc.msg})")
        return

    scenarios = script.get("scenarios", [])
    if not isinstance(scenarios, list) or not scenarios:
        report.errors.append("mock_script.json: 'scenarios' must be a non-empty list")
        return

    matches: list[str] = []
    by_match: dict[str, dict[str, Any]] = {}
    for i, scenario in enumerate(scenarios):
        where = f"mock_script.json scenarios[{i}]"
        match = str(scenario.get("match", ""))
        if not match:
            report.errors.append(f"{where}: missing 'match'")
        elif match.lower() in [m.lower() for m in matches]:
            report.errors.append(f"{where}: duplicate match {match!r}")
        matches.append(match)
        by_match.setdefault(match.lower(), scenario)

        turns = scenario.get("turns", [])
        if not turns:
            report.errors.append(f"{where}: has no turns")

        # A resilience arena scripts faults on purpose — an undeclared tool name
        # or malformed arguments IS the test. Such scenarios opt out by saying so,
        # which keeps the check strict everywhere else instead of loosening it.
        fault = scenario.get("deliberate_fault")
        for j, turn in enumerate(turns):
            for call in turn.get("tool_calls", []) or []:
                name = call.get("name", "")
                if name in tools or fault:
                    continue
                report.errors.append(
                    f"{where}.turns[{j}]: calls tool {name!r}, "
                    f"which the arena does not declare ({sorted(tools)})"
                )
        if turns and turns[-1].get("tool_calls"):
            report.errors.append(
                f"{where}: last turn is a tool call, so the agent never gets a final "
                "answer and will burn max_tool_iterations"
            )

    # The drift check this whole module exists for.
    for item in items:
        text = str(item.get("input", "")).lower()
        hits = [m for m in matches if m and m.lower() in text]
        item_id = item.get("id", "?")
        if not hits:
            report.errors.append(
                f"{item_id}: no mock scenario matches its input — this item would "
                "silently fall through to the default scenario in mock mode"
            )
        elif len(hits) > 1:
            report.warnings.append(
                f"{item_id}: matches {len(hits)} scenarios {hits}; the first one wins"
            )

        if len(hits) == 1:
            _validate_tool_checks(
                item_id, item.get("checks", []), by_match[hits[0].lower()], report
            )


def _scripted_tool_calls(scenario: dict[str, Any]) -> list[str]:
    """The tool-call names the mock will actually serve for this scenario.

    The agent loops until a turn carries a final answer (content, no tool calls),
    so every tool call scripted up to that point is one the adapter makes and
    reports; turns after it are dead. This is what a `tool_used` / `*_tool_calls`
    check is really being run against.
    """
    names: list[str] = []
    for turn in scenario.get("turns", []) or []:
        calls = turn.get("tool_calls") or []
        for call in calls:
            names.append(str(call.get("name", "")))
        if not calls and turn.get("content") is not None:
            break
    return names


def _validate_tool_checks(
    item_id: str, checks: list[Any], scenario: dict[str, Any], report: Report
) -> None:
    """Catch a tool-count / tool-name check the matched scenario can never satisfy.

    A `min_tool_calls: 2` on an item whose scenario scripts one `search`, or a
    `tool_used: calculator` on a scenario that only calls `search`, fails every
    mock run for a reason nothing else reports — it looks like an adapter bug.
    Skipped for `deliberate_fault` scenarios, where the mismatch is the point.
    """
    if scenario.get("deliberate_fault"):
        return
    scripted = _scripted_tool_calls(scenario)
    n, present = len(scripted), set(scripted)
    for check in checks:
        if not isinstance(check, dict):
            continue
        ctype, where = check.get("type"), f"{item_id}: {check.get('type')!r} check"
        if ctype == "min_tool_calls" and isinstance(check.get("value"), int) and check["value"] > n:
            report.errors.append(
                f"{where} wants >= {check['value']} tool calls, but its mock scenario "
                f"scripts {n} ({scripted}) — the item fails every mock run"
            )
        elif (
            ctype == "max_tool_calls" and isinstance(check.get("value"), int) and check["value"] < n
        ):
            report.errors.append(
                f"{where} allows <= {check['value']} tool calls, but its mock scenario "
                f"scripts {n} ({scripted}) — the item fails every mock run"
            )
        elif ctype == "tool_used" and check.get("name") and check["name"] not in present:
            report.errors.append(
                f"{where} expects {check['name']!r}, but its mock scenario calls "
                f"{sorted(present) or 'no tools'} — the item fails every mock run"
            )
        elif ctype == "no_tool" and n:
            report.errors.append(
                f"{where} expects no tool calls, but its mock scenario scripts {n} "
                f"({scripted}) — the item fails every mock run"
            )
        elif ctype == "tool_not_used" and check.get("name") and check["name"] in present:
            report.errors.append(
                f"{where} forbids {check['name']!r}, but its mock scenario calls it "
                f"({scripted}) — the item fails every mock run"
            )


def validate_arena(arena_id: str) -> Report:
    report = Report(arena=arena_id)
    base = ARENAS_DIR / arena_id

    spec_path = base / "arena.toml"
    if not spec_path.exists():
        report.errors.append("missing arena.toml")
        return report
    try:
        meta = tomllib.loads(spec_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        report.errors.append(f"arena.toml: invalid TOML ({exc})")
        return report

    if meta.get("id") != arena_id:
        report.errors.append(f"arena.toml: id {meta.get('id')!r} != directory name {arena_id!r}")
    if not str(meta.get("description", "")).strip():
        report.warnings.append("arena.toml: empty 'description' (it heads the scorecard)")
    if not str(meta.get("system_prompt_intent", "")).strip():
        report.warnings.append("arena.toml: empty 'system_prompt_intent'")

    tools = set(meta.get("tools", []))
    unknown = sorted(tools - set(TOOL_FUNCS))
    if unknown:
        report.errors.append(
            f"arena.toml: declares tools {unknown} that arena.tools does not provide "
            f"({sorted(TOOL_FUNCS)})"
        )

    items = _load_dataset(base, report)
    _validate_mock(base, items, tools & set(TOOL_FUNCS), report)
    return report


def validate_all(arena_ids: list[str] | None = None) -> list[Report]:
    return [validate_arena(a) for a in (arena_ids or available_arenas())]
