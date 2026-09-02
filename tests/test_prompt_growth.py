"""What happens to framework overhead when the conversation gets long?

`docs/overhead.md` measures a two-call task and then asserted, untested, that a
fixed per-request cost "matters much less on a 20-turn conversation". Scripting
the same tool loop out to 30 turns says exactly how much less, and turns up one
thing nobody had checked at all.

Estimated prompt tokens per request, same scripted conversation for everyone:

    request #        1      11      31
    vanilla        121    1531    4350
    smolagents    1069    2551    5515
    ratio         8.83x   1.67x   1.27x

**Nobody truncates.** Every framework here resends the entire history on every
request, all the way out to 31 requests. None of them ships context management,
summarisation or a sliding window by default. The only thing bounding the prompt
is `max_tool_iterations`, which is the harness's knob rather than the library's.

**The marginal cost of a turn is the same everywhere** - 136.7 to 148.2 estimated
tokens across seven frameworks, a 8% band, against an 8.8x spread on the first
request. Frameworks differ by a *constant*, not by a rate.

Those two facts together are why the overhead multiple decays: the constant is
paid once per request, so it grows linearly in turns, while the conversation it
is being compared against grows quadratically. On a long loop the framework you
picked stops mattering and the number of turns takes over.

What is gated here is the shape, not the constants. The constants are findings
and live in docs/overhead.md, the same rule as `resilience` and `transport`. The
shape is the instrument: if some framework started dropping history, every
comparison in that document would be between different conversations, and the
right outcome is a failure rather than a quietly wrong table.

Reproduce the full curve with

    python .github/scripts/report_growth.py 30
"""

import json
from dataclasses import replace

import pytest

from arena.config import ArenaConfig
from arena.llm.mockserver import MockScript, MockServer
from arena.registry import available_frameworks, load_framework
from arena.types import ArenaSpec, EvalItem

STUBS = {"claude_agent_sdk"}
ANSWER = "The Eiffel Tower is 330 metres tall."
QUERIES = ["eiffel tower", "great wall", "amazon river", "mount everest", "sahara"]
ITEM = EvalItem(id="g-01", input="How tall is the Eiffel Tower?", checks=[])

# Long enough for the trend to be unambiguous, short enough to stay cheap: the
# 30-turn curve is in report_growth.py, and it is the same straight line.
TURNS = 8


def _arena():
    return ArenaSpec(
        id="growth",
        description="prompt growth over a long tool loop",
        tools=["search"],
        system_prompt_intent="\nAnswer the question concisely.\n",
        dataset=[],
        mock_script_path="",
    )


def _script(turns):
    steps = [
        {"tool_calls": [{"name": "search", "arguments": {"query": QUERIES[i % len(QUERIES)]}}]}
        for i in range(turns)
    ]
    return MockScript({"default": {"turns": [*steps, {"content": ANSWER}]}})


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
_CACHE: dict[str, list[int]] = {}


def _curve(name):
    """Estimated prompt tokens for each request, cached: one run per framework."""
    if name in _CACHE:
        return _CACHE[name]
    with MockServer(_script(TURNS), arena_tools=["search"]) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=TURNS + 4,
        )
        load_framework(name).build(_arena(), config).run(ITEM)
        out = []
        for req in server.requests:
            chars = len(json.dumps(req.get("messages", [])))
            chars += len(json.dumps(req.get("tools", []))) if req.get("tools") else 0
            out.append(chars // 4)
    _CACHE[name] = out
    return out


@pytest.mark.parametrize("name", BUILDABLE)
def test_the_whole_history_is_resent_every_turn(name):
    """No framework here truncates, summarises or windows the conversation.

    A gate rather than a finding, on the instrument rather than the framework:
    docs/overhead.md compares token counts across frameworks *on the assumption
    that they are sending the same conversation*. One that started dropping
    messages would look cheap for a reason that has nothing to do with
    serialisation, and the whole table would silently mean something else.

    It is also worth knowing on its own. Whatever bounds your prompt in a long
    tool loop, it is not the library.
    """
    curve = _curve(name)
    assert len(curve) >= TURNS, f"{name}: only {len(curve)} requests for {TURNS} scripted turns"
    shrank = [(i, a, b) for i, (a, b) in enumerate(zip(curve, curve[1:], strict=False)) if b <= a]
    assert not shrank, (
        f"{name}: prompt did not grow at request(s) {[i + 2 for i, _, _ in shrank]} — "
        f"history is being dropped, and docs/overhead.md is no longer comparing "
        f"like with like. Curve: {curve}"
    )


@pytest.mark.parametrize("name", BUILDABLE)
def test_frameworks_differ_by_a_constant_not_by_a_rate(name):
    """Adding a turn costs everyone the same. Only the starting point differs.

    Measured across seven frameworks the marginal cost of a turn spans 136.7 to
    148.2 estimated tokens - an 8% band, against an 8.8x spread on the first
    request. That is what makes the overhead multiple in docs/overhead.md a
    *decaying* one rather than a fixed tax.

    Gated because it is a property of the comparison being fair: the mock replays
    byte-identical turns, so if one framework's per-turn growth drifted away from
    the others it would mean the conversation is no longer identical - extra
    scaffolding injected per turn, a reformatted tool result, a duplicated
    message. The tolerance is deliberately loose (35%) so that ordinary
    serialisation differences pass and a structural one does not.
    """
    reference = _curve("vanilla") if "vanilla" in BUILDABLE else None
    if reference is None:
        pytest.skip("no stdlib baseline installed in this venv")
    curve = _curve(name)
    n = min(len(curve), len(reference))
    if n < 4:
        pytest.skip("too few requests to fit a rate")
    # Slope over the middle of the curve, avoiding the first request (where the
    # constant lives) and the last (whose turn carries the final answer).
    mine = (curve[n - 2] - curve[1]) / (n - 3)
    theirs = (reference[n - 2] - reference[1]) / (n - 3)
    assert abs(mine - theirs) / theirs < 0.35, (
        f"{name} grows {mine:.1f} tokens/turn against the baseline's {theirs:.1f} — "
        f"the scripted conversation is no longer identical on the wire. Check both: "
        f"a drifting baseline fails this for every other framework at once"
    )


def test_the_overhead_multiple_decays_as_the_conversation_grows():
    """The claim docs/overhead.md used to make without measuring anything.

    smolagents costs 8.83x the baseline on the first request of this loop, 1.67x
    by the eleventh and 1.27x by the thirty-first. That is not a property of
    smolagents; it follows from the two gates above. A constant paid once per
    request is linear in turns, and the conversation it is divided by is
    quadratic, so any fixed overhead decays as 1/n.

    Asserted against the framework with the largest constant that happens to be
    installed, so it means something in every venv rather than only where
    smolagents is present.
    """
    if "vanilla" not in BUILDABLE or len(BUILDABLE) < 2:
        pytest.skip("needs the baseline and at least one framework")
    base = _curve("vanilla")
    others = {n: _curve(n) for n in BUILDABLE if n != "vanilla"}
    name, curve = max(others.items(), key=lambda kv: kv[1][0] / base[0])
    n = min(len(curve), len(base)) - 1
    first, last = curve[0] / base[0], curve[n] / base[n]
    if first < 1.05:
        pytest.skip(f"{name} has no measurable constant to amortise ({first:.2f}x)")
    assert last < first, (
        f"{name}'s overhead multiple went from {first:.2f}x to {last:.2f}x over "
        f"{n + 1} requests — a per-request constant should be shrinking, not growing"
    )
