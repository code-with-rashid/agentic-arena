"""Every control the arena owns, and whether it actually reaches the adapter.

Four fairness bugs of the same shape have been found one at a time, each after a
published number had already been built on it:

    max_tool_iterations   three adapters' "loop caps" were not loop caps;
                          a budget of 6 ran 50, 41, and one too many
    request_timeout_s     five of seven never passed it to their client and
                          inherited a ten-minute library default
    arena.tools           two adapters declared a narrower tool than the arena
                          did, dropping a parameter the model never saw
    tool descriptions     all six frameworks cut the sentence telling the model
                          to pause, on the arena that grades pausing

Every one was invisible to mock mode, because the mock replays a script whatever
the adapter sent. The pattern is not "adapters are careless" — it is that a
control the arena owns has to be *carried* by each framework in its own idiom,
and nothing was checking the carrying.

So this file enumerates the controls rather than waiting for the next one to
surface. `docs/fairness-controls.md` is the same table in prose, with where each
is verified.

What is gated here: that every `ArenaConfig` and every `ArenaSpec` field has an
answer; that the configured model and the configured sampling temperature are the
ones on the wire (methodology 1 and 3e — both were rules with nothing behind
them); and that no adapter puts a sampling parameter on the wire that the arena
did not choose. The rest name the file that covers them.
"""

from __future__ import annotations

from dataclasses import fields, replace

import pytest

from arena.config import ArenaConfig
from arena.llm.mockserver import MockScript, MockServer
from arena.registry import available_frameworks, load_arena, load_framework
from arena.types import ArenaSpec, EvalItem

STUBS = {"claude_agent_sdk"}
ARENA = load_arena("tool_use")
SCRIPT = MockScript({"default": {"turns": [{"content": "330 metres."}]}})
ITEM = EvalItem(id="t-01", input="How tall is the Eiffel Tower?", checks=[])

# Deliberately not a real model name. A framework that substituted its own
# default would send something plausible; this cannot be mistaken for one.
CANARY_MODEL = "arena-canary-model-7"

# Deliberately not 0.0. The invariant is "temperature is 0.0 everywhere", held
# until now by ten hard-coded literals; an adapter still sending one of those
# instead of reading the config sends 0.0 here and fails.
CANARY_TEMPERATURE = 0.7

# What the hand-rolled baseline puts in a request body and nothing more. Any key
# outside this set is a sampling choice the arena did not make and nothing is
# holding constant across frameworks.
SAMPLING_ENVELOPE = {"model", "messages", "temperature", "stream", "tools", "tool_choice"}

# The one measured exception, kept as a reviewable declaration rather than a
# pattern match. smolagents sends `stop: ["Observation:", "Calling tools:"]` on
# every request because its text ReAct loop parses generation that halts at those
# markers - intrinsic to the mechanism, not a sampling knob. See
# docs/fairness-controls.md and docs/overhead.md.
SAMPLING_EXCEPTIONS = {
    "smolagents": {"stop"},
    "smolagents_multi": {"stop"},
}

# Every field of ArenaConfig, and where it is held to reaching the adapter.
# `None` means the harness consumes it and no adapter ever sees it.
VERIFIED_BY = {
    "mode": None,
    "model": "tests/test_shared_controls.py",
    "base_url": "tests/test_adapters_contract.py (nothing reaches the mock otherwise)",
    "api_key": None,
    "price_input_per_m": None,
    "price_output_per_m": None,
    "repeat": None,
    "request_timeout_s": "tests/test_transport_faults.py",
    "max_tool_iterations": "tests/test_adapters_contract.py",
    "checkpoint_dir": "tests/test_durable_across_a_restart.py",
    "temperature": "tests/test_shared_controls.py",
}

# Same question for the arena spec, which is where two of the four bugs were.
SPEC_VERIFIED_BY = {
    "id": None,
    "description": None,
    "system_prompt_intent": "tests/test_adapters_contract.py",
    "tools": "tests/test_adapters_contract.py + tests/test_tool_schema_fidelity.py",
    "dataset": None,
    "mock_script_path": None,
    "durable": "tests/test_durable_state.py + tests/test_durable_across_a_restart.py",
}


def _buildable():
    out = []
    for name in available_frameworks():
        if name in STUBS:
            continue
        try:
            config = replace(ArenaConfig(mode="mock"), base_url="http://127.0.0.1:1", api_key="k")
            load_framework(name).build(ARENA, config)
        except Exception:  # noqa: BLE001 - not installed in this venv
            continue
        out.append(name)
    return out


BUILDABLE = _buildable()


def test_every_config_field_is_accounted_for():
    """A new shared control must say where it is checked, or say that nobody sees it.

    This is the cheap half of the whole idea: the four bugs above were all
    "a control existed and nothing verified it arrived". Adding a field to
    `ArenaConfig` now fails here until someone has answered the question.
    """
    declared = {f.name for f in fields(ArenaConfig)}
    unaccounted = declared - set(VERIFIED_BY)
    stale = set(VERIFIED_BY) - declared
    assert not unaccounted, (
        f"new ArenaConfig field(s) {sorted(unaccounted)} — add them to VERIFIED_BY with "
        f"the test that holds adapters to them, or None if the harness consumes it. "
        f"See docs/fairness-controls.md"
    )
    assert not stale, f"VERIFIED_BY names field(s) that no longer exist: {sorted(stale)}"


