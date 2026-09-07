"""Two tool calls in one assistant turn: does every framework run both?

A model may return several tool calls in a single turn, and a framework that
quietly executes only the first would give the model half its evidence and still
look fine — the answer is scripted in mock mode, so nothing else here would
notice.

**With two valid calls, all seven adapters handle it correctly** — both run, both
results reach the model. That half is a negative result and lives here as a test
rather than as an arena: an arena everybody passes adds runtime and dilutes the
scorecard without discriminating between anything.

The half that *does* discriminate is what happens when one call in the batch is
broken. For each fault, batched with one good call, asking two questions of the
next request — did the *successful* call's result reach the model, and was the
broken call reported at all:

                          | unknown tool | malformed args | missing arg |
    vanilla               | both         | both           | both        |
    pydantic_ai           | both         | both           | both        |
    microsoft_af          | both         | both           | both        |
    langgraph             | both         | good only  (1) | both        |
    smolagents            | error only(2)| good only  (1) | error only  |
    openai_agents         | raises    (3)| both           | both        |
    google_adk            | raises    (3)| raises      (3)| both        |

Three distinct ways to mishandle a batch, and they are not equally bad:

 (1) **Silent partial.** The broken call vanishes with no message of any kind.
     The run continues and answers from partial evidence, and the model is never
     told a call went missing. This is the quietest failure here.
 (2) **The successful sibling is discarded.** smolagents reports the error, but
     as a *rewritten task* ("New task: ... Error: ... Now let's retry") rather
     than as a turn in the transcript — and the good call's observation is
     dropped along with the history. The model then re-emits the identical batch,
     because from its point of view it never ran anything.
 (3) **Raises.** Loud, and the same root cause as those frameworks' `resilience`
     losses (`res-02` for openai_agents; `res-01` and `res-02` for google_adk).
     Nothing is silently wrong, which makes it the best of the three.

That is a different question from the one the `resilience` arena asks, which is
whether a framework recovers; this asks whether it tells the truth about what
happened on the way.

It also refines a published claim. `langgraph` losing malformed tool arguments
(`res-01`) turns out to be conditional: alone, the malformed call produces no
tool message and the graph simply halts; batched with a call that succeeds, the
graph carries on and the drop becomes invisible.

The per-framework numbers are documented in docs/feature-matrix.md rather than
asserted here, following the same rule as `resilience`: differences between
frameworks are findings, not test failures. What is gated here are the
invariants — valid batches must work, the baseline must surface every result, and
batching must never make a framework *worse* than it is serially.
"""

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from arena.config import ArenaConfig
from arena.llm.mockserver import MockScript, MockServer
from arena.registry import available_frameworks, load_arena, load_framework
from arena.types import ArenaSpec, EvalItem

STUBS = {"claude_agent_sdk"}
ANSWER = "The Burj Khalifa is 498 metres taller than the Eiffel Tower."
ITEM = EvalItem(
    id="par-01", input="How much taller is the Burj Khalifa than the Eiffel Tower?", checks=[]
)

GOOD = [
    {"name": "search", "arguments": {"query": "Burj Khalifa"}},
    {"name": "search", "arguments": {"query": "Eiffel Tower"}},
]
# One good call plus one broken one, in a single turn.
FAULTS = {
    "unknown tool": {"name": "teleport", "arguments": {"destination": "mars"}},
    "malformed args": {"name": "search", "arguments": '{"query": "Eiffel'},
    "missing required arg": {"name": "search", "arguments": {}},
}


def _arena():
    return ArenaSpec(
        id="parallel",
        description="two tool calls in one turn",
        tools=["search"],
        system_prompt_intent="\nCompare two landmarks. Use `search` for each.\n",
        dataset=[],
        mock_script_path="",
    )


def _buildable():
    out = []
    for name in available_frameworks():
        if name in STUBS or name.endswith("_multi"):
            continue
        try:
            config = replace(ArenaConfig(mode="mock"), base_url="http://127.0.0.1:1", api_key="k")
            load_framework(name).build(_arena(), config)
        except Exception:  # noqa: BLE001 - not installed in this venv
            continue
        out.append(name)
    return out


BUILDABLE = _buildable()


def _run(name, calls):
    """Run one item whose first turn asks for `calls`. Returns (outcome, requests).

    `outcome` is "answered", "gave up", or the exception type — the same three
    ways a framework can end a run in the `resilience` arena.
    """
    script = MockScript({"default": {"turns": [{"tool_calls": calls}, {"content": ANSWER}]}})
    with MockServer(script) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        try:
            result = load_framework(name).build(_arena(), config).run(ITEM)
        except Exception as exc:  # noqa: BLE001 - the outcome under test
            return type(exc).__name__, server.requests
        outcome = "answered" if "498" in (result.output_text or "") else "gave up"
        return outcome, server.requests


