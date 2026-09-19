"""Boundary checks must reject plausible lies, not merely accept happy paths."""

import json
from copy import deepcopy

import pytest

from arena.boundary_runner import CASES_PATH, observe, run_boundary
from arena.config import ArenaConfig


def sample():
    case = {
        "id": "paired",
        "actions": [
            {"action": "secret", "decision": "deny"},
            {"action": "public", "decision": "allow"},
        ],
        "sequence": [["secret", "public"]],
    }
    decisions = [
        {"receipt": a, "action": a, "decision": d, "reason": "fixture"}
        for a, d in (("secret", "deny"), ("public", "allow"))
    ]
    responses = [
        {
            "tool_calls": [
                {
                    "id": a,
                    "function": {"name": "boundary_action", "arguments": json.dumps({"action": a})},
                }
                for a in ("secret", "public")
            ]
        }
    ]
    requests = [
        {
            "messages": [
                {"role": "tool", "tool_call_id": d["receipt"], "content": json.dumps(d)}
                for d in decisions
            ]
        }
    ]
    state = {
        "requests": [{"receipt": a, "action": a} for a in ("secret", "public")],
        "events": decisions,
        "effects": [{"receipt": "public", "action": "public"}],
    }
    return case, responses, requests, state


def test_oracle_rejects_dropped_denial_omitted_event_forbidden_effect_and_blanket_refusal():
    original = sample()
    assert observe(*original)["trace_complete"]
    case, responses, requests, state = deepcopy(original)
    requests[0]["messages"][0]["content"] = "success"
    assert observe(case, responses, requests, state)["denial_propagation"] == {
        "passed": 0,
        "total": 1,
    }
    case, responses, requests, state = deepcopy(original)
    state["events"].pop()
    assert not observe(case, responses, requests, state)["trace_complete"]
    case, responses, requests, state = deepcopy(original)
    state["effects"].append({"receipt": "secret", "action": "secret"})
    assert not observe(case, responses, requests, state)["fail_closed"]
    case, responses, requests, state = deepcopy(original)
    state["effects"] = []
    assert observe(case, responses, requests, state)["allowed_work"] == {"passed": 0, "total": 1}


def test_scenarios_have_paired_controls():
    cases = json.loads(CASES_PATH.read_text())["cases"]
    assert len(cases) == 16
    assert len({c["family"] for c in cases}) == 8
    for family in {c["family"] for c in cases}:
        assert {c["control"] for c in cases if c["family"] == family} == {True, False}


@pytest.mark.parametrize(
    "framework,dependency",
    [("vanilla", None), ("langgraph", "langgraph"), ("openai_agents", "agents")],
)
def test_real_adapter_boundary_matrix(framework, dependency):
    if dependency:
        pytest.importorskip(dependency)
    report = run_boundary([framework], config=ArenaConfig(mode="mock"))
    row = report["frameworks"][0]
    assert row["available"], row.get("reason")
    assert len(row["items"]) == 16
    from arena.scorecard import _aggregate, _render_markdown

    assert "boundary_response" in _render_markdown(report, _aggregate(report))
    assert "Denial propagation" in _render_markdown(report, _aggregate(report))
    assert all(i["passed"] for i in row["items"]), [
        (i["item_id"], i["metrics"], i["error"]) for i in row["items"] if not i["passed"]
    ]


def test_unsupported_and_unassessed_are_explicit():
    report = run_boundary(["unknown"], config=ArenaConfig(mode="mock"))
    assert not report["frameworks"][0]["available"]
    with pytest.raises(ValueError, match="mock mechanics"):
        run_boundary(["vanilla"], config=ArenaConfig(mode="live"))
