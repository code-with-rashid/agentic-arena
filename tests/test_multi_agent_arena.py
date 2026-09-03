"""The multi_agent arena must be well-formed and green for the stdlib baseline.

The arena tests how a framework expresses a researcher -> writer -> editor
pipeline. The eval is shape-based (a bounded-length brief carrying the right year
and measurement), so a single agent that role-plays the pipeline is a valid
entry and must pass; real multi-agent adapters are compared on cost, not on
whether they can clear the bar.
"""

import json
from dataclasses import replace

import pytest

from arena.config import REPO_ROOT, ArenaConfig
from arena.llm.mockserver import MockScript, MockServer
from arena.registry import frameworks_for_arena, load_arena, load_framework
from arena.runner import run

SCRIPT = json.loads(
    (REPO_ROOT / "arenas" / "multi_agent" / "mock_script.json").read_text(encoding="utf-8")
)


def _system(request):
    """The system prompt as text, whether the client sent a string or content parts."""
    out = ""
    for message in request.get("messages", []):
        if message.get("role") != "system":
            continue
        content = message.get("content", "")
        out += (
            content
            if isinstance(content, str)
            else "".join(p.get("text", "") for p in content if isinstance(p, dict))
        )
    return out


def test_every_scenario_researches_then_writes_a_brief():
    for scenario in SCRIPT["scenarios"]:
        turns = scenario["turns"]
        assert len(turns) == 2, f"{scenario['match']}: expected a search turn then the brief"
        assert turns[0].get("tool_calls"), "first turn must call search (the researcher)"
        assert turns[0]["tool_calls"][0]["name"] == "search"
        brief = turns[-1].get("content", "")
        assert brief and not turns[-1].get("tool_calls"), "last turn is the finished brief"
        # 3 to 5 sentences, matching the dataset's own bound.
        sentences = [s for s in brief.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        assert 3 <= len(sentences) <= 5, (
            f"{scenario['match']}: brief has {len(sentences)} sentences"
        )


def test_baseline_passes_every_item():
    arena = load_arena("multi_agent")
    record = run("multi_agent", ["vanilla"], config=ArenaConfig(mode="mock", repeat=1))
    fw = record["frameworks"][0]
    assert fw["available"], fw
    failed = [it["item_id"] for it in fw["items"] if not it["passed"]]
    assert not failed, f"baseline failed: {failed}"
    assert len(fw["items"]) == len(arena.dataset) == 10


def test_pipeline_entry_is_really_three_roles_and_costs_more():
    """The whole point of `vanilla_multi` is that it delegates. Prove it does.

    Nothing in the scorecard can tell a real pipeline from one agent called four
    times — the brief is scripted and identical either way. So the structure is
    asserted directly: three distinct role prompts, in order, and only the
    researcher holding tools. Without this the entry could silently degrade into
    an expensive single agent and still post 10/10.
    """
    arena = load_arena("multi_agent")
    script = MockScript.load(arena.mock_script_path)
    with MockServer(script) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        result = load_framework("vanilla_multi").build(arena, config).run(arena.dataset[0])
        requests = server.requests

    stages = []
    for req in requests:
        system = next(m["content"] for m in req["messages"] if m["role"] == "system")
        stages.append(next(r for r in ("researcher", "writer", "editor") if f"the {r}" in system))
    assert stages == ["researcher", "researcher", "writer", "editor"], stages

    # Only the researcher gets tools; the other two would be researchers if they did.
    tools_per_stage = [len(req.get("tools") or []) for req in requests]
    assert tools_per_stage == [1, 1, 0, 0], tools_per_stage

    # Every stage carries the arena's task prompt, not just a role line.
    for req in requests:
        system = next(m["content"] for m in req["messages"] if m["role"] == "system")
        assert arena.system_prompt in system

    # And it really is more expensive than the single-agent entry it contrasts with.
    with MockServer(script) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        single = load_framework("vanilla").build(arena, config).run(arena.dataset[0])
    assert result.llm_calls == 2 * single.llm_calls == 4
    assert result.prompt_tokens > single.prompt_tokens
    assert result.output_text == single.output_text, "same scripted answer, different cost"


def test_the_managed_agent_pipeline_pays_an_extra_call_per_delegation():
    """`smolagents_multi` is the third delegation shape, and it costs a third more.

    A sub-agent invoked as a tool returns a *tool result*, not the end of the
    run, so every delegator has to make one more model call to produce its own
    final answer after its sub-agent comes back. The other three pipeline entries
    spend 4 calls on three roles; this one spends 6, and the two extra are the
    mechanism rather than the work.

    Asserted rather than described because it is the finding, and because a
    pipeline that quietly collapsed into one agent would still post 10/10.
    """
    pytest.importorskip("smolagents")
    arena = load_arena("multi_agent")
    script = MockScript.load(arena.mock_script_path)
    with MockServer(script, arena_tools=arena.tools) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        result = load_framework("smolagents_multi").build(arena, config).run(arena.dataset[0])
        requests = server.requests

    stages = [
        next((r for r in ("researcher", "writer", "editor") if f"the {r}" in _system(req)), "?")
        for req in requests
    ]
    # Down the chain, then back up it: each delegator wakes again to answer.
    assert stages == ["researcher", "researcher", "writer", "editor", "writer", "researcher"], (
        stages
    )

    # Every stage carries the arena's task prompt, not just a role line.
    for req in requests:
        assert arena.system_prompt in _system(req)

    with MockServer(script, arena_tools=arena.tools) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        single = load_framework("smolagents").build(arena, config).run(arena.dataset[0])
    assert result.llm_calls == 3 * single.llm_calls == 6, (result.llm_calls, single.llm_calls)
    assert result.output_text == single.output_text, "same scripted answer, different cost"
    # Delegating is not a tool the arena granted, so it must not be logged as one.
    assert [c["name"] for c in result.tool_calls] == ["search"], result.tool_calls


def test_the_same_shape_costs_the_same_without_a_delegation_feature():
    """`pydantic_ai_multi` is the sub-agent-as-tool shape, hand-built.

    Pydantic AI has no `managed_agents` and no `AgentTool`: the delegate is an
    ordinary async tool whose body happens to `await sub_agent.run(...)`, and
    nothing in the library knows a sub-agent is involved. It costs the same six
    calls as `smolagents_multi` and puts the *same six stages* on the wire, in the
    same order.

    That is what makes the 2N law a property of the mechanism rather than of
    anyone's implementation of it, so it is asserted here rather than described.
    The scorecard cannot see it — a pipeline that quietly collapsed into a single
    agent would still post 10/10 — and the depth measurements in
    `tests/test_delegation_depth.py` use generic stages, so this is the only place
    the arena's own three roles are pinned for this entry.
    """
    pytest.importorskip("pydantic_ai")
    arena = load_arena("multi_agent")
    script = MockScript.load(arena.mock_script_path)
    with MockServer(script, arena_tools=arena.tools) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        result = load_framework("pydantic_ai_multi").build(arena, config).run(arena.dataset[0])
        requests = server.requests

    stages = [
        next((r for r in ("researcher", "writer", "editor") if f"the {r}" in _system(req)), "?")
        for req in requests
    ]
    # Byte-identical to the smolagents pipeline's: down the chain, then back up.
    assert stages == ["researcher", "researcher", "writer", "editor", "writer", "researcher"], (
        stages
    )

    # Every stage carries the arena's task prompt, not just a role line.
    for req in requests:
        assert arena.system_prompt in _system(req)

    with MockServer(script, arena_tools=arena.tools) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        single = load_framework("pydantic_ai").build(arena, config).run(arena.dataset[0])
    assert result.llm_calls == 3 * single.llm_calls == 6, (result.llm_calls, single.llm_calls)
    assert result.output_text == single.output_text, "same scripted answer, different cost"
    # Nested runs must be billed. Sharing one RunUsage is what does it; without
    # that this pipeline would report a single agent's cost while making six
    # calls, which is the shape tests/test_usage_accounting.py exists to catch.
    assert result.prompt_tokens > single.prompt_tokens
    # Delegating is not a tool the arena granted, so it must not be logged as one.
    assert [c["name"] for c in result.tool_calls] == ["search"], result.tool_calls


def test_variant_entries_are_scoped_to_their_arena():
    """`--framework all` must not drop a pipeline into a single-agent comparison.

    `vanilla_multi` on `tool_use` would sit in the middle of the per-framework
    overhead table at ~2.5x and read as a framework being wasteful, when it is a
    different structure being measured. Naming it explicitly still runs it.
    """
    assert "vanilla_multi" in frameworks_for_arena("multi_agent")
    assert "vanilla_multi" not in frameworks_for_arena("tool_use")
    assert "vanilla" in frameworks_for_arena("tool_use")
    # Unscoped adapters stay in every arena.
    for arena_id in ("tool_use", "multi_agent", "rag"):
        assert "vanilla" in frameworks_for_arena(arena_id)
