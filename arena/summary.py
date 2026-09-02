"""One cross-arena view built from the latest run record per arena.

The hard part of summarising this benchmark is not the table, it is refusing to
put the wrong number in it. Mock-mode pass rates are ~100% by construction, so a
grid of them looks like a leaderboard while meaning nothing. This report puts
coverage and the genuinely comparable measurements up front, and labels the
plumbing checks as plumbing checks.

    python -m arena summary                 # every arena's latest mock run
    python -m arena summary --mode live
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .config import REPO_ROOT
from .registry import available_arenas
from .scorecard import RESULTS_DIR, RUNS_DIR, latest_run

# Reasons an adapter contributed no items. These are not failures and must not be
# averaged in with them - see docs/methodology.md section 7.
_NOT_SUPPORTED = "resume API"
_NOT_INSTALLED = "No module named"
_STUB = "stub adapter"

BASELINE = "vanilla"


def _cell(fw: dict[str, Any]) -> str:
    if fw.get("available"):
        items = fw["items"]
        passed = sum(1 for it in items if it["passed"])
        return "✅" if passed == len(items) else f"{passed}/{len(items)}"
    reason = str(fw.get("reason", ""))
    if _NOT_SUPPORTED in reason:
        return "n/s"
    if _STUB in reason:
        return "stub"
    if _NOT_INSTALLED in reason:
        return "·"
    return "err"


def collect(mode: str = "mock", arena_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Latest run record per arena, skipping arenas with no run in that mode."""
    records = []
    for arena_id in arena_ids or available_arenas():
        try:
            records.append(latest_run(arena_id, mode=mode))
        except FileNotFoundError:
            continue
    return records


