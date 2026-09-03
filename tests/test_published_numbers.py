"""Every published `tool_use` overhead number still matches what the code produces.

`tests/test_doc_links.py` gates that a cross-reference *resolves*. Nothing gated
that a **number** is still true, and the failure mode is worse than a dead link:
a stale figure reads as current.

It has already happened, and it took five iterations to notice. The tool-schema
audit proved that three frameworks measured cheaper on the wire only because they
were declaring narrower tools, and corrected `findings.md`, `overhead.md`,
`decision-guide.md` and the README. It missed four per-framework pages. Two of
them went on asserting that a framework is **cheaper than the hand-rolled
baseline** — the exact claim that had been withdrawn — until somebody happened to
open one of those pages for an unrelated reason.

So this holds the docs to the run record:

  * every page that quotes a `tool_use` prompt-token count or a `× baseline`
    ratio must quote the measured one;
  * every page that is *supposed* to carry such a claim must still carry it, so
    deleting or rewording one fails rather than quietly reducing coverage.

**Blockquotes are skipped, deliberately.** A `>` block is where a doc quotes its
own history — the "Correction." notes on the framework pages say what a number
*used to be*, and pinning those to the current measurement would make it
impossible to write down that a number ever changed. That is already the repo's
convention rather than an escape hatch invented here, and
`test_a_blockquoted_number_is_left_alone` pins it so the exemption cannot silently
widen.

Scope, stated rather than implied: **only the `tool_use` overhead family**. That
is the most-cited number set in the repo and the one that has actually gone wrong.
Not covered, and not claimed to be: the delegation-depth tables (measured inside
`tests/test_delegation_depth.py`, whose own docstring carries them — a different
problem), the `resilience` recovery counts, the transport retry counts, and every
prose ratio derived from these rather than measured directly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Doc page -> the framework it is about. The per-framework pages are named for
# the library rather than the adapter, so the mapping is written out.
PAGE_FRAMEWORK = {
    "docs/frameworks/langgraph.md": "langgraph",
    "docs/frameworks/pydantic-ai.md": "pydantic_ai",
    "docs/frameworks/openai-agents-sdk.md": "openai_agents",
    "docs/frameworks/microsoft-agent-framework.md": "microsoft_af",
    "docs/frameworks/google-adk.md": "google_adk",
    "docs/frameworks/smolagents.md": "smolagents",
}
SLUG_FRAMEWORK = {Path(page).name: fw for page, fw in PAGE_FRAMEWORK.items()}
# `vanilla` has no deep-dive page of its own - it lives beside its code - but it
# is the baseline every ratio is against, so it appears in the summary tables.
KNOWN = set(PAGE_FRAMEWORK.values()) | {"vanilla"}

# Pages that must keep carrying a claim, and how many. Without this the whole
# file passes by finding nothing: delete the row from a framework page and every
# assertion below is vacuously true. The counts are deliberately exact.
EXPECTED_CLAIMS = {
    "docs/findings.md": 14,  # 7 frameworks x (tokens, ratio)
    "docs/decision-guide.md": 14,
    "docs/frameworks/langgraph.md": 1,  # tokens only; the ratio is prose
    "docs/frameworks/pydantic-ai.md": 2,
    "docs/frameworks/openai-agents-sdk.md": 2,
    "docs/frameworks/microsoft-agent-framework.md": 2,
    # These two present the same measurement as a heading plus a sentence rather
    # than a results-table row: one ratio, then its own tokens and the baseline's.
    "docs/frameworks/google-adk.md": 3,
    "docs/frameworks/smolagents.md": 3,
    "docs/frameworks/README.md": 1,
}

# Published to one decimal in the summary tables and rounded to whole tokens on
# the framework pages, so 753.5 is legitimately written as either 753.5 or 754.
TOKEN_TOLERANCE = 0.6
# Ratios are published to two decimals.
RATIO_TOLERANCE = 0.006

_NUM = r"(\d+(?:\.\d+)?)"
# "794 prompt tok/item" / "794 prompt tok/item, 1.05x baseline"
ROW = re.compile(rf"{_NUM}\s+prompt tok/item(?:,\s*{_NUM}\s*[x×]\s*baseline)?")
# "### Prompt size: 1.11x baseline"
HEADING_RATIO = re.compile(rf"^#{{1,6}}\s+Prompt size:\s*{_NUM}\s*[x×]\s*baseline")
# "836 estimated prompt tokens per item against `vanilla`'s 754"
AGAINST = re.compile(
    rf"{_NUM}\s+estimated prompt tokens per item against\s+`vanilla`'s\s+{_NUM}",
)
# "**3.90x baseline on the wire**", on a row linking to a framework page
README_ROW = re.compile(rf"\]\((\S+\.md)\).*?{_NUM}\s*[x×]\s*baseline on the wire")
# "| `pydantic_ai` | 794.0 | 1.05x |" - the summary tables in findings/decision-guide
TABLE = re.compile(rf"^\|\s*`?([a-z_]+)`?[^|]*\|\s*{_NUM}\s*\|\s*\**{_NUM}\s*[x×]\**\s*\|")


def _claims(path: Path) -> list[tuple[str, str, float]]:
    """(framework, kind, value) for every live overhead claim on this page.

    `kind` is "tokens" or "ratio". Lines inside a blockquote are skipped - see the
    module docstring for why that is the right rule rather than a loophole.
    """
    rel = path.relative_to(ROOT).as_posix()
    own = PAGE_FRAMEWORK.get(rel)
    found: list[tuple[str, str, float]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith(">"):
            continue

        match = README_ROW.search(line)
        if match:
            framework = SLUG_FRAMEWORK.get(Path(match.group(1)).name)
            if framework:
                found.append((framework, "ratio", float(match.group(2))))
            continue

        match = TABLE.match(line)
        if match and match.group(1) in KNOWN:
            found.append((match.group(1), "tokens", float(match.group(2))))
            found.append((match.group(1), "ratio", float(match.group(3))))
            continue

        if own is None:
            continue

        match = HEADING_RATIO.match(line)
        if match:
            found.append((own, "ratio", float(match.group(1))))
            continue

        match = AGAINST.search(line)
        if match:
            found.append((own, "tokens", float(match.group(1))))
            found.append(("vanilla", "tokens", float(match.group(2))))
            continue

        match = ROW.search(line)
        if match:
            found.append((own, "tokens", float(match.group(1))))
            if match.group(2):
                found.append((own, "ratio", float(match.group(2))))
    return found


ALL_CLAIMS = {page: _claims(ROOT / page) for page in EXPECTED_CLAIMS}


def _newest_source_mtime():
    """When the measurement-affecting code last changed.

    A run record older than the adapters is not evidence about the current code,
    and comparing docs against one would turn this file into a test that passes
    because it is out of date - the exact failure it exists to prevent.
    """
    sources = [*(ROOT / "frameworks").rglob("adapter.py"), *(ROOT / "arena").rglob("*.py")]
    return max((p.stat().st_mtime for p in sources), default=0.0)


def _measured():
    """Mean prompt tokens per item per framework, from a usable `tool_use` run.

    Read from a run record rather than re-measured here: CI's comparison job
    already produces one for `report_overhead.py` a step earlier, and that job is
    the only place every framework is installed.

    "Usable" is doing real work. The *latest* record is not good enough - the
    offline suite writes single-framework `tool_use` runs of its own, so locally
    the newest file is routinely a one-entry run that would silently check
    nothing. So: the newest record that carries `vanilla` **and** at least one
    other framework, and that is newer than every adapter and harness source
    file. Otherwise there is nothing here worth comparing against and the
    comparisons skip.

    In CI that record is always the one produced moments earlier in the same job.
    Locally the freshness check is what stops a stale run from vouching for docs
    you have just invalidated.
    """
    newest_source = _newest_source_mtime()
    for path in sorted((ROOT / "runs").glob("*__tool_use__mock.json"), reverse=True):
        record = json.loads(path.read_text(encoding="utf-8"))
        means = {}
        for framework in record["frameworks"]:
            items = framework.get("items") or []
            if framework.get("available") and items:
                means[framework["framework"]] = sum(i["prompt_tokens"] for i in items) / len(items)
        if "vanilla" in means and len(means) > 1:
            if path.stat().st_mtime < newest_source:
                return None
            return means
    return None


MEASURED = _measured()
SKIP_REASON = (
    "no tool_use mock run newer than the adapters, carrying vanilla and at least one "
    "other framework - run `python -m arena run --arena tool_use --framework all "
    "--mode mock --no-scorecard` in a venv that has the frameworks installed"
)


@pytest.mark.parametrize("page", sorted(EXPECTED_CLAIMS))
def test_every_page_still_carries_the_claim_it_is_meant_to(page):
    """Coverage is pinned, because silence here would look exactly like success.

    A reworded sentence or a deleted table row stops matching, and every
    comparison below then passes over nothing. The counts are exact rather than a
    floor so that adding a claim is also a deliberate act.
    """
    assert len(ALL_CLAIMS[page]) == EXPECTED_CLAIMS[page], (
        f"{page} yielded {len(ALL_CLAIMS[page])} overhead claim(s), expected "
        f"{EXPECTED_CLAIMS[page]}: {ALL_CLAIMS[page]}. If the wording changed, update "
        f"the patterns in this file; if a claim was removed on purpose, update "
        f"EXPECTED_CLAIMS in the same commit."
    )


def test_the_pages_agree_with_each_other():
    """The same framework must not be given two different numbers in two places.

    Checkable with no framework installed, which matters: this is the half that
    runs in `lint-and-test`, and it is exactly the failure that actually happened
    — `findings.md` said 1.05x for `pydantic_ai` while its own page said 0.96x,
    and the two sat in the repo together for five iterations.
    """
    seen: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for page, claims in ALL_CLAIMS.items():
        for framework, kind, value in claims:
            seen.setdefault((framework, kind), []).append((page, value))

    disagreements = []
    for (framework, kind), entries in sorted(seen.items()):
        tolerance = TOKEN_TOLERANCE if kind == "tokens" else RATIO_TOLERANCE
        values = [value for _, value in entries]
        if max(values) - min(values) > tolerance:
            disagreements.append(f"{framework} {kind}: {entries}")
    assert not disagreements, "pages disagree about the same measurement:\n" + "\n".join(
        disagreements
    )


@pytest.mark.skipif(MEASURED is None, reason=SKIP_REASON)
@pytest.mark.parametrize("page", sorted(EXPECTED_CLAIMS))
def test_the_published_numbers_match_the_run(page):
    """The half that needs the frameworks installed: docs against the wire.

    Only frameworks present in the run record are checked, so this is meaningful
    in CI's comparison job and harmless in a venv carrying one library. A claim
    about a framework that is not in the record is not silently passed - it is
    reported as unchecked by the test below.
    """
    wrong = []
    for framework, kind, claimed in ALL_CLAIMS[page]:
        if framework not in MEASURED:
            continue
        if kind == "tokens":
            actual, tolerance = MEASURED[framework], TOKEN_TOLERANCE
        else:
            actual, tolerance = MEASURED[framework] / MEASURED["vanilla"], RATIO_TOLERANCE
        if abs(claimed - actual) > tolerance:
            wrong.append(f"  {framework} {kind}: page says {claimed}, run says {actual:.2f}")
    assert not wrong, (
        f"{page} publishes numbers the code no longer produces:\n"
        + "\n".join(wrong)
        + "\nRegenerate with `python -m arena run --arena tool_use --framework all "
        "--mode mock --no-scorecard`. If the change is intended, correct the page in "
        "this commit - and if the old number was published, say so in a blockquote "
        "rather than deleting it."
    )


@pytest.mark.skipif(MEASURED is None, reason=SKIP_REASON)
def test_the_comparison_is_not_running_on_an_empty_set():
    """A run record with one framework in it would make the test above near-vacuous.

    Not an assertion about how many frameworks exist - a venv carrying a single
    library is a legitimate way to run this suite. It fails only if the record has
    the baseline and nothing else, which means the comparison job's install step
    silently produced a one-framework run and every doc number went unchecked.
    """
    checked = {
        framework
        for claims in ALL_CLAIMS.values()
        for framework, _, _ in claims
        if framework in MEASURED
    }
    assert checked, "no claimed framework appears in the run record at all"
    if len(MEASURED) > 2:
        assert len(checked) > 1, f"only {checked} was checked against a run of {set(MEASURED)}"


def test_a_blockquoted_number_is_left_alone():
    """The exemption is tested, not assumed.

    Superseded numbers are kept on the page in a `>` block so a reader can see
    that a figure changed and why. If that stopped being skipped, the honest thing
    to do with a correction would become deleting it, so the rule is pinned here
    rather than left as a comment.
    """
    corrections = ROOT / "docs" / "frameworks" / "pydantic-ai.md"
    body = corrections.read_text(encoding="utf-8")
    assert "0.96" in body, (
        "the superseded pydantic_ai ratio is no longer written down on its own page - "
        "this test needs a real blockquoted number to prove the rule"
    )
    assert not [c for c in _claims(corrections) if c[2] == 0.96], (
        "a number inside a blockquote was collected as a live claim"
    )
