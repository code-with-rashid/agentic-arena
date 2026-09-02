"""Every relative link and heading anchor in the docs actually resolves.

Fifteen iterations of findings have left the documentation heavily
cross-referenced — `findings.md` points at eight other pages, most of them at a
specific section, and the per-framework deep dives point back. A renamed heading
breaks those silently: the link still renders, GitHub still serves the page, and
the reader lands at the top with no idea what they were meant to see.

Checks two things, both mechanical:

  * a relative link's target file exists;
  * an `#anchor` matches a heading in that file, using GitHub's slug rules
    (lowercase, punctuation dropped, spaces to hyphens).

Deliberately not checked: external `http(s)://` links, which would make the
suite depend on the network and on other people's uptime.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# Inline links only. Image links and bare autolinks carry no anchors worth
# checking, and code spans are stripped first so examples in fenced blocks do
# not register as links.
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.MULTILINE)
FENCE = re.compile(r"```.*?```", re.DOTALL)


def _markdown_files():
    skip = {".git", "node_modules", ".venv", "runs", "__pycache__"}
    return sorted(
        p for p in ROOT.rglob("*.md") if not any(part in skip for part in p.relative_to(ROOT).parts)
    )


def _slug(heading):
    """GitHub's anchor rules: lowercase, strip punctuation, spaces to hyphens.

    Inline formatting is removed first — a heading written as ``### `faults` and
    the wire`` anchors as `faults-and-the-wire`, with the backticks gone rather
    than slugged.
    """
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"\*\*?([^*]*)\*\*?", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def _anchors(path):
    body = FENCE.sub("", path.read_text(encoding="utf-8"))
    return {_slug(h) for h in HEADING.findall(body)}


MARKDOWN = _markdown_files()


@pytest.mark.parametrize("path", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_relative_link_resolves(path):
    """A link to a file that does not exist is a typo nobody notices until a reader does."""
    body = FENCE.sub("", path.read_text(encoding="utf-8"))
    broken = []
    for target in LINK.findall(body):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        file_part = target.split("#", 1)[0]
        if not file_part:
            continue
        if not (path.parent / file_part).resolve().exists():
            broken.append(target)
    assert not broken, f"{path.relative_to(ROOT)} links to missing file(s): {broken}"


@pytest.mark.parametrize("path", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_heading_anchor_resolves(path):
    """The failure mode this exists for: a heading gets reworded, the link still renders.

    GitHub does not 404 on a bad anchor — it serves the page scrolled to the top.
    So a stale deep link looks exactly like a working one to whoever wrote it,
    and sends the reader to the wrong place forever.
    """
    body = FENCE.sub("", path.read_text(encoding="utf-8"))
    broken = []
    for target in LINK.findall(body):
        if target.startswith(("http://", "https://", "mailto:")) or "#" not in target:
            continue
        file_part, _, anchor = target.partition("#")
        if not anchor:
            continue
        other = (path.parent / file_part).resolve() if file_part else path
        if other.suffix != ".md" or not other.exists():
            continue
        if anchor not in _anchors(other):
            broken.append(target)
    assert not broken, (
        f"{path.relative_to(ROOT)} points at heading(s) that no longer exist: {broken}"
    )