def _frameworks_in(records: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for record in records:
        for fw in record["frameworks"]:
            if fw["framework"] not in names:
                names.append(fw["framework"])
    return sorted(names)


def _by_name(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {fw["framework"]: fw for fw in record["frameworks"]}


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _coverage(records, names, out) -> None:
    out.append("## Coverage\n")
    out.append("| framework | " + " | ".join(r["arena"] for r in records) + " |")
    out.append("|---|" + "---|" * len(records))
    for name in names:
        cells = [_cell(_by_name(r)[name]) if name in _by_name(r) else " " for r in records]
        out.append(f"| `{name}` | " + " | ".join(cells) + " |")
    out.append("")
    out.append(
        "✅ every item passed · `n/m` partial · **`n/s`** the adapter does not implement a "
        "capability the arena requires (not a failure) · `stub` deliberate stub · `·` library "
        "not installed in this run\n"
    )


def _resilience(records, names, out) -> None:
    record = next((r for r in records if r["arena"] == "resilience"), None)
    if record is None:
        return
    out.append("## Comparable: recovery from scripted faults\n")
    out.append(
        "The faults are byte-identical for every framework and the mock is "
        "deterministic, so nothing about the *model* varies. Any difference is the "
        "framework's own error handling.\n"
    )
    out.append("| framework | recovered | failed on |")
    out.append("|---|--:|---|")
    for name in names:
        fw = _by_name(record).get(name)
        if not fw or not fw.get("available"):
            continue
        items = fw["items"]
        passed = sum(1 for it in items if it["passed"])
        bad = ", ".join(it["item_id"] for it in items if not it["passed"]) or "—"
        out.append(f"| `{name}` | {passed}/{len(items)} | {bad} |")
    out.append("")


def _is_variant(name: str) -> bool:
    """Is this a contrast entry scoped to one arena rather than a framework?

    Declared by the adapter as `arenas = (...)`. Looked up defensively: the
    summary reads run records, which may name an adapter this checkout no longer
    has.
    """
    from .registry import available_frameworks, load_framework

    if name not in available_frameworks():
        return False
    try:
        return bool(getattr(load_framework(name), "arenas", None))
    except Exception:  # noqa: BLE001 - a summary must never fail on a bad adapter
        return False


def _overhead(records, names, out) -> None:
    out.append("## Comparable: prompt size on the wire\n")
    out.append(
        "Every framework gets the same prompt and the same tool definitions and the "
        "mock replays identical turns, so this is the framework's own serialisation "
        "cost, which a provider bills for. Estimated tokens (chars/4) over messages "
        "plus tool schemas — compare frameworks with each other, not with a bill.\n"
    )
    out.append("| framework | " + " | ".join(r["arena"] for r in records) + " | vs baseline |")
    out.append("|---|" + "---:|" * (len(records) + 1))

    means: dict[str, dict[str, float]] = {}
    for name in names:
        row: dict[str, float] = {}
        for record in records:
            fw = _by_name(record).get(name)
            if fw and fw.get("available") and fw["items"]:
                value = _mean([it["prompt_tokens"] for it in fw["items"]])
                if value is not None:
                    row[record["arena"]] = value
        if row:
            means[name] = row

    base = means.get(BASELINE, {})
    for name, row in means.items():
        cells = [f"{row[r['arena']]:.0f}" if r["arena"] in row else "—" for r in records]
        # Only arenas BOTH ran, or an adapter that sits out an expensive arena
        # would look cheap for a reason that has nothing to do with its overhead.
        shared = [a for a in row if a in base]
        ratio = (
            f"{sum(row[a] for a in shared) / sum(base[a] for a in shared):.2f}×" if shared else "—"
        )
        # A variant entry is a different *structure*, not a different
        # serialisation of the same one. Left unmarked, `vanilla_multi` reads in
        # this table as a framework that wastes 2.5x the tokens, when what it
        # measures is the cost of splitting one agent into three.
        mark = " †" if _is_variant(name) else ""
        out.append(f"| `{name}`{mark} | " + " | ".join(cells) + f" | {ratio} |")
    out.append("")
    out.append(
        f"`vs baseline` is against `{BASELINE}` over **only the arenas both ran**, so an "
        "adapter that sits out an arena is not credited for skipping it."
    )
    if any(_is_variant(name) for name in means):
        out.append(
            "\n† A multi-agent **contrast entry**, not a framework comparison: its ratio is "
            "the cost of running three roles instead of one, which is a different structure "
            "rather than a heavier serialisation of the same one. Read those rows in "
            "`docs/multi-agent.md`, not against the frameworks above them.\n"
        )
    else:
        out.append("")


def _pause_cell(record: dict[str, Any] | None, name: str) -> str:
    if record is None:
        return "—"
    fw = _by_name(record).get(name)
    if fw is None:
        return " "
    if not fw.get("available"):
        return "no" if _NOT_SUPPORTED in str(fw.get("reason", "")) else "—"
    items = fw["items"]
    paused = sum(1 for it in items if it.get("suspends"))
    if paused == len(items) and all(it["passed"] for it in items):
        return f"yes ({paused}/{len(items)})"
    return f"**{paused}/{len(items)}**"


def _pauses(records, names, out) -> None:
    hitl = next((r for r in records if r["arena"] == "human_in_the_loop"), None)
    durable = next((r for r in records if r["arena"] == "durable_state"), None)
    if hitl is None and durable is None:
        return
    out.append("## Comparable: pausing, and surviving a crash\n")
    out.append(
        "The pause is observed by the harness, not claimed by the agent — see "
        "`docs/methodology.md` §7. `durable_state` goes further: it throws the "
        "runner away at the pause and rebuilds it, so only a real checkpoint or a "
        "serialised transcript survives. An adapter with no `resume` method is "
        "reported as not supported rather than as failing.\n"
    )
    out.append("| framework | pauses for a human | survives a crash |")
    out.append("|---|---|---|")
    for name in names:
        out.append(f"| `{name}` | {_pause_cell(hitl, name)} | {_pause_cell(durable, name)} |")
    out.append("")


def render(records: list[dict[str, Any]], mode: str) -> str:
    if not records:
        return f"# Cross-arena summary\n\nNo `{mode}` runs found in `runs/`.\n"

    names = _frameworks_in(records)
    out: list[str] = [
        "# Cross-arena summary",
        "",
        f"Generated {datetime.now(UTC).strftime('%Y-%m-%d')} from the latest **{mode}** run of "
        f"each arena · harness {records[0].get('harness_version', '?')} · "
        f"Python {records[0].get('python', '?')}",
        "",
    ]
    if mode == "mock":
        out += [
            "> **Read the coverage grid as a wiring check, not a leaderboard.** Mock-mode "
            "pass rates are ~100% by construction: the script feeds correct turns "
            "regardless of what the agent asked for. A ✅ means the adapter is wired up "
            "correctly, nothing more. The sections below it are the parts that do "
            "compare frameworks honestly, because the model is held identical and only "
            "the framework varies.",
            "",
        ]
    _coverage(records, names, out)
    _resilience(records, names, out)
    _overhead(records, names, out)
    _pauses(records, names, out)
    out.append("---")
    out.append("")
    out.append(
        "Quality numbers require `--mode live` against a real provider; see "
        "`docs/methodology.md` §5. No live scorecard exists yet."
        if mode == "mock"
        else "See `docs/methodology.md` §8 for reproducing these numbers."
    )
    return "\n".join(out) + "\n"


def write_summary(mode: str = "mock", arena_ids: list[str] | None = None):
    records = collect(mode, arena_ids)
    # Same rule as scorecards: results/ only ever holds live numbers.
    base = RESULTS_DIR if mode == "live" else RUNS_DIR
    base.mkdir(parents=True, exist_ok=True)
    path = base / "summary.md"
    path.write_text(render(records, mode), encoding="utf-8")
    return path.relative_to(REPO_ROOT), records
