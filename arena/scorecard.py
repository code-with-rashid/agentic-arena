"""Turns a run record into committed scorecards (markdown + json + csv)."""

from __future__ import annotations

import csv
import io
import json
import statistics
from pathlib import Path
from typing import Any

from .config import REPO_ROOT

RESULTS_DIR = REPO_ROOT / "results"
RUNS_DIR = REPO_ROOT / "runs"


def latest_run(arena_id: str, mode: str | None = None) -> dict[str, Any]:
    candidates = sorted(RUNS_DIR.glob(f"*__{arena_id}__*.json"))
    if mode:
        candidates = [p for p in candidates if p.stem.endswith(f"__{mode}")]
    if not candidates:
        raise FileNotFoundError(f"no runs found for arena {arena_id!r} in {RUNS_DIR}")
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def _stability(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Reliability across repeats.

    A single run tells you almost nothing about a stochastic agent: the same item
    can pass on one repeat and fail on the next. Methodology 6 tells people to use
    `--repeat`, so the scorecard has to report what the repeats disagreed about,
    otherwise the extra runs are silently averaged away.
    """
    by_repeat: dict[int, list[bool]] = {}
    by_item: dict[str, list[bool]] = {}
    for it in items:
        by_repeat.setdefault(it.get("repeat", 0), []).append(bool(it["passed"]))
        by_item.setdefault(it["item_id"], []).append(bool(it["passed"]))

    rates = [sum(v) / len(v) for v in by_repeat.values() if v]
    unstable = sorted(item_id for item_id, runs in by_item.items() if len(set(runs)) > 1)
    return {
        "repeats": len(by_repeat),
        "pass_rate_by_repeat": [round(r, 3) for r in rates],
        # Population stddev: these are all the repeats there were, not a sample.
        "pass_rate_stddev": round(statistics.pstdev(rates), 4) if len(rates) > 1 else None,
        "unstable_items": len(unstable),
        "unstable_item_ids": unstable,
    }


def _aggregate(record: dict[str, Any]) -> list[dict[str, Any]]:
    price_in = record["pricing"]["input_per_m"]
    price_out = record["pricing"]["output_per_m"]
    rows: list[dict[str, Any]] = []
    for fw in record["frameworks"]:
        if not fw.get("available", False):
            rows.append(
                {
                    "framework": fw["framework"],
                    "available": False,
                    "reason": fw.get("reason", "unavailable"),
                }
            )
            continue
        items = fw["items"]
        n = len(items) or 1
        passed = sum(1 for it in items if it["passed"])
        errors = sum(1 for it in items if it["error"])
        pt = sum(it["prompt_tokens"] for it in items)
        ct = sum(it["completion_tokens"] for it in items)
        latency = sum(it["latency_s"] for it in items)
        llm_calls = sum(it["llm_calls"] for it in items)
        rows.append(
            {
                "framework": fw["framework"],
                "available": True,
                "lib_version": fw.get("lib_version", "?"),
                "items": len(items),
                "pass_rate": round(passed / n, 3),
                "passed": passed,
                "errors": errors,
                "mean_latency_s": round(latency / n, 3),
                "total_tokens": pt + ct,
                "mean_tokens": round((pt + ct) / n, 1),
                "mean_llm_calls": round(llm_calls / n, 2),
                "est_cost_usd": round(pt / 1e6 * price_in + ct / 1e6 * price_out, 6),
                **_stability(items),
            }
        )
    rows.sort(key=lambda r: (not r["available"], -(r.get("pass_rate") or 0)))
    return rows


def _render_markdown(record: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        f"# Scorecard — `{record['arena']}`",
        "",
        f"> {record['arena_description']}",
        "",
        f"- **Mode:** {record['mode']}"
        + ("  ⚠️ plumbing only — not a quality signal" if record["mode"] == "mock" else ""),
        f"- **Model:** {record['model']}",
        f"- **Dataset:** {record['dataset_size']} items × {record['repeat']} repeat(s)",
        f"- **Run at:** {record['started_at']} ({record['duration_s']}s)",
        f"- **Harness:** v{record['harness_version']} · Python {record['python']}",
        "",
        "| Framework | Ver | Pass rate | Errors | Mean latency | Mean tokens | Mean LLM calls | Est. cost |",
        "|---|---|--:|--:|--:|--:|--:|--:|",
    ]
    for r in rows:
        if not r["available"]:
            lines.append(f"| `{r['framework']}` | — | _not available_ | — | — | — | — | — |")
            continue
        rate = f"{r['pass_rate']:.0%} ({r['passed']}/{r['items']})"
        if r.get("pass_rate_stddev") is not None:
            rate += f" ±{r['pass_rate_stddev']:.1%}"
        lines.append(
            f"| `{r['framework']}` | {r['lib_version']} | "
            f"{rate} | {r['errors']} | "
            f"{r['mean_latency_s']:.3f}s | {r['mean_tokens']:.0f} | {r['mean_llm_calls']:.2f} | "
            f"${r['est_cost_usd']:.4f} |"
        )

    if record.get("repeat", 1) > 1:
        lines += [
            "",
            f"± is the population standard deviation of the per-repeat pass rate "
            f"across {record['repeat']} repeats.",
        ]
        flaky = [r for r in rows if r.get("unstable_items")]
        if flaky:
            lines += [
                "",
                "**Unstable items** — passed on some repeats and failed on others. "
                "Their contribution to the pass rates above is not reproducible:",
                "",
            ]
            for r in flaky:
                ids = ", ".join(f"`{i}`" for i in r["unstable_item_ids"])
                lines.append(f"- `{r['framework']}` — {r['unstable_items']} item(s): {ids}")
        else:
            lines += ["", "Every item gave the same verdict on every repeat."]

    unavailable = [r for r in rows if not r["available"]]
    if unavailable:
        lines += ["", "**Not available this run:**", ""]
        lines += [f"- `{r['framework']}` — {r['reason']}" for r in unavailable]
    lines += [
        "",
        "_Generated by `python -m arena scorecard`. Do not edit by hand._",
        "",
    ]
    return "\n".join(lines)


def _render_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    fields = [
        "framework",
        "available",
        "lib_version",
        "items",
        "pass_rate",
        "errors",
        "mean_latency_s",
        "total_tokens",
        "mean_tokens",
        "mean_llm_calls",
        "est_cost_usd",
        "repeats",
        "pass_rate_stddev",
        "unstable_items",
        "reason",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()


def output_dir_for(record: dict[str, Any]) -> Path:
    """Where a run's scorecard belongs.

    Only live runs go to the committed `results/`. Mock scorecards land under
    `runs/` (gitignored) — methodology §5 says mock numbers are plumbing checks,
    not a quality signal, so they must never reach a published scorecard. Keeping
    them out of the tree by construction beats relying on everyone remembering.
    """
    if record.get("mode") == "live":
        return RESULTS_DIR / record["arena"]
    return RUNS_DIR / "scorecards" / record["arena"]


def write_scorecard(record: dict[str, Any]) -> Path:
    rows = _aggregate(record)
    out_dir = output_dir_for(record)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scorecard.md").write_text(_render_markdown(record, rows), encoding="utf-8")
    (out_dir / "scorecard.csv").write_text(_render_csv(rows), encoding="utf-8")
    (out_dir / "scorecard.json").write_text(
        json.dumps(
            {"meta": {k: v for k, v in record.items() if k != "frameworks"}, "rows": rows}, indent=2
        ),
        encoding="utf-8",
    )
    return out_dir / "scorecard.md"