def test_every_arena_spec_field_is_accounted_for():
    """The same question for `ArenaSpec`, which is where two of the four bugs were.

    `tools` is one field and it went wrong twice in different ways — first the
    *set* of tools (an adapter advertising one the arena never declared), then
    their *shape* (a missing parameter, a cut description). Both are named here,
    because "tools is checked" was true and insufficient the first time.
    """
    declared = {f.name for f in fields(ArenaSpec)}
    unaccounted = declared - set(SPEC_VERIFIED_BY)
    stale = set(SPEC_VERIFIED_BY) - declared
    assert not unaccounted, (
        f"new ArenaSpec field(s) {sorted(unaccounted)} — add them to SPEC_VERIFIED_BY "
        f"with the test that holds adapters to them, or None if adapters never see it. "
        f"See docs/fairness-controls.md"
    )
    assert not stale, f"SPEC_VERIFIED_BY names field(s) that no longer exist: {sorted(stale)}"


@pytest.mark.parametrize("name", BUILDABLE)
def test_the_configured_model_is_the_model_on_the_wire(name):
    """methodology §1: one model for everyone, and no adapter picks its own.

    The repo's most fundamental fairness rule, and until now the only one with
    nothing behind it. An adapter that defaulted to its library's favourite model
    would be *comparing a different model* in every live run — the one difference
    that would invalidate every number at once, and the one mock mode is least
    able to see, since the mock answers to any model name at all.

    Measured across all seven: every adapter propagates it faithfully today.
    That is a negative result; it is pinned because of what it would cost to be
    wrong about it later.

    `google_adk` is the interesting row — it must reach an OpenAI-compatible
    gateway through LiteLLM, so the adapter builds `openai/<model>` and LiteLLM
    strips the prefix again. The name on the wire is still exactly what the arena
    configured.
    """
    with MockServer(SCRIPT, arena_tools=list(ARENA.tools)) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            model=CANARY_MODEL,
            max_tool_iterations=3,
        )
        load_framework(name).build(ARENA, config).run(ITEM)
        seen = {str(request.get("model")) for request in server.requests}

    assert seen, f"{name} made no request"
    assert seen == {CANARY_MODEL}, (
        f"{name} sent model={sorted(seen)} where the arena configured "
        f"{CANARY_MODEL!r} — every live comparison against it would be against a "
        f"different model"
    )


@pytest.mark.parametrize("name", BUILDABLE)
def test_the_configured_temperature_is_on_the_wire(name):
    """methodology 3e: one sampling temperature, and it is a field, not a literal.

    "Temperature is 0.0 everywhere" was an invariant with nothing behind it - ten
    hard-coded `temperature=0.0` literals, one per adapter, and no check that any
    reached the gateway. The same blind spot that hid the unwired iteration
    budget, the unwired request timeout and the narrowed tool schemas: mock mode
    strips control fields before it matches a scripted turn, so an adapter that
    dropped temperature, or a library whose default is 1.0, would be invisible
    offline and would only show up live as that framework sampling differently
    from the rest of the field - read as flakiness, not as a harness bug.

    Built here with a non-zero canary: an adapter still emitting a literal 0.0
    sends the wrong number and fails.
    """
    with MockServer(SCRIPT, arena_tools=list(ARENA.tools)) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            temperature=CANARY_TEMPERATURE,
            max_tool_iterations=3,
        )
        load_framework(name).build(ARENA, config).run(ITEM)
        seen = {request.get("temperature") for request in server.requests}

    assert seen, f"{name} made no request"
    assert seen == {CANARY_TEMPERATURE}, (
        f"{name} sent temperature={sorted(seen, key=str)} where the arena "
        f"configured {CANARY_TEMPERATURE} — every live run would sample "
        f"differently from the other frameworks and it would look like variance"
    )


@pytest.mark.parametrize("name", BUILDABLE)
def test_no_unowned_sampling_parameter_reaches_the_wire(name):
    """The arena chooses `temperature` and nothing else about sampling.

    Every other knob - `top_p`, `seed`, `max_tokens`, the penalties, `n`,
    `logprobs`, `response_format` - is left at the provider default so it is the
    same for everyone. Measured today: no adapter sets any of them, and
    `smolagents` alone adds `stop` (declared above, because its ReAct loop needs
    it). A future adapter that quietly injects `top_p=0.9` would be comparing a
    different sampling distribution; this fails until that key is removed or
    added to SAMPLING_EXCEPTIONS with a reason.
    """
    allowed = SAMPLING_ENVELOPE | SAMPLING_EXCEPTIONS.get(name, set())
    with MockServer(SCRIPT, arena_tools=list(ARENA.tools)) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=3,
        )
        load_framework(name).build(ARENA, config).run(ITEM)
        unowned = {key for request in server.requests for key in request} - allowed

    assert not unowned, (
        f"{name} put {sorted(unowned)} on the wire — a sampling parameter the "
        f"arena never chose and nothing holds constant across frameworks. Remove "
        f"it, or record it in SAMPLING_EXCEPTIONS with why the mechanism needs it"
    )
