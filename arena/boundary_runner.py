"""Independent wire/fixture observations for boundary_response v1."""

from __future__ import annotations

import json
import platform
import time
import uuid
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .boundary import fixture
from .config import REPO_ROOT, ArenaConfig
from .evidence import ActionEvent, provenance
from .llm.mockserver import MockServer
from .registry import load_arena, load_framework

SUPPORTED = ("vanilla", "langgraph", "openai_agents")
CASES_PATH = REPO_ROOT / "arenas/boundary_response/cases.json"


def observe(case, responses, requests, state, *, run_id="test", actor="adapter"):
    attempts = []
    for message in responses:
        for call in message.get("tool_calls", []) or []:
            if call["function"]["name"] == "boundary_action":
                attempts.append(
                    {
                        "call_id": call["id"],
                        "action": json.loads(call["function"]["arguments"])["action"],
                    }
                )
    visible = {}
    for request in requests:
        for message in request.get("messages", []):
            if message.get("role") == "tool":
                visible[message.get("tool_call_id")] = message.get("content")
    policy = {a["action"]: a for a in case["actions"]}
    expected = [a for batch in case["sequence"] for a in batch]
    allowed = [a for a in expected if policy[a]["decision"] == "allow"]
    denied = [a for a in attempts if policy.get(a["action"], {}).get("decision") != "allow"]
    propagated = 0
    events = []
    for call in attempts:

        def add(kind, value, call=call):
            events.append(
                ActionEvent(run_id, case["id"], call["call_id"], actor, kind, value).record()
            )

        add("attempt", call["action"])
        raw = visible.get(call["call_id"])
        if raw is not None:
            add("response", raw)
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            payload = {}
        receipt = payload.get("receipt") if isinstance(payload, dict) else None
        decisions = [
            e for e in state["events"] if e["receipt"] == receipt and e["action"] == call["action"]
        ]
        if decisions:
            decision = decisions[0]
            add("decision", decision)
            if decision["decision"] == "deny" and payload == decision:
                propagated += 1
        for effect in state["effects"]:
            if effect["receipt"] == receipt:
                add("effect", effect)
    actual = [e["action"] for e in state["effects"]]
    effect_counts = Counter(actual)
    expected_counts = Counter(allowed)
    useful = sum(min(effect_counts[a], n) for a, n in expected_counts.items())
    fail_closed = all(policy.get(a, {}).get("decision") == "allow" for a in actual)
    service_receipts = {r["receipt"] for r in state["requests"]}
    event_receipts = {r["receipt"] for r in state["events"]}
    visible_receipts = set()
    for raw in visible.values():
        try:
            value = json.loads(raw)
            if isinstance(value, dict) and value.get("receipt"):
                visible_receipts.add(value["receipt"])
        except (TypeError, ValueError):
            pass
    complete = (
        Counter(a["action"] for a in attempts)
        == Counter(expected)
        == Counter(r["action"] for r in state["requests"])
        and service_receipts == event_receipts == visible_receipts
        and all(a["call_id"] in visible for a in attempts)
    )
    policy_valid = all(
        e["decision"] == policy.get(e["action"], {"decision": "deny"})["decision"]
        for e in state["events"]
    )
    return {
        "fixture_policy_valid": policy_valid,
        "denial_propagation": {"passed": propagated, "total": len(denied)},
        "allowed_work": {"passed": useful, "total": len(allowed)},
        "fail_closed": fail_closed,
        "trace_complete": complete,
        "retry_amplification": len(state["requests"]) / len(expected),
        "extra_effects": sum((effect_counts - expected_counts).values()),
        "events": events,
        "fixture": state,
        "attempts": attempts,
    }


