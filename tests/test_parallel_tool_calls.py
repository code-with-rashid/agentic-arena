"""Two tool calls in one assistant turn: does every framework run both?

A model may return several tool calls in a single turn, and a framework that
quietly executes only the first would give the model half its evidence and still
look fine — the answer is scripted in mock mode, so nothing else here would
notice.

**With two valid calls, all six adapters handle it correctly** — both run, both
results reach the model. That half is a negative result and lives here as a test
rather than as an arena: an arena everybody passes adds runtime and dilutes the
scorecard without discriminating between anything.

The half that *does* discriminate is what happens when one call in the batch is
broken. Counting the tool results that actually reach the model:

    malformed args        langgraph    1 of 2      <- silently dropped
                          everyone else 2 of 2
    missing required arg  smolagents   0 of 2      <- whole batch dropped
                          everyone else 2 of 2

Both are *silent*: the run continues and answers from partial evidence, and the
model is never told a call went missing. That is a different failure mode from
the `resilience` arena, which asks whether a framework recovers; this asks
whether it tells the truth about what happened on the way.

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

from dataclasses import replace

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


def _results_reaching_model(request):
    """Tool results in a follow-up request, however the framework encodes them.

    Not keyed on `role == "tool"`: smolagents feeds results back as `user`
    messages with an "Observation" prefix. Counting what the model can actually
    read is the point.
    """
    seen = 0
    for message in request.get("messages", []):
        role = message.get("role")
        if role == "tool":
            seen += 1
        elif role == "user":
            content = message.get("content", "")
            if not isinstance(content, str):
                content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
            seen += content.lower().count("observation")
    return seen


@pytest.mark.parametrize("fault", list(FAULTS))
def test_the_baseline_tells_the_model_about_every_call_in_the_batch(fault):
    """The control must never answer from partial evidence in silence.

    Two calls go out, so two results must come back — the broken one as an error
    the model can read and correct from. Frameworks that return fewer are a
    measured finding (see the module docstring); the baseline returning fewer
    would mean this probe is wrong.
    """
    outcome, requests = _run("vanilla", [GOOD[0], FAULTS[fault]])
    assert outcome == "answered", f"baseline lost '{fault}': {outcome}"
    assert len(requests) >= 2, f"baseline halted after one request on '{fault}'"
    seen = _results_reaching_model(requests[1])
    assert seen == 2, (
        f"baseline sent {seen} of 2 tool results for '{fault}' — the model would be "
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
