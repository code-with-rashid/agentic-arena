"""Bar charts for a scorecard, rendered as hand-written SVG.

Phase 3 of the roadmap asks for "latency / token / cost charts generated into
`results/charts/`". The harness core is deliberately dependency-free, so this
draws the SVG by hand rather than pulling in matplotlib — the same trade the
inline JSON-schema validator makes in `arena.scorer`. Four horizontal bar
charts, one file each, next to the scorecard they summarise:

    results/<arena>/charts/        for a live run
    runs/scorecards/<arena>/charts/ for a mock run  (git-ignored, plumbing only)

The chart data is exactly the aggregated scorecard rows, so a chart can never
disagree with `scorecard.md`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from .scorecard import _aggregate, output_dir_for

# Canvas geometry. One number to tune is ROW_H; everything else follows.
_WIDTH = 760
_LABEL_W = 180  # left gutter for framework names
_VALUE_W = 96  # right gutter for the value printed after each bar
_TOP = 66  # space for the title + subtitle
_ROW_H = 32
_BAR_H = 18
_PLOT_W = _WIDTH - _LABEL_W - _VALUE_W

_STYLE = """
  .bg{fill:#ffffff}
  text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;fill:#1a1a1a}
  .title{font-size:16px;font-weight:600}
  .sub{font-size:11px;fill:#666}
  .label{font-size:12px}
  .value{font-size:12px;fill:#333}
  .track{fill:#ececec}
  .bar{fill:#4c8dff}
  @media (prefers-color-scheme:dark){
    .bg{fill:#0d1117}
    text{fill:#e6edf3}.sub{fill:#9aa0a6}.value{fill:#c9d1d9}
    .track{fill:#21262d}.bar{fill:#5b8def}
  }
""".strip()


def _bar_chart(
    title: str,
    subtitle: str,
    labels: list[str],
    values: list[float],
    fmt: Callable[[float], str],
    *,
    vmax: float | None = None,
) -> str:
    """One horizontal bar chart. `vmax` fixes the axis (e.g. 1.0 for a rate);
    otherwise it is the largest value, so the widest bar always fills the plot."""
    n = len(labels)
    height = _TOP + _ROW_H * n + 16
    scale_max = vmax if vmax is not None else (max(values) if values else 0)
    scale_max = scale_max or 1.0  # all-zero data still renders (zero-width bars)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{height}" '
        f'viewBox="0 0 {_WIDTH} {height}" role="img">',
        f"<style>{_STYLE}</style>",
        f'<rect class="bg" width="{_WIDTH}" height="{height}"/>',
        f'<text class="title" x="16" y="26">{escape(title)}</text>',
        f'<text class="sub" x="16" y="44">{escape(subtitle)}</text>',
    ]
    for i, (label, value) in enumerate(zip(labels, values, strict=True)):
        cy = _TOP + _ROW_H * i
        bar_w = round(_PLOT_W * max(value, 0) / scale_max, 1)
        text_y = cy + _BAR_H - 4
        parts += [
            f'<text class="label" x="{_LABEL_W - 10}" y="{text_y}" '
            f'text-anchor="end">{escape(label)}</text>',
            f'<rect class="track" x="{_LABEL_W}" y="{cy}" '
            f'width="{_PLOT_W}" height="{_BAR_H}" rx="2"/>',
            f'<rect class="bar" x="{_LABEL_W}" y="{cy}" width="{bar_w}" height="{_BAR_H}" rx="2"/>',
            f'<text class="value" x="{_LABEL_W + _PLOT_W + 8}" y="{text_y}">'
            f"{escape(fmt(value))}</text>",
        ]
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _specs(
    rows: list[dict[str, Any]],
) -> list[tuple[str, str, list[float], Callable[[float], str], float | None]]:
    return [
        ("pass-rate.svg", "Pass rate", [r["pass_rate"] for r in rows], lambda v: f"{v:.0%}", 1.0),
        (
            "mean-tokens.svg",
            "Mean tokens per item",
            [r["mean_tokens"] for r in rows],
            lambda v: f"{v:,.0f}",
            None,
        ),
        (
            "mean-llm-calls.svg",
            "Mean LLM calls per item",
            [r["mean_llm_calls"] for r in rows],
            lambda v: f"{v:.2f}",
            None,
        ),
        (
            "est-cost.svg",
            "Estimated cost (USD, whole run)",
            [r["est_cost_usd"] for r in rows],
            lambda v: f"${v:.4f}",
            None,
        ),
    ]


def write_charts(record: dict[str, Any]) -> Path:
    """Render the four charts for `record` into `<scorecard dir>/charts/` and
    return that directory. Raises if the run has no available framework."""
    rows = [r for r in _aggregate(record) if r.get("available")]
    if not rows:
        raise ValueError("no available frameworks in this run - nothing to chart")

    out_dir = output_dir_for(record) / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)

    subtitle = f"{record['arena']} · {record['model']} · {record['started_at']}"
    if record.get("mode") == "mock":
        subtitle += "  — mock mode: plumbing only, not a quality signal"

    labels = [r["framework"] for r in rows]
    index = [f"# Charts — `{record['arena']}`", "", f"_{subtitle}_", ""]
    for fname, title, values, fmt, vmax in _specs(rows):
        (out_dir / fname).write_text(
            _bar_chart(title, subtitle, labels, values, fmt, vmax=vmax), encoding="utf-8"
        )
        index.append(f"## {title}\n\n![{title}]({fname})\n")
    (out_dir / "index.md").write_text("\n".join(index), encoding="utf-8")
    return out_dir
