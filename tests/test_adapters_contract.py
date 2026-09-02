"""Every adapter must load, expose `name` + `lib_version`, and either build or raise
a clean NotImplementedError. This keeps stubs honest and catches import-time typos.
"""

import contextlib
import json
import os
from dataclasses import replace

import pytest

from arena.config import ArenaConfig
from arena.llm.mockserver import MockScript, MockServer
from arena.registry import available_frameworks, load_arena, load_framework
from arena.tools import CONTROL_TOOL_PREFIXES, CONTROL_TOOLS, TOOL_FUNCS, is_control_tool
from arena.types import ArenaSpec, EvalItem

STUBS = {"claude_agent_sdk"}

SENTINEL = "Reply only with the word ORNITHOPTER and nothing else."


def _sentinel_arena(tools):
    """An arena that shares nothing with tool_use, so a hard-coded prompt shows up."""
    return ArenaSpec(
        id="sentinel",
        description="sentinel",
        tools=list(tools),
        system_prompt_intent=f"\n{SENTINEL}\n",
        dataset=[],
        mock_script_path="",
    )


def _buildable_frameworks():
    """Adapters that are neither stubs nor missing their dependency."""
    out = []
    for name in available_frameworks():
        if name in STUBS:
            continue
        try:
            load_framework(name).build(_sentinel_arena(["search"]), ArenaConfig(mode="mock"))
        except Exception:  # noqa: BLE001 - dependency not installed in this env
            continue
        out.append(name)
    return out


BUILDABLE = _buildable_frameworks()


@pytest.mark.parametrize("name", available_frameworks())
def test_adapter_loads_and_declares_metadata(name):
    adapter = load_framework(name)
    assert adapter.name == name
    assert isinstance(adapter.lib_version, str) and adapter.lib_version


@pytest.mark.parametrize("name", sorted(STUBS))
def test_stub_adapters_raise_not_implemented(name):
    adapter = load_framework(name)
    arena = load_arena("tool_use")
    with pytest.raises(NotImplementedError):
        adapter.build(arena, ArenaConfig(mode="mock"))


def _wire_traffic(name, tools):
    """Run one item through an adapter and return what it actually sent."""
    arena = _sentinel_arena(tools)
    arena.dataset = [EvalItem(id="s-01", input="Say the word.", checks=[])]
    with MockServer(MockScript({"default": {"turns": [{"content": "ORNITHOPTER"}]}})) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        load_framework(name).build(arena, config).run(arena.dataset[0])
        assert server.requests, f"{name}: adapter sent no request"
        return server.requests[0]


@pytest.mark.parametrize("name", BUILDABLE)
def test_adapter_takes_its_system_prompt_from_the_arena(name):
    """No adapter may hard-code a task instruction.

    A hard-coded prompt means the adapter asks for the wrong thing whenever it is
    run on an arena other than the one its author had in mind — and mock mode
    hides it, because the script replays correct turns regardless of the prompt.
    Asserted against the actual request body, not an adapter attribute.
    """
    sent = json.dumps(_wire_traffic(name, ["search"]).get("messages", []))
    assert SENTINEL in sent, f"{name}: arena prompt never reached the model -> {sent[:400]}"


@pytest.mark.parametrize("name", BUILDABLE)
def test_adapter_advertises_only_the_tools_the_arena_declares(name):
    """Handing an agent an undeclared tool breaks 'same fight for everyone'."""
    body = _wire_traffic(name, ["search"])
    advertised = sorted(t.get("function", {}).get("name", "") for t in body.get("tools", []) or [])
    # A framework may add tools that only drive its own loop - smolagents ends a
    # run by calling `final_answer`, and a handoff chain advertises
    # `transfer_to_<agent>`. Those grant no arena capability, so exactly that set
    # is subtracted and nothing else.
    task_tools = [t for t in advertised if not is_control_tool(t)]
    assert task_tools == ["search"], (
        f"{name}: advertised {advertised}, but the arena declares only ['search'] "
        f"(exempt: {list(CONTROL_TOOLS)} and {list(CONTROL_TOOL_PREFIXES)}*)"
    )


@pytest.mark.parametrize("name", BUILDABLE)
def test_adapter_respects_the_shared_iteration_budget(name):
    """Every framework must stop after `max_tool_iterations` LLM calls.

    `max_tool_iterations` is one shared knob, but each framework spells its loop
    cap differently, and three of them originally mapped it to something that was
    not a loop cap at all — measured against a mock that never stops requesting
    tools, budgets of 6 produced 50 (pydantic_ai) and 41 (microsoft_af) LLM calls.
    An adapter allowed to grind eight times longer reports incomparable latency,
    token and cost numbers, which are exactly what the scorecard publishes.
    """
    budget = 4
    arena = _sentinel_arena(["calculator"])
    item = EvalItem(id="loop", input="loop forever", checks=[])
    never_stops = MockScript(
        {
            "default": {
                "turns": [{"tool_calls": [{"name": "calculator", "arguments": {"expr": "1+1"}}]}]
            }
        }
    )

    with MockServer(never_stops) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=budget,
        )
        runner = load_framework(name).build(arena, config)
        # Hitting the cap raises in some frameworks and returns in others; both
        # are acceptable, what matters is that the loop stopped.
        with contextlib.suppress(Exception):
            runner.run(item)
        calls = len(server.requests)

    assert calls <= budget, f"{name}: made {calls} LLM calls on a budget of {budget}"
    assert calls > 1, f"{name}: made {calls} calls — the probe never reached the tool loop"