@pytest.mark.parametrize("name", BUILDABLE)
def test_both_tool_calls_in_one_turn_are_executed(name):
    """Half the evidence would still produce the scripted answer. Check the wire."""
    outcome, requests = _run(name, GOOD)
    assert outcome == "answered", f"{name}: {outcome}"

    # Both results must reach the model, not just the first.
    sent = ""
    for message in requests[-1].get("messages", []):
        if message.get("role") == "system":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            sent += content
        elif isinstance(content, list):
            sent += "".join(p.get("text", "") for p in content if isinstance(p, dict))

    for landmark in ("Burj Khalifa", "Eiffel Tower"):
        assert f"[{landmark}]" in sent, (
            f"{name}: only one of two parallel tool results reached the model ({landmark} missing)"
        )


@pytest.mark.parametrize("fault", list(FAULTS))
@pytest.mark.parametrize("name", BUILDABLE)
def test_batching_never_makes_a_framework_worse(name, fault):
    """A batch may rescue a fault, but must never turn a working case into a broken one.

    Batching is *not* neutral — `langgraph` answers when a malformed call is
    batched with a good one and halts when it is alone. That direction is
    tolerable. The other direction is not: a framework that handles a fault on its
    own but loses the item once a second call is present would be dropping work
    it had already done.
    """
    serial, _ = _run(name, [FAULTS[fault]])
    batched, _ = _run(name, [GOOD[0], FAULTS[fault]])
    if serial == "answered":
        assert batched == "answered", (
            f"{name}: handles '{fault}' alone but ends as {batched!r} when batched "
            f"with a second call — batching lost work it had already done"
        )


# The successful call in every batch below is `search("Burj Khalifa")`, and this
# bracketed title appears in the corpus entry it returns and nowhere else.
GOOD_MARKER = "[Burj Khalifa]"

# How each framework words the broken call's outcome. Every one of these is
# absent from `arena/tools/corpus.json`, checked by a test below, so a match
# means the framework reported the fault rather than the corpus mentioning it.
FAULT_MARKERS = ("error", "invalid", "unknown tool", "required", "no results")


def _model_visible_text(request):
    """Everything in a request the model can read that is not its own words.

    System and assistant turns are skipped: the assistant turn is the framework
    echoing back the tool call it just made, so the fault's own text appears
    there whether or not a result ever came back.
    """
    parts = []
    for message in request.get("messages", []):
        if message.get("role") in ("system", "assistant"):
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            parts.extend(p.get("text", "") for p in content if isinstance(p, dict))
    return "\n".join(parts)


def _outcomes_reaching_model(request):
    """(good result seen, broken call reported) for a batch of one good + one broken call.

    Matches each outcome's own text rather than counting messages, because no
    count is correct across these protocols. Counting `role == "tool"` messages
    reads 0 for smolagents, which feeds results back as `user` turns; counting
    the word "observation" — which an earlier version of this helper did — reads
    *3* for two results, because the corpus entry for Tokyo Tower calls it a
    "communications and observation tower". That contamination inflated a
    published number and is the reason this is two booleans and not an integer.

    "observation" is the only one of these markers the corpus contains, which
    `test_the_fault_markers_do_not_appear_in_the_corpus` pins.
    """
    text = _model_visible_text(request)
    good = GOOD_MARKER in text
    broken = any(marker in text.lower() for marker in FAULT_MARKERS)
    return good, broken


def test_the_fault_markers_do_not_appear_in_the_corpus():
    """The instrument above is only sound while the corpus stays clear of its markers.

    An earlier version of this file counted the word "observation" and read 3
    for a batch of 2, because a corpus entry describes Tokyo Tower as a
    "communications and observation tower". That is the failure this pins: if a
    future corpus entry mentions an error or a requirement, the fault marker
    would start matching the successful result and every number below would
    quietly drift.
    """
    corpus = json.dumps(json.loads(Path("arena/tools/corpus.json").read_text(encoding="utf-8")))
    found = [m for m in FAULT_MARKERS if m in corpus.lower()]
    assert not found, f"corpus now contains fault marker(s) {found} — the probe would over-report"
    assert GOOD_MARKER.strip("[]").lower() in corpus.lower(), "the good marker left the corpus"


@pytest.mark.parametrize("fault", list(FAULTS))
def test_the_baseline_tells_the_model_about_every_call_in_the_batch(fault):
    """The control must never answer from partial evidence in silence.

    Two calls go out, so both outcomes must come back — the broken one as an
    error the model can read and correct from. Frameworks that report fewer are
    a measured finding (see the module docstring); the baseline reporting fewer
    would mean this probe is wrong.
    """
    outcome, requests = _run("vanilla", [GOOD[0], FAULTS[fault]])
    assert outcome == "answered", f"baseline lost '{fault}': {outcome}"
    assert len(requests) >= 2, f"baseline halted after one request on '{fault}'"
    good, broken = _outcomes_reaching_model(requests[1])
    assert good, f"baseline dropped the *successful* call's result on '{fault}'"
    assert broken, (
        f"baseline never told the model the second call failed on '{fault}' — it would be "
        f"answering from partial evidence without being told"
    )


