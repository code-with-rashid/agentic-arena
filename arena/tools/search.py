"""A deterministic stand-in for web search.

Backed by a small fixed corpus (`corpus.json`) so results never drift between runs
or machines. Every adapter gets exactly this function.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_CORPUS_PATH = Path(__file__).with_name("corpus.json")
_WORD = re.compile(r"[a-z0-9]+")


@lru_cache(maxsize=1)
def _corpus() -> list[dict[str, str]]:
    return json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def search(query: str, k: int = 3) -> str:
    """Return the top-k corpus snippets most relevant to `query`, as plain text."""
    q = _tokens(query)
    if not q:
        return "No results."
    scored: list[tuple[int, dict[str, str]]] = []
    for doc in _corpus():
        overlap = len(q & _tokens(doc["title"] + " " + doc["text"]))
        if overlap:
            scored.append((overlap, doc))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    hits = [doc for _, doc in scored[:k]]
    if not hits:
        return "No results."
    return "\n\n".join(f"[{doc['title']}] {doc['text']}" for doc in hits)
