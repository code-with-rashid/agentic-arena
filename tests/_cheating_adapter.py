"""An adapter that is "durable" only within one process.

A test fixture, deliberately not registered in `frameworks/`. It exists to keep
`test_durable_across_a_restart.py` honest: without something that *should* fail,
a passing suite proves only that the probe ran.

The cheat is one line. It puts everything the real adapter needed into a
module-level cache keyed by item id, and sends only the key across:

    _STASH[item.id] = out.resume_state
    out.resume_state = {"stash_key": item.id}

That is invisible to every check the repo had before this one. The state is
valid JSON, so `arena.runner._across_the_gap` accepts it. The runner is rebuilt,
so `test_durable_state.py`'s rebuild assertion passes. The transcript is not a
live object, so the `_SmugglerAgent` check does not fire. Measured: it scores
`durable_state` **8/8**, with `['search', 'search', 'calculator']` and one
suspend — byte-identical in the scorecard to the honest `vanilla` it wraps.

In a second interpreter `_STASH` is empty and `resume` raises `KeyError`, which
is the whole point.
"""

from __future__ import annotations

from typing import Any

from arena.config import ArenaConfig
from arena.types import AgentResult, ArenaSpec, EvalItem

# The cheat: process-global, so it survives a rebuilt runner and a JSON
# round-trip, and nothing else.
_STASH: dict[str, Any] = {}


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        from frameworks.vanilla.adapter import _Runner as Baseline

        self._real = Baseline(arena, config)

    def run(self, item: EvalItem) -> AgentResult:
        out = self._real.run(item)
        if out.suspended and isinstance(out.resume_state, dict):
            _STASH[item.id] = out.resume_state
            out.resume_state = {"stash_key": item.id}
        return out

    def resume(self, item: EvalItem, state: Any, decision: str) -> AgentResult:
        # KeyError in a fresh process, which is what the restart test detects.
        return self._real.resume(item, _STASH[state["stash_key"]], decision)


class Adapter:
    name = "__cheater__"
    lib_version = "test fixture"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
