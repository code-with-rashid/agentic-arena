"""MkDocs build hook: point links that leave the docs tree at GitHub.

Several pages deep-link to files outside `docs/` — `ROADMAP.md`, adapter source
under `frameworks/`, tests under `tests/`. Those links are correct for reading
the repo on GitHub, but they are not part of the rendered site, so MkDocs flags
them (and `--strict` turns that into a build failure).

Rather than dilute the source with absolute URLs or relax the build, this
rewrites exactly those links — relative targets that resolve outside `docs/` —
to `https://github.com/.../blob/main/<path>` while the site builds. Links that
stay inside the docs tree are left untouched.
"""

from __future__ import annotations

import posixpath
import re

_BLOB = "https://github.com/code-with-rashid/agentic-arena/blob/main"

# [text](target) and ![alt](target); target up to a '#fragment' or ')'.
_LINK = re.compile(r"(!?\]\()([^)#\s]+)(#[^)\s]*)?(\))")


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


def on_page_markdown(markdown: str, *, page, config, files) -> str:  # noqa: ARG001
    return _rewrite(markdown, page.file.src_uri)
