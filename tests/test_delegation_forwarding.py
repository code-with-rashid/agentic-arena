"""Who pays to forward context down a delegation chain, and who forwards for free.

Every pipeline number this repo publishes was measured with the delegate told
**only the original task** — the cheapest thing a manager could possibly forward.
`docs/multi-agent.md` says so and calls 4.03x a floor, and "whether forwarding
context between roles changes the ranking" has sat in the *not measured* list
since. It is the obvious objection to the whole comparison: the design favours
the mechanisms that carry the transcript for free, so the ranking might be an
artifact of the harness rather than a fact about delegation.

It is not. Measured, with the **same payload for every framework** so that who
pays is the mechanism and not whatever transcript a particular library happens to
keep:

    forwarded chars                 0    277    553   1105
    ------------------------------------------------------
    vanilla_multi     structural    0      0      0      0
    langgraph_multi   structural    0      0      0      0
    openai_agents_multi  swap       0      0      0      0
    smolagents_multi  as tool       0    509    978   1916
    pydantic_ai_multi as tool       0    508    977   1915

**Three of the four mechanisms forward for free; one pays.** A structural
pipeline shares one transcript by construction. A speaker swap hands the *same*
conversation on, and its `transfer_to_<agent>` tool takes no arguments at all —
there is nowhere to put a payload and nothing that needs one. Only a sub-agent
invoked as a tool starts a **fresh** conversation, so it has to be told, and it
pays.

**The two sub-agent implementations agree to within one token at every size** —
509/978/1916 against 508/977/1915, in libraries that share no code. Same
signature as the 2N call law in `test_delegation_depth.py`, now in a second
dimension.

**And it costs about 1.77 tokens per forwarded character, not 0.25.** The payload
is not paid once per hop: it becomes the sub-agent's opening user message and is
then re-sent on every request of that sub-agent's conversation. Forwarding is
priced like a system prompt, not like a message.

So the answer to the open question is that forwarding **does not change the
ranking — it widens the gap it was suspected of creating.** The published numbers
were a floor, and this is how far above it a realistic pipeline sits.

What this deliberately does not say: whether forwarding *helps*. The mock replays
a script either way, so the benefit is held at zero by construction, exactly as it
is everywhere else on `docs/multi-agent.md`. Only a live run can price the other
side of that trade.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from arena.config import ArenaConfig
from arena.llm.mockserver import MockScript, MockServer
from arena.registry import available_frameworks, load_arena, load_framework

ARENA = load_arena("multi_agent")
SCRIPT = MockScript.load(ARENA.mock_script_path)
ITEM = ARENA.dataset[0]

# One sentence of plausible research, repeated. Held byte-identical across every
# framework: the question is what a *mechanism* charges to forward N bytes, and a
# payload derived from each framework's own transcript would answer a different
# question for each of them.
UNIT = "the Eiffel Tower was completed in 1889 and stands 330 metres tall. "
SIZES = [0, 4, 8, 16]

# Mechanism per pipeline entry. `vanilla_multi` and `langgraph_multi` never reach
# the mock's delegation path at all - their wiring always visits every stage - so
# they are here as the control rather than as a fourth mechanism.
FREE = ["vanilla_multi", "langgraph_multi", "openai_agents_multi"]
PAYS = ["smolagents_multi", "pydantic_ai_multi"]
PIPELINES = FREE + PAYS

# Measuring is slow enough (six requests through a real library per point) that
# re-running per assertion would dominate the comparison job. Every measurement
# is deterministic, so caching is safe.
_CACHE: dict[tuple[str, int], int] = {}


def _payload(units: int) -> str:
    return f"Findings so far: {UNIT * units}" if units else ""


def _prompt_tokens(name: str, units: int) -> int:
    key = (name, units)
    if key not in _CACHE:
        with MockServer(
            SCRIPT, arena_tools=list(ARENA.tools), forward_context=_payload(units)
        ) as server:
            config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
            load_framework(name).build(ARENA, config).run(ITEM)
            _CACHE[key] = server.served_usage["prompt_tokens"]
    return _CACHE[key]


def _installed(name: str) -> bool:
    if name not in available_frameworks():
        return False
    try:
        load_framework(name).build(ARENA, ArenaConfig(mode="mock"))
    except Exception:  # noqa: BLE001 - not installed in this venv
        return False
    return True


def _deltas(name: str) -> list[int]:
    """Extra prompt tokens against forwarding nothing, one per payload size."""
    base = _prompt_tokens(name, 0)
    return [_prompt_tokens(name, units) - base for units in SIZES]


@pytest.mark.parametrize("name", FREE)
def test_carrying_the_conversation_makes_forwarding_free(name):
    """A shared transcript costs nothing to forward, at any payload size.

    Two reasons, both worth keeping apart. `vanilla_multi` and `langgraph_multi`
    are structural: every stage runs regardless and they never take the mock's
    delegation path. `openai_agents_multi` does take it, and still pays nothing,
    because a `transfer_to_<agent>` tool declares no parameters - there is
    physically nowhere to put a payload, which is the mechanism's whole point.
    """
    if not _installed(name):
        pytest.skip(f"{name} is not installed in this environment")
    assert _deltas(name) == [0] * len(SIZES), (
        f"{name} started paying to forward context: {_deltas(name)}"
    )


@pytest.mark.parametrize("name", PAYS)
def test_a_fresh_conversation_has_to_be_told_and_pays_for_it(name):
    """A sub-agent invoked as a tool pays, and pays linearly in the payload.

    Gated as a shape rather than as constants: the cost rises with every payload
    size and each doubling roughly doubles it. The byte counts are findings and
    live in docs/multi-agent.md.
    """
    if not _installed(name):
        pytest.skip(f"{name} is not installed in this environment")
    deltas = _deltas(name)
    assert deltas[0] == 0, deltas
    assert all(later > earlier for earlier, later in zip(deltas, deltas[1:], strict=False)), (
        f"{name} does not pay more for a larger payload: {deltas}"
    )
    # Linear in the payload, measured as cost per forwarded character rather than
    # by doubling: the payload carries a fixed prefix, so 16 units is 1.97x the
    # bytes of 8, not 2x, and asserting on a doubling would be asserting on the
    # fixture instead of on the mechanism.
    rates = [
        delta / len(_payload(units)) for delta, units in zip(deltas, SIZES, strict=True) if units
    ]
    assert max(rates) - min(rates) < 0.1, (
        f"{name} does not charge a constant rate per forwarded character: {rates}"
    )


def test_the_cost_is_the_mechanism_not_the_library():
    """The two sub-agent-as-tool implementations agree at every payload size.

    smolagents and Pydantic AI share no code and express the shape completely
    differently - a `managed_agents` list against an ordinary async tool that
    awaits a nested run. If their forwarding costs ever diverged, the claim that
    this is a property of the mechanism would be wrong, and it is the claim the
    advice in docs/multi-agent.md rests on.

    Compared as deltas rather than as totals on purpose: smolagents' absolute
    prompt is four times Pydantic AI's because of its own templated system
    prompt, which is a different finding and would swamp this one.
    """
    present = [name for name in PAYS if _installed(name)]
    if len(present) < 2:
        pytest.skip("needs both sub-agent-as-tool pipelines installed")
    first, second = (_deltas(name) for name in present[:2])
    assert all(abs(a - b) <= 2 for a, b in zip(first, second, strict=True)), (
        f"{present[0]} and {present[1]} no longer agree on what forwarding costs: "
        f"{first} vs {second}"
    )


def test_forwarding_is_priced_like_a_system_prompt_not_like_a_message():
    """The payload costs far more than one copy of itself, and that is the point.

    A reader who assumed forwarding costs `len(payload)` once per hop would be
    out by about sevenfold. The forwarded text becomes the sub-agent's opening
    user message and is then re-sent on every request of that sub-agent's
    conversation, so it is billed the way a system prompt is.

    Asserted as "several times one copy" rather than at a constant, because the
    multiple depends on how many requests each conversation takes and that is a
    per-mechanism number rather than a law.
    """
    present = [name for name in PAYS if _installed(name)]
    if not present:
        pytest.skip("needs a sub-agent-as-tool pipeline installed")
    name = present[0]
    units = SIZES[-1]
    one_copy = len(_payload(units)) / 4  # the mock's chars/4 estimate
    paid = _deltas(name)[-1]
    assert paid > 2 * one_copy, (
        f"{name} paid {paid} tokens for a {one_copy:.0f}-token payload — if this is "
        f"now close to a single copy, the payload has stopped riding on every request "
        f"and docs/multi-agent.md overstates the cost"
    )


def test_forwarding_changes_the_cost_and_never_the_answer():
    """The instrument checking itself: the benefit is held at zero by construction.

    Every claim on this page is about what forwarding *costs*. That is only
    honest if forwarding cannot quietly change what the pipeline produces - the
    mock replays the same script either way, and if it ever stopped doing so, a
    cost comparison would silently become a quality comparison between different
    conversations.
    """
    present = [name for name in PIPELINES if _installed(name)]
    if not present:
        pytest.skip("no pipeline entry installed")
    name = present[0]
    outputs = []
    for units in (0, SIZES[-1]):
        with MockServer(
            SCRIPT, arena_tools=list(ARENA.tools), forward_context=_payload(units)
        ) as server:
            config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
            outputs.append(load_framework(name).build(ARENA, config).run(ITEM).output_text)
    assert outputs[0] == outputs[1] != "", (
        f"{name} answered differently with context forwarded: {outputs}"
    )


def test_the_payload_actually_reaches_the_delegate():
    """Without this, every zero above could mean the knob simply does nothing.

    Checked on the wire rather than inferred from the totals: the forwarded text
    must appear in a request that the *sub-agent* makes, which is the only place
    it could have been carried to.
    """
    present = [name for name in PAYS if _installed(name)]
    if not present:
        pytest.skip("needs a sub-agent-as-tool pipeline installed")
    marker = _payload(SIZES[-1])
    with MockServer(SCRIPT, arena_tools=list(ARENA.tools), forward_context=marker) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        load_framework(present[0]).build(ARENA, config).run(ITEM)
        bodies = [
            str(message.get("content") or "")
            for request in server.requests
            for message in request.get("messages", [])
        ]
    assert any(UNIT in body for body in bodies), (
        "the forwarded payload never reached the wire - forward_context is inert and "
        "every zero measured above is meaningless"
    )
