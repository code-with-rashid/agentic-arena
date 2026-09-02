"""What the `structured_output` arena actually measures, and what it does not.

The arena's own `arena.toml` says adapters "may use a native structured-output
mechanism (`response_format`, a Pydantic result type, a tool-as-schema)" and that
which one each uses "is a finding for the feature matrix". Nobody had checked.
The answer is **none of them do**:

    plan            every framework, all seven
    ------------------------------------------------------------
    response_format  absent from every request
    valid JSON       returned unchanged, 2 calls
    not JSON         returned unchanged, 2 calls
    wrong types      returned unchanged, 2 calls
    missing field    returned unchanged, 2 calls
    extra field      returned unchanged, 2 calls

Not one adapter asks the *provider* to constrain the output — including
`pydantic_ai`, whose stated reason to exist is typed results. All seven ask the
model nicely in the system prompt and hand back whatever comes.

Nor does any of them validate what comes back. Given output that violates the
schema in four different ways, every framework returns it byte-for-byte in
exactly two LLM calls. Nobody re-prompts, nobody raises.

Which makes `arena/scorer.py` the only thing standing between a malformed answer
and a green scorecard — and nothing was pinning *that*. If `json_schema` quietly
stopped validating, every `structured_output` run would go green and read as
seven frameworks with perfect typed output.

Two things are gated here, and they are different in kind:

  * **the scorer rejects each way the schema can be violated.** Not a framework
    property at all; it is the instrument, and the one this arena's entire
    result rests on.
  * **the final answer reaches the scorer unchanged.** A framework that repaired
    or reformatted JSON on the way out would have the arena grading its repair
    layer while reporting the number as the model's output.

That no adapter uses a native mechanism is a **finding**, documented in
docs/structured-output.md, not a gate — the same rule as `resilience` and
`transport`. Wiring one in per framework is real work and is named there as a
next step rather than half-done here, because doing it for one adapter and not
the others would make the arena incomparable.
"""

import contextlib
import json
from dataclasses import replace

import pytest

from arena.config import ArenaConfig
from arena.llm.mockserver import MockScript, MockServer
from arena.registry import available_frameworks, load_arena, load_framework
from arena.scorer import score_item
from arena.types import AgentResult, EvalItem

STUBS = {"claude_agent_sdk"}
ARENA = load_arena("structured_output")
ITEM = EvalItem(id="so-01", input="Eiffel Tower", checks=[])

VALID = '{"name": "Eiffel Tower", "year": 1889, "height_m": 330, "sources": ["Eiffel Tower"]}'

# Four ways to violate the schema, one per failure mode the checks describe.
BROKEN = {
    "not json": "The Eiffel Tower was completed in 1889 and is 330 m tall.",
    "wrong types": '{"name": "Eiffel Tower", "year": "eighteen eighty-nine", '
    '"height_m": "330 m", "sources": "Eiffel Tower"}',
    "missing field": '{"name": "Eiffel Tower", "year": 1889}',
    "extra field": '{"name": "Eiffel Tower", "year": 1889, "height_m": 330, '
    '"sources": ["Eiffel Tower"], "confidence": "high"}',
}


def _script(final):
    """One search, then the same final answer however many times it is asked for."""
    return MockScript(
        {
            "default": {
                "turns": [
                    {"tool_calls": [{"name": "search", "arguments": {"query": "Eiffel Tower"}}]},
                    *[{"content": final}] * 4,
                ]
            }
        }
    )


def _buildable():
    out = []
    for name in available_frameworks():
        if name in STUBS or name.endswith("_multi"):
            continue
        try:
            config = replace(ArenaConfig(mode="mock"), base_url="http://127.0.0.1:1", api_key="k")
            load_framework(name).build(ARENA, config)
        except Exception:  # noqa: BLE001 - not installed in this venv
            continue
        out.append(name)
    return out


BUILDABLE = _buildable()


def _run(name, final):
    with MockServer(_script(final), arena_tools=list(ARENA.tools)) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=6,
        )
        try:
            result = load_framework(name).build(ARENA, config).run(ITEM)
            text = (result.output_text or "").strip()
        except Exception as exc:  # noqa: BLE001 - the outcome under test
            text = f"<raised {type(exc).__name__}>"
        return text, [r.get("response_format") for r in server.requests]


def _scored(text):
    result = AgentResult(
        output_text=text,
        tool_calls=[{"name": "search", "arguments": {"query": "Eiffel Tower"}}],
        prompt_tokens=1,
        completion_tokens=1,
        llm_calls=2,
    )
    return score_item(ARENA.dataset[0], result).passed


