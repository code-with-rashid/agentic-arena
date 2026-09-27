"""MkDocs build hook for repository links and product-profile summaries.

Several pages deep-link to files outside `docs/` — `ROADMAP.md`, adapter source
under `frameworks/`, tests under `tests/`. Those links are correct for reading
the repo on GitHub, but they are not part of the rendered site, so MkDocs flags
them (and `--strict` turns that into a build failure).

Rather than dilute the source with absolute URLs or relax the build, this
rewrites exactly those links — relative targets that resolve outside `docs/` —
to `https://github.com/.../blob/main/<path>` while the site builds. Links that
stay inside the docs tree are left untouched.

Framework and coding-harness pages also declare a small front-matter contract.
The hook renders it as a consistent decision, evidence, version, and freshness
summary without duplicating the same HTML across every profile.
"""

from __future__ import annotations

import posixpath
import re
from datetime import date
from html import escape

_BLOB = "https://github.com/code-with-rashid/agentic-arena/blob/main"

# [text](target) and ![alt](target); target up to a '#fragment' or ')'.
_LINK = re.compile(r"(!?\]\()([^)#\s]+)(#[^)\s]*)?(\))")

_PROFILE_TYPE_LABELS = {
    "framework": "Framework / SDK",
    "coding-harness": "Coding agent / harness",
}
_EVIDENCE_STATUS_LABELS = {
    "mock-tested": "Mock-tested",
    "diagnostic-only": "Diagnostic only",
    "protocol-mismatch": "Protocol mismatch",
    "source-reviewed": "Source-reviewed",
    "native-live": "Native live",
    "independently-reproduced": "Independently reproduced",
}


def _rewrite(markdown: str, src_uri: str) -> str:
    src_dir = posixpath.dirname(src_uri)

    def repl(m: re.Match[str]) -> str:
        opener, target, frag, closer = m.group(1), m.group(2), m.group(3) or "", m.group(4)
        if "://" in target or target.startswith(("/", "mailto:", "#")):
            return m.group(0)
        # Resolve relative to the page, treating docs/ as the root of the tree.
        resolved = posixpath.normpath(posixpath.join("docs", src_dir, target))
        if resolved == "docs" or resolved.startswith("docs/"):
            return m.group(0)  # still inside the site
        return f"{opener}{_BLOB}/{resolved}{frag}{closer}"

    return _LINK.sub(repl, markdown)


def _profile_summary(markdown: str, meta: dict) -> str:
    """Render the same decision and evidence summary on every product profile."""
    profile_type = meta.get("profile_type")
    if profile_type not in _PROFILE_TYPE_LABELS:
        return markdown

    status = str(meta.get("evidence_status", "unknown"))
    status_label = _EVIDENCE_STATUS_LABELS.get(status, status.replace("-", " ").title())
    reviewed = escape(str(meta.get("reviewed_version", "Not recorded")))
    verified = str(meta.get("last_verified", "Not recorded"))
    revalidate = str(meta.get("revalidate_after", "Not recorded"))
    try:
        overdue = date.today() > date.fromisoformat(revalidate)
    except ValueError:
        overdue = False
    freshness = f"Review overdue since {revalidate}" if overdue else f"Review due {revalidate}"

    def value(name: str) -> str:
        return escape(str(meta.get(name, "Not recorded")))

    banner = f"""
<aside class="profile-summary" data-evidence-status="{escape(status)}" data-review-overdue="{str(overdue).lower()}" aria-label="Profile decision and evidence summary">
  <div class="profile-summary__meta">
    <span>{_PROFILE_TYPE_LABELS[profile_type]}</span>
    <span>{escape(status_label)}</span>
    <span>Verified {escape(verified)}</span>
    <span>{escape(freshness)}</span>
  </div>
  <dl class="profile-summary__grid">
    <div><dt>Best fit</dt><dd>{value("best_for")}</dd></div>
    <div><dt>What it owns</dt><dd>{value("owns")}</dd></div>
    <div><dt>Important limit</dt><dd>{value("important_limit")}</dd></div>
    <div><dt>Evidence here</dt><dd>{value("evidence_summary")}</dd></div>
  </dl>
  <p class="profile-summary__version"><strong>Reviewed version:</strong> {reviewed} · <a href="../../reference/profile-evidence/">How to read this evidence label</a></p>
</aside>
""".strip()
    heading = re.search(r"^# .+$", markdown, flags=re.MULTILINE)
    if not heading:
        return f"{banner}\n\n{markdown}"
    end = heading.end()
    return f"{markdown[:end]}\n\n{banner}{markdown[end:]}"


def on_page_markdown(markdown: str, *, page, config, files) -> str:  # noqa: ARG001
    markdown = _profile_summary(markdown, page.meta)
    return _rewrite(markdown, page.file.src_uri)
