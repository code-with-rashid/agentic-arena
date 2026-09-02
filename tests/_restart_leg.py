"""One leg of a `durable_state` run, in its own interpreter.

Not a test. `test_durable_across_a_restart.py` invokes this twice as a
subprocess, so that nothing except a JSON file and the harness-owned
`checkpoint_dir` can carry state between the two legs — which is the only way to
tell real durability from an adapter caching state in a process global.

    python tests/_restart_leg.py <leg1|leg2> <framework> <workdir>

Prints one JSON object on stdout. Anything on stderr is the framework's own
noise and is ignored by the caller.
"""

from __future__ import annotations

import json
import pathlib
import sys
from dataclasses import replace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from arena.config import ArenaConfig  # noqa: E402
from arena.llm.mockserver import MockScript, MockServer  # noqa: E402
from arena.registry import load_arena, load_framework  # noqa: E402

CHEATER = "__cheater__"


def _build(framework, arena, config):
    """The cheater is a test fixture, not a registered adapter."""
    if framework == CHEATER:
        from tests._cheating_adapter import Adapter

        return Adapter().build(arena, config)
    return load_framework(framework).build(arena, config)


def main() -> None:
    leg, framework, workdir = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
    checkpoints = workdir / "ckpt"
    checkpoints.mkdir(parents=True, exist_ok=True)
    state_file = workdir / "state.json"

    arena = load_arena("durable_state")
    item = arena.dataset[0]
    script = MockScript.load(arena.mock_script_path)

    with MockServer(script, arena_tools=list(arena.tools)) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=8,
            checkpoint_dir=str(checkpoints),
        )
        runner = _build(framework, arena, config)

        if leg == "leg1":
            result = runner.run(item)
            if not result.suspended:
                print(json.dumps({"ok": False, "why": "did not suspend"}))
                return
            # Exactly what the harness carries across the gap: JSON, nothing else.
            state_file.write_text(json.dumps(result.resume_state), encoding="utf-8")
            print(
                json.dumps(
                    {
                        "ok": True,
                        "tool_calls": [c.get("name") for c in result.tool_calls],
                        "checkpoint_files": sorted(
                            p.name for p in checkpoints.rglob("*") if p.is_file()
                        ),
                    }
                )
            )
            return

        state = json.loads(state_file.read_text(encoding="utf-8"))
        runner = _build(framework, arena, config)
        try:
            result = runner.resume(item, state, "approved")
        except Exception as exc:  # noqa: BLE001 - the outcome under test
            print(json.dumps({"ok": False, "why": f"{type(exc).__name__}: {str(exc)[:200]}"}))
            return
        print(
            json.dumps(
                {
                    "ok": True,
                    "output": result.output_text or "",
                    "tool_calls": [c.get("name") for c in result.tool_calls],
                }
            )
        )


main()