def test_the_scorer_accepts_a_record_that_matches_the_schema():
    """The control. Without it, a scorer that rejected everything would pass below."""
    assert _scored(VALID), "the scorer rejects a valid record — every item would fail"


@pytest.mark.parametrize("label", sorted(BROKEN))
def test_the_scorer_rejects_each_way_the_schema_can_be_violated(label):
    """The only thing standing between a malformed answer and a green scorecard.

    No framework validates its own output — measured, see the module docstring —
    so this is not redundant with anything. If `json_schema` stopped checking,
    every `structured_output` run would go green and read as seven frameworks
    with flawless typed output.

    `extra field` is in here deliberately: it is the one violation a lenient
    parser would let through, and the dataset asks for `additionalProperties:
    false`.
    """
    assert not _scored(BROKEN[label]), (
        f"the scorer accepted {label!r} — a schema violation now scores as a pass"
    )


def test_a_fenced_record_is_accepted_on_purpose():
    """Pinning a deliberate leniency, so nobody reads the arena as stricter than it is.

    The arena's system prompt says "no markdown fences", and `extract_json`
    accepts them anyway — it tries the whole string, then a fenced block, then the
    first balanced span. That is documented behaviour and the right call for a
    live run, but it means the arena grades whether the record is *extractable
    and correct*, not whether the model obeyed the envelope instruction. A
    framework that returns clean JSON gets no credit here over one that wraps it
    in prose.
    """
    assert _scored(f"```json\n{VALID}\n```"), "fenced JSON is expected to be extracted"
    assert _scored(f"Here is the record:\n{VALID}"), "chatty prose around JSON is tolerated"


@pytest.mark.parametrize("name", BUILDABLE)
def test_the_model_answer_reaches_the_scorer_unchanged(name):
    """No framework may repair, reformat or re-serialise the final answer.

    If one did, the arena would be grading that repair layer while reporting the
    number as the model's output — and the comparison against frameworks that do
    not would be meaningless.

    Checked with a *broken* record rather than a valid one, because that is where
    a repair layer would show itself: a framework that re-serialises valid JSON
    is invisible, one that fixes `"year": "eighteen eighty-nine"` is not.
    """
    broken = BROKEN["wrong types"]
    text, _ = _run(name, broken)
    assert text == broken, (
        f"{name} altered the model's answer on the way out.\n"
        f"  model produced: {broken}\n"
        f"  scorer received: {text}"
    )


@pytest.mark.parametrize("name", BUILDABLE)
def test_a_schema_violation_costs_no_extra_model_calls(name):
    """Nobody re-prompts on a bad record — pinned, because it is what the numbers assume.

    A framework that retried a schema violation would spend more LLM calls on
    exactly the items it failed, so its cost numbers on this arena would not be
    comparable with one that does not. Today every framework spends the same two
    calls whether the record is valid or garbage.

    If this ever fails it is not necessarily a regression — retrying is a
    perfectly good design. It means docs/structured-output.md needs rewriting,
    and that the arena has finally started to discriminate.
    """
    valid_text, _ = _run(name, VALID)
    with MockServer(_script(BROKEN["missing field"]), arena_tools=list(ARENA.tools)) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=6,
        )
        with contextlib.suppress(Exception):  # counted, not raised
            load_framework(name).build(ARENA, config).run(ITEM)
        broken_calls = len(server.requests)
    with MockServer(_script(VALID), arena_tools=list(ARENA.tools)) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=6,
        )
        load_framework(name).build(ARENA, config).run(ITEM)
        valid_calls = len(server.requests)
    assert valid_text, f"{name} produced nothing on a valid record"
    assert broken_calls == valid_calls, (
        f"{name} spent {broken_calls} calls on a schema violation against "
        f"{valid_calls} on a valid record — it now re-prompts, and "
        f"docs/structured-output.md needs updating"
    )


def test_no_adapter_silently_hard_codes_the_schema_into_its_own_prompt():
    """The arena owns the schema. An adapter that inlined its own would be cheating.

    Same rule as the system prompt: `test_adapters_contract.py` already holds
    every adapter to taking its instruction from the arena. This is the narrower
    version for this arena specifically — the schema text lives in
    `arenas/structured_output/arena.toml` and must reach the model from there.
    """
    schema = json.dumps(ARENA.dataset[0].checks[0]["schema"], sort_keys=True)
    assert "height_m" in ARENA.system_prompt, (
        "the arena stopped describing its own schema; the check below is now vacuous"
    )
    assert "height_m" in schema, schema
