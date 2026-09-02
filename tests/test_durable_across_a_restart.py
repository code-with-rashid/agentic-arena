"""Durability, tested against an actual process boundary.

`test_durable_state.py` opens with "durability has to be demonstrated, not
declared", and then demonstrates it *within one interpreter*: the harness
rebuilds the runner and JSON round-trips `resume_state`, which rules out handing
a live object across.

It does not rule out an adapter stashing state in a module-level cache keyed by
item id and sending only the key. That survives the rebuild **and** the JSON gap,
and it could not survive the restart the arena is named after.

Measured, with `tests/_cheating_adapter.py`: a cheat like that scores
`durable_state` **8/8** today, with `['search', 'search', 'calculator']` and one
suspend — indistinguishable in the scorecard from the honest `vanilla` it wraps.
So this is a real hole in the benchmark's strongest claim, not a hypothetical.

What closes it is running the two legs in two interpreters, with nothing between
them but a JSON file and the harness-owned `checkpoint_dir`:

    adapter          leg 2 in a fresh process    checkpoint files written
    ------------------------------------------------------------------------
    vanilla          ok                          none - transcript in the state
    pydantic_ai      ok                          none - message history as JSON
    openai_agents    ok                          none - RunState.to_json()
    langgraph        ok                          langgraph.sqlite (+wal, +shm)
    google_adk       ok                          adk_sessions.sqlite
    __cheater__      KeyError: 'dur-01'          none

All five real adapters pass, which is a negative result and the point of running
it: the published 8/8s mean what they say. The last row is what stops this file
from being a test that can only succeed.

That table is also the honest version of the "stateless resume vs real
checkpointer" distinction the docs draw. It is read off what lands in
`checkpoint_dir`, not off the adapter source.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from arena.config import ArenaConfig
from arena.registry import available_frameworks, load_arena, load_framework

ARENA = load_arena("durable_state")
LEG = Path(__file__).resolve().parent / "_restart_leg.py"
CHEATER = "__cheater__"
ANSWER = "498"


def _resumable():
    """Adapters that offer a `resume` on the durable arena, in this environment."""
    out = []
    for name in available_frameworks():
        try:
            runner = load_framework(name).build(ARENA, ArenaConfig(mode="mock"))
        except Exception:  # noqa: BLE001 - stub, or not installed here
            continue
        if hasattr(runner, "resume"):
            out.append(name)
    return out


RESUMABLE = _resumable()


def _leg(which, framework, workdir):
    """Run one leg in its own interpreter and return its JSON report."""
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(LEG), which, framework, str(workdir)],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(LEG.parent.parent),
        check=False,
    )
    # Frameworks are noisy on stderr and some warn on stdout; the report is the
    # last line that parses as JSON.
    for line in reversed(proc.stdout.splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise AssertionError(
        f"{framework} {which} produced no report (exit {proc.returncode})\n"
        f"stdout: {proc.stdout[-800:]}\nstderr: {proc.stderr[-800:]}"
    )


def _both_legs(framework, tmp_path):
    workdir = tmp_path / framework.strip("_")
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        first = _leg("leg1", framework, workdir)
        assert first["ok"], f"{framework} leg 1: {first.get('why')}"
        return first, _leg("leg2", framework, workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@pytest.mark.parametrize("name", RESUMABLE)
def test_durability_survives_a_restart(name, tmp_path):
    """The claim `durable_state` is named for, tested against a real restart.

    Leg two runs in a fresh interpreter and knows nothing except the JSON the
    harness carried and whatever the adapter wrote into `checkpoint_dir`. An
    adapter that kept state in process memory raises here while passing every
    other durability check in the repo.
    """
    first, second = _both_legs(name, tmp_path)
    assert second["ok"], f"{name} did not survive a restart: {second.get('why')}"
    assert ANSWER in second["output"], f"{name} resumed but answered {second['output']!r}"


@pytest.mark.parametrize("name", RESUMABLE)
def test_the_work_done_before_the_pause_is_not_redone(name, tmp_path):
    """Resumed, not restarted — the distinction the whole arena exists to draw.

    Both lookups happen before the pause and the arithmetic after it, so a
    framework that quietly began again would show `search` in leg two. Checked
    across the process boundary because that is where "began again" is easiest
    to do by accident.
    """
    first, second = _both_legs(name, tmp_path)
    assert first["tool_calls"] == ["search", "search"], f"{name} leg 1: {first['tool_calls']}"
    assert second["tool_calls"] == ["calculator"], (
        f"{name} redid work after the restart: {second['tool_calls']}"
    )


def test_the_restart_probe_actually_catches_a_process_global_cheat(tmp_path):
    """Without this, a green file above would prove only that the probe ran.

    `tests/_cheating_adapter.py` wraps the honest baseline and moves the resume
    state into a module-level dict, sending only a key across the gap. It scores
    `durable_state` 8/8 and passes every other durability check in the repo,
    because the state is valid JSON and the runner really is rebuilt.

    In a second interpreter its cache is empty.
    """
    first, second = _both_legs(CHEATER, tmp_path)
    assert first["ok"], first
    assert not second["ok"], (
        "a process-global cache survived a restart — the probe is not isolating "
        f"the interpreters: {second}"
    )
    assert "KeyError" in second["why"], second["why"]


def test_who_writes_a_checkpoint_and_who_serialises_the_transcript(tmp_path):
    """Report-only: the mechanism split, read off disk rather than off the source.

    `langgraph` and `google_adk` keep a real on-disk store in `checkpoint_dir`;
    `vanilla`, `pydantic_ai` and `openai_agents` write nothing there and carry
    the whole conversation in `resume_state`. Both are legitimately durable —
    that is the finding — but only the first kind keeps working once the state
    stops fitting in a message list.

    Which side an adapter falls on is a finding, not a gate — either route is
    legitimately durable. What *is* gated is that a checkpointing adapter writes
    into the directory the harness owns. `langgraph` once wrote its sqlite file
    into the repo root instead, which works, passes, and is the kind of thing
    that gets committed by accident.
    """
    if "vanilla" not in RESUMABLE:
        pytest.skip("baseline not buildable here")
    written = {}
    for name in RESUMABLE:
        first, _ = _both_legs(name, tmp_path)
        written[name] = first["checkpoint_files"]
    assert written["vanilla"] == [], (
        f"the baseline started writing checkpoints: {written['vanilla']} — "
        "docs/methodology.md calls it a stateless resume"
    )
    # Only the two that keep a real store. Absent from a venv that has neither,
    # which is why this is keyed on what is installed rather than on a count.
    for name in ("langgraph", "google_adk"):
        if name in written:
            assert written[name], (
                f"{name} resumed without writing anything to checkpoint_dir. It uses an "
                f"on-disk store, so it is now keeping it somewhere the harness does not "
                f"own and cannot clear between runs"
            )
