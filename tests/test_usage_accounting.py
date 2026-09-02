"""Every adapter must report the cost it actually incurred.

This is the assumption the whole benchmark rests on and nothing was checking it.
An adapter's `AgentResult` numbers are a *claim*; the mock server knows what it
actually served. If a framework under-reports, it posts better overhead, cost and
LLM-call numbers than it earned — and every correctness check still passes, so
the scorecard stays green while the comparison silently lies.

It is not a hypothetical failure. Three real bugs of exactly this shape have been
found in this repo:

  * `openai_agents` reports usage *cumulatively* after a resume, so leg two came
    back carrying leg one's numbers - summing them doubled the cost of every
    paused item.
  * `smolagents` resets its usage monitor inside `run()`, so a before/after
    subtraction silently produced garbage.
  * `langgraph` sliced counted messages by index. That is right for
    `human_in_the_loop` (a resumed `invoke` returns the whole thread) and wrong
    for `durable_state` (it returns only the new messages), where it discarded
    all of leg two - a whole LLM call per item, unreported.

The resumed path is where these live, so it is tested separately: single-turn
accounting is easy and leg-summed accounting is not.
"""

import json
from dataclasses import replace

import pytest

from arena.config import ArenaConfig
from arena.llm.mockserver import MockScript, MockServer
from arena.registry import available_frameworks, load_arena, load_framework

STUBS = {"claude_agent_sdk"}


def _buildable():
    out = []
    for name in available_frameworks():
        if name in STUBS:
            continue
        try:
            arena = load_arena("tool_use")
            config = replace(ArenaConfig(mode="mock"), base_url="http://127.0.0.1:1", api_key="k")
            load_framework(name).build(arena, config)
        except Exception:  # noqa: BLE001 - not installed in this venv
            continue
        out.append(name)
    return out


BUILDABLE = _buildable()


def _reported(result):
    return (result.prompt_tokens, result.completion_tokens, result.llm_calls)


def _served(server):
    usage = server.served_usage
    return (usage["prompt_tokens"], usage["completion_tokens"], usage["llm_calls"])


@pytest.mark.parametrize("name", BUILDABLE)
def test_adapter_reports_the_cost_it_actually_incurred(name):
    arena = load_arena("tool_use")
    with MockServer(MockScript.load(arena.mock_script_path)) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        result = load_framework(name).build(arena, config).run(arena.dataset[0])
        served = _served(server)

    assert _reported(result) == served, (
        f"{name}: reported (prompt, completion, llm_calls) {_reported(result)} "
        f"but the wire carried {served}"
    )


def _resumable(name, arena):
    """Adapters that implement the resume contract for this arena."""
    config = replace(ArenaConfig(mode="mock"), base_url="http://127.0.0.1:1", api_key="k")
    try:
        return hasattr(load_framework(name).build(arena, config), "resume")
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.parametrize("arena_id", ["human_in_the_loop", "durable_state"])
@pytest.mark.parametrize("name", BUILDABLE)
def test_cost_summed_across_legs_matches_the_wire(name, arena_id, tmp_path):
    """The paused path, where an off-by-one leg is invisible to every other check.

    The harness sums cost across legs, so each leg must report only its own work:
    counting from zero twice doubles a paused item, and slicing too aggressively
    drops a leg entirely. Both look fine on the scorecard.
    """
    arena = load_arena(arena_id)
    if not _resumable(name, arena):
        pytest.skip(f"{name} does not implement resume")

    item = arena.dataset[0]
    adapter = load_framework(name)
    with MockServer(MockScript.load(arena.mock_script_path)) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        if arena.durable:
            # The harness owns a checkpoint dir and hands the same path to the
            # rebuilt runner (arena.runner.run). Without it an adapter whose store
            # is on disk falls back to a private temp dir per build and cannot
            # find its own session - a fault of this probe, not of the adapter.
            config = replace(config, checkpoint_dir=str(tmp_path))
        runner = adapter.build(arena, config)
        first = runner.run(item)
        if not first.suspended:
            pytest.skip(f"{name} did not suspend on {arena_id}")

        state = first.resume_state
        if arena.durable:
            # Exactly what the harness does: cross a real JSON gap and throw the
            # runner away, so only what is in `resume_state` survives.
            state = json.loads(json.dumps(state))
            runner = adapter.build(arena, config)
        second = runner.resume(item, state, item.resume_with or "approve")
        served = _served(server)

    summed = tuple(a + b for a, b in zip(_reported(first), _reported(second), strict=True))
    assert summed == served, (
        f"{name} on {arena_id}: legs summed to {summed} but the wire carried {served} "
        f"(leg1 {_reported(first)}, leg2 {_reported(second)})"
    )