def test_the_stdlib_baseline_recovers_from_every_batched_fault():
    """If the control cannot recover, the probe is broken rather than the framework."""
    for fault, call in FAULTS.items():
        outcome, _ = _run("vanilla", [GOOD[0], call])
        assert outcome == "answered", f"baseline lost '{fault}': {outcome}"


def test_the_shared_arena_tools_are_unchanged_by_this_file():
    """This file builds its own ArenaSpec; it must not have drifted from the real one."""
    assert _arena().tools == ["search"]
    assert "search" in load_arena("tool_use").tools


# --- the batched-fault table is copied to two doc pages; keep them in step -----

_ROOT = Path(__file__).resolve().parent.parent
_BATCH_PAGES = ("docs/findings.md", "docs/feature-matrix.md")
_FAULT_COLS = ("unknown tool", "malformed args", "missing")
_CELL_VALUES = {"both", "good only", "error only", "raises"}
_BATCH_FRAMEWORKS = {
    "vanilla",
    "pydantic_ai",
    "microsoft_af",
    "langgraph",
    "smolagents",
    "openai_agents",
    "google_adk",
}


def _batched_fault_table(page):
    """{framework: (unknown, malformed, missing)} parsed off a doc page.

    Both pages carry the same table; `findings.md` groups the three "both/both/
    both" frameworks on one row and `feature-matrix.md` lists them separately, so
    a leading cell may name more than one framework.
    """
    text = (_ROOT / page).read_text(encoding="utf-8")
    rows: dict[str, tuple[str, str, str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|") or line.startswith(("|--", "| |", "| unknown")):
            continue
        cells = [c.strip().replace("*", "") for c in line.strip("|").split("|")]
        if len(cells) != 4:
            continue
        names = re.findall(r"`([a-z_]+)`", cells[0])
        values = tuple(cells[1:])
        if not names or any(v not in _CELL_VALUES for v in values):
            continue
        for name in names:
            rows[name] = values
    return rows


@pytest.mark.parametrize("page", _BATCH_PAGES)
def test_the_batched_fault_table_is_complete_on_each_page(page):
    """Every framework's row is present — a deleted row must fail, not pass quietly."""
    got = set(_batched_fault_table(page))
    assert got == _BATCH_FRAMEWORKS, (
        f"{page}: batched-fault table covers {sorted(got)}, expected {sorted(_BATCH_FRAMEWORKS)}"
    )


def test_the_batched_fault_table_agrees_across_the_docs():
    """`findings.md` §2b and `feature-matrix.md` publish the same table.

    The per-framework cells are findings, not gated against a run — but the two
    copies must say the same thing. A correction that reaches one page and not
    the other is the exact failure `test_published_numbers.py` was built for,
    now for the one other multi-page results table.
    """
    findings, matrix = (_batched_fault_table(p) for p in _BATCH_PAGES)
    disagreements = [
        f"{fw}: findings={findings[fw]} feature-matrix={matrix[fw]}"
        for fw in sorted(_BATCH_FRAMEWORKS)
        if findings.get(fw) != matrix.get(fw)
    ]
    assert not disagreements, "the batched-fault table disagrees between pages:\n" + "\n".join(
        disagreements
    )


def _measured_batch_verdict(name, fault):
    """`both` / `good only` / `error only` / `raises` for one broken call batched
    with one good one, measured the way the doc table was.

    `_run` returns the exception class name (not "answered"/"gave up") when the
    framework raises, and a raise means no second request the model ever saw —
    so either signal is "raises".
    """
    outcome, requests = _run(name, [GOOD[0], FAULTS[fault]])
    if outcome not in ("answered", "gave up") or len(requests) < 2:
        return "raises"
    good, broken = _outcomes_reaching_model(requests[1])
    if good and broken:
        return "both"
    if good:
        return "good only"
    if broken:
        return "error only"
    return "neither"


@pytest.mark.parametrize("name", BUILDABLE)
def test_the_batched_fault_table_matches_a_fresh_measurement(name):
    """Re-measure this framework's row and hold it to what `findings.md` §2b prints.

    iteration 62 gated that the two doc copies agree with *each other*; this
    gates that they agree with the *code*. The sibling `resilience` table drifted
    (smolagents 4/8 -> 8/8) for iterations with nothing noticing, precisely
    because its per-framework counts were reported and never re-checked. This is
    cheap — three faults, one run each — so there is no reason to leave it
    exposed the same way.
    """
    published = _batched_fault_table("docs/findings.md").get(name)
    if published is None:
        pytest.skip(f"{name} is not in the published batched-fault table")
    measured = tuple(_measured_batch_verdict(name, fault) for fault in FAULTS)
    assert measured == published, (
        f"{name}: batched-fault row measured {measured}, docs/findings.md §2b says "
        f"{published}. If the change is real, correct §2b and feature-matrix.md together."
    )