def _tool_round_trip(name):
    """Run one search item and return (what the tool was asked, what came back)."""
    arena = _sentinel_arena(["search"])
    arena.dataset = [EvalItem(id="t-01", input="How tall is the Eiffel Tower?", checks=[])]
    script = MockScript(
        {
            "default": {
                "turns": [
                    {"tool_calls": [{"name": "search", "arguments": {"query": "Eiffel Tower"}}]},
                    {"content": "330 metres."},
                ]
            }
        }
    )
    with MockServer(script) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        load_framework(name).build(arena, config).run(arena.dataset[0])
        assert len(server.requests) >= 2, f"{name}: never sent the tool result back"
        return server.requests


def _decoded(text):
    """Undo a framework's own encoding of the tool result, but nothing else.

    Google ADK hands tool output back as `{"result": "<the text>"}`, so the
    payload arrives JSON-escaped - an apostrophe becomes `\'` and a raw
    containment check fails on a result that is in fact completely intact. That
    is an encoding difference, like smolagents' "Observation:" prefix, not a
    difference in what the model gets to see.

    Only the *values* of a JSON object are unwrapped, and only when the whole
    message parses. Truncation and summarisation still fail the check, because
    the decoded payload is compared against the tool output in full.
    """
    try:
        decoded = json.loads(text)
    except (ValueError, TypeError):
        return text
    if isinstance(decoded, dict):
        return "\n".join(str(v) for v in decoded.values())
    if isinstance(decoded, str):
        return decoded
    return text


def _tool_result_text(name, requests):
    """The tool output as the framework handed it back to the model.

    Deliberately not keyed on `role == "tool"`. smolagents feeds tool results
    back as `user` messages, which is a wire-format difference, not a difference
    in what the model gets to see. Asserting on the content rather than the
    envelope is the stronger check anyway: it is the text reaching the model that
    the arena depends on.
    """
    truth = TOOL_FUNCS["search"]({"query": "Eiffel Tower"})
    messages = requests[-1].get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") in ("system", "assistant"):
            continue
        # Content may be a plain string or a list of content parts; flatten
        # parts rather than json.dumps-ing them, or a real newline in the tool
        # output becomes an escaped backslash-n and nothing matches.
        content = msg.get("content", "")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        else:
            text = json.dumps(content)
        text = _decoded(text)
        if truth in text or "Eiffel Tower" in text:
            return text
    roles = [m.get("role") for m in messages]
    raise AssertionError(f"{name}: the tool result never reached the model -> roles {roles}")


@pytest.mark.parametrize("name", BUILDABLE)
def test_adapter_returns_the_tool_result_verbatim(name):
    """The model must see exactly what the tool returned.

    A framework that truncates, re-wraps or summarises tool output would still
    look green in mock mode — the script replays the next scripted turn no matter
    what came back — while scoring near zero live. Same blind spot that hid the
    hard-coded-prompt bug, so it gets the same wire-level treatment.
    """
    requests = _tool_round_trip(name)
    sent = _tool_result_text(name, requests)
    truth = TOOL_FUNCS["search"]({"query": "Eiffel Tower"})
    # Containment, not equality: a framework may wrap the output in its own
    # scaffolding ("Observations: ..."). Truncating or summarising it is the
    # failure this guards against, and containment still catches that.
    assert truth in sent, (
        f"{name}: tool result altered on the way to the model "
        f"({len(truth)} chars out, {len(sent)} chars in) -> {sent[:200]!r}"
    )


@pytest.mark.parametrize("name", BUILDABLE)
def test_adapter_executes_the_arguments_the_model_asked_for(name):
    """The query the model requested must be the query the tool actually ran."""
    requests = _tool_round_trip(name)
    sent = _tool_result_text(name, requests)
    # 'Eiffel Tower' is the top hit for that query and for nothing else in the corpus.
    assert "Eiffel Tower" in sent, (
        f"{name}: the tool ran on different arguments than the model requested -> {sent[:200]!r}"
    )


@pytest.mark.parametrize("name", BUILDABLE)
def test_adapter_replays_the_whole_transcript(name):
    """Each request must carry the prior turns, not just the newest message.

    The mock picks its scenario from the first user message and counts assistant
    turns to decide what to serve next, so an adapter that sent only the latest
    delta would desync and read as a mysterious wrong answer. STATUS.md carried
    this as an untested assumption; this is the test.
    """
    requests = _tool_round_trip(name)
    messages = requests[-1].get("messages", [])
    roles = [m.get("role") for m in messages]
    assert "user" in roles, f"{name}: dropped the original question -> {roles}"
    assert "assistant" in roles, f"{name}: dropped its own tool-call turn -> {roles}"
    # The tool result must be there; which role carries it is a framework detail.
    _tool_result_text(name, requests)


def test_at_least_one_adapter_was_actually_exercised():
    """Guard against the parametrised contract tests silently collapsing to zero."""
    assert "vanilla" in BUILDABLE, BUILDABLE


def test_every_expected_framework_is_contract_tested():
    """In an environment that has the frameworks installed, all of them must run.

    `pip install -e '.[dev]'` deliberately pulls no framework, so a plain CI test
    job can only ever contract-test `vanilla` — which meant the wire-level checks
    that caught the arena-spec and iteration-budget bugs were not actually
    guarding the frameworks they were written for. The job that does install them
    sets ARENA_EXPECT_FRAMEWORKS so a broken install fails loudly instead of
    quietly reducing the matrix to one adapter.
    """
    expected = [n for n in os.environ.get("ARENA_EXPECT_FRAMEWORKS", "").split(",") if n.strip()]
    if not expected:
        pytest.skip("ARENA_EXPECT_FRAMEWORKS not set (no frameworks installed here)")
    missing = sorted(set(expected) - set(BUILDABLE))
    assert not missing, f"expected to contract-test {expected}, but could not build {missing}"
