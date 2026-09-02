"""Executes framework x arena x repeat, scores every item, and records the run."""

from __future__ import annotations

import json
import platform
import time
import traceback
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from . import __version__
from .config import REPO_ROOT, ArenaConfig
from .llm.mockserver import MockServer
from .registry import load_arena, load_framework
from .scorer import score_item
from .tools import SUSPEND_TOOL
from .types import AgentResult, ArenaSpec, EvalItem

RUNS_DIR = REPO_ROOT / "runs"

# A suspend/resume cycle that never terminates would hang the whole run. Real
# arenas need one pause; the cap only exists so a broken adapter fails loudly.
MAX_RESUMES = 3


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _merge_legs(legs: list[AgentResult]) -> AgentResult:
    """Fold a suspended run's legs into the single result the scorer sees.

    Cost is summed across legs — a framework that pauses and resumes pays for
    the whole conversation, and hiding the first leg's tokens would make an
    interrupting framework look cheaper than one that runs straight through.
    """
    last = legs[-1]
    if len(legs) == 1:
        return last
    return replace(
        last,
        tool_calls=[tc for leg in legs for tc in leg.tool_calls],
        prompt_tokens=sum(leg.prompt_tokens for leg in legs),
        completion_tokens=sum(leg.completion_tokens for leg in legs),
        latency_s=sum(leg.latency_s for leg in legs),
        llm_calls=sum(leg.llm_calls for leg in legs),
        tool_calls_before_suspend=list(legs[0].tool_calls),
        suspends=sum(1 for leg in legs if leg.suspended),
    )


def _run_item(agent: Any, item: EvalItem) -> AgentResult:
    """Run one item, driving any suspend/resume cycle to completion."""
    legs = [agent.run(item)]
    while legs[-1].suspended and len(legs) <= MAX_RESUMES:
        if not hasattr(agent, "resume"):
            return replace(
                _merge_legs(legs),
                error="adapter suspended but does not implement resume()",
            )
        decision = item.resume_with or "approve"
        legs.append(agent.resume(item, legs[-1].resume_state, decision))
    if legs[-1].suspended:
        return replace(
            _merge_legs(legs),
            error=f"still suspended after {MAX_RESUMES} resumes",
        )
    return _merge_legs(legs)


def _run_one_framework(fw_name: str, arena: ArenaSpec, config: ArenaConfig) -> dict[str, Any]:
    record: dict[str, Any] = {"framework": fw_name, "items": [], "available": True}
    try:
        adapter = load_framework(fw_name)
    except Exception as exc:  # noqa: BLE001
        return {**record, "available": False, "reason": f"load failed: {exc}"}

    try:
        record["lib_version"] = adapter.lib_version
    except Exception as exc:  # noqa: BLE001
        record["lib_version"] = f"unknown ({exc})"

    try:
        agent = adapter.build(arena, config)
    except NotImplementedError as exc:
        return {**record, "available": False, "reason": f"stub adapter: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {
            **record,
            "available": False,
            "reason": f"build failed: {exc}",
            "traceback": traceback.format_exc(),
        }

    # "This framework has no interrupt mechanism wired up" and "this framework
    # tried to pause and got it wrong" are different findings, and scoring them
    # both as a pile of failed items would conflate them.
    if SUSPEND_TOOL in arena.tools and not hasattr(agent, "resume"):
        return {
            **record,
            "available": False,
            "reason": (
                "arena requires a pause for human approval, but this adapter does "
                "not implement the resume API (arena.types.ResumableRunner)"
            ),
        }

    for rep in range(config.repeat):
        for item in arena.dataset:
            started = time.perf_counter()
            error_tb: str | None = None
            try:
                result = _run_item(agent, item)
            except Exception as exc:  # noqa: BLE001
                # Keep the traceback: an adapter that fails every item otherwise
                # reports one unhelpful line, and the frame that actually raised
                # is usually deep inside the framework.
                error_tb = traceback.format_exc()
                result = AgentResult(error=f"{type(exc).__name__}: {exc}")
            if not result.latency_s:
                result = replace(result, latency_s=time.perf_counter() - started)
            outcome = score_item(item, result)
            record["items"].append(
                {
                    "repeat": rep,
                    "item_id": item.id,
                    "passed": outcome.passed,
                    "checks": outcome.checks,
                    "output_text": result.output_text,
                    "tool_calls": [tc.get("name") for tc in result.tool_calls],
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "latency_s": round(result.latency_s, 4),
                    "llm_calls": result.llm_calls,
                    "error": result.error,
                    **(
                        {
                            "suspends": result.suspends,
                            "tool_calls_before_suspend": [
                                tc.get("name") for tc in result.tool_calls_before_suspend
                            ],
                        }
                        if result.suspends
                        else {}
                    ),
                    **({"traceback": error_tb} if error_tb else {}),
                }
            )
    return record


def run(
    arena_id: str,
    framework_names: list[str],
    *,
    config: ArenaConfig | None = None,
) -> dict[str, Any]:
    config = config or ArenaConfig.from_env()
    arena = load_arena(arena_id)

    mock: MockServer | None = None
    if config.mode == "mock":
        mock = MockServer(arena.mock_script_path).start()
        config = replace(config, base_url=mock.base_url, api_key="mock-key")

    started = _now_iso()
    t0 = time.perf_counter()
    try:
        frameworks = [_run_one_framework(name, arena, config) for name in framework_names]
    finally:
        if mock is not None:
            mock.stop()

    record = {
        "schema": 1,
        "arena": arena.id,
        "arena_description": arena.description,
        "mode": config.mode,
        "model": config.model if config.mode == "live" else "mock-model",
        "repeat": config.repeat,
        "dataset_size": len(arena.dataset),
        "started_at": started,
        "duration_s": round(time.perf_counter() - t0, 2),
        "harness_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pricing": {
            "input_per_m": config.price_input_per_m,
            "output_per_m": config.price_output_per_m,
        },
        "frameworks": frameworks,
    }

    RUNS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = RUNS_DIR / f"{stamp}__{arena.id}__{config.mode}.json"
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    record["_path"] = str(out_path)
    return record