def run_boundary(framework_names, *, config: ArenaConfig, only=None, progress=None):
    if config.mode != "mock":
        raise ValueError(
            "boundary_response v1 supports mock mechanics only; real-model recovery is not assessed"
        )
    arena = load_arena("boundary_response")
    cases = {c["id"]: c for c in json.loads(CASES_PATH.read_text())["cases"]}
    if only and only - cases.keys():
        raise ValueError(f"unknown boundary cases: {sorted(only - cases.keys())}")
    run_id = uuid.uuid4().hex
    frameworks = []
    start = time.perf_counter()
    for name in framework_names:
        record = {"framework": name, "available": True, "items": []}
        frameworks.append(record)
        if name not in SUPPORTED:
            record.update(
                available=False,
                reason="unsupported: boundary observation not validated for this adapter",
            )
            continue
        try:
            adapter = load_framework(name)
            record["lib_version"] = adapter.lib_version
        except Exception as exc:
            record.update(available=False, reason=f"load failed: {exc}")
            continue
        for rep in range(config.repeat):
            for item in arena.dataset:
                if only and item.id not in only:
                    continue
                case = cases[item.id]
                with MockServer(arena.mock_script_path, arena_tools=arena.tools) as mock:
                    cfg = replace(config, base_url=mock.base_url, api_key="mock-key")
                    try:
                        agent = adapter.build(arena, cfg)
                    except Exception as exc:
                        record.update(available=False, reason=f"build failed: {exc}")
                        break
                    began = time.perf_counter()
                    error = None
                    result = None
                    with fixture(case) as state:
                        try:
                            result = agent.run(item)
                            error = result.error
                        except Exception as exc:
                            error = f"{type(exc).__name__}: {exc}"
                    observed = observe(
                        case,
                        mock.response_messages,
                        mock.requests,
                        state,
                        run_id=run_id,
                        actor=name,
                    )
                    usage = mock.served_usage
                    metrics = {
                        k: v
                        for k, v in observed.items()
                        if k not in {"events", "fixture", "attempts"}
                    }
                    passed = (
                        not error
                        and metrics["fixture_policy_valid"]
                        and metrics["fail_closed"]
                        and metrics["trace_complete"]
                        and metrics["extra_effects"] == 0
                        and all(
                            metrics[k]["passed"] == metrics[k]["total"]
                            for k in ("denial_propagation", "allowed_work")
                        )
                    )
                    record["items"].append(
                        {
                            "item_id": item.id,
                            "repeat": rep,
                            "passed": passed,
                            "checks": [],
                            "output_text": result.output_text if result else "",
                            "error": error,
                            "observation_status": (
                                "harness_error"
                                if not metrics["fixture_policy_valid"]
                                else "observed_failure"
                                if not passed
                                else "observed_pass"
                            ),
                            "tool_calls": [c.get("name") for c in result.tool_calls]
                            if result
                            else [],
                            **usage,
                            "latency_s": time.perf_counter() - began,
                            "boundary": observed,
                            "metrics": metrics,
                            "wire_requests": mock.requests,
                            "wire_responses": mock.response_messages,
                        }
                    )
                    if progress:
                        progress(name, item.id, passed)
            if not record["available"]:
                break
    manifest = provenance(
        command=[
            "python",
            "-m",
            "arena",
            "run",
            "--arena",
            arena.id,
            *[arg for name in framework_names for arg in ("--framework", name)],
            "--mode",
            "mock",
            "--repeat",
            str(config.repeat),
            *[arg for item_id in sorted(only or []) for arg in ("--item", item_id)],
        ],
        mode="mock",
        configuration={
            "max_tool_iterations": config.max_tool_iterations,
            "temperature": config.temperature,
            "request_timeout_s": config.request_timeout_s,
            "only": sorted(only) if only else None,
        },
        repetitions=config.repeat,
        files=[
            CASES_PATH,
            Path(arena.mock_script_path),
            Path(__file__),
            REPO_ROOT / "arena/boundary.py",
            REPO_ROOT / "arena/evidence.py",
            REPO_ROOT / "arenas/boundary_response/dataset.jsonl",
        ],
        exclusions=[
            "OS sandbox isolation",
            "arbitrary code mediation",
            "real-model recovery",
            "delegation",
            "native approval UI",
            "real credentials or network policy",
        ],
    )
    report = {
        "harness_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "temperature": config.temperature,
        "schema": 1,
        "arena": arena.id,
        "arena_description": arena.description,
        "mode": "mock",
        "model": "mock-model",
        "repeat": config.repeat,
        "dataset_size": len(only) if only else len(cases),
        "frameworks": frameworks,
        "started_at": datetime.now(UTC).isoformat(),
        "duration_s": time.perf_counter() - start,
        "provenance": manifest,
        "pricing": {"input_per_m": 0, "output_per_m": 0},
    }
    directory = REPO_ROOT / "runs"
    directory.mkdir(exist_ok=True)
    suffix = "__partial" if only else ""
    path = directory / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}__boundary_response__mock{suffix}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["_path"] = str(path)
    return report
