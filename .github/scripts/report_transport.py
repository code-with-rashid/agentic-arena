"""Report how each framework handles a gateway that fails, not a model that misbehaves.

Mostly report-only, like report_overhead.py: the outcome differences are
findings. Two things are gated, because a published number had already gone
stale once (smolagents' `resilience` count) with nothing noticing:

  * the `vanilla` baseline still has no retry (1 attempt on a 429);
  * every retrying framework still gives up after the number of retries
    docs/transport.md and docs/feature-matrix.md publish — `langgraph` once,
    the rest twice — measured on three consecutive 429s.

`smolagents` is excluded from that second gate and from the default run: it does
not give up on three 429s, it sleeps for two to four minutes and then succeeds,
which is its documented finding and far too slow for every push. `--deep` adds
it back as report-only.

    python .github/scripts/report_transport.py           # gated plans
    python .github/scripts/report_transport.py --deep    # + smolagents' 429 x3 sleep
"""

import sys
import time
from dataclasses import replace

sys.path.insert(0, ".")

from arena.config import ArenaConfig  # noqa: E402
from arena.llm.mockserver import MockScript, MockServer  # noqa: E402
from arena.registry import available_frameworks, load_framework  # noqa: E402
from arena.types import ArenaSpec, EvalItem  # noqa: E402

STUBS = {"claude_agent_sdk"}
ANSWER = "The Eiffel Tower is 330 metres tall."
SCRIPT = MockScript({"default": {"turns": [{"content": ANSWER}]}})
ITEM = EvalItem(id="t-01", input="How tall is the Eiffel Tower?", checks=[])

FAST = [("healthy", []), ("429 once", [429, 200]), ("500 once", [500, 200]), ("400", [400, 200])]
# Three consecutive 429s: every framework except smolagents gives up fast, after
# its own number of retries. That is the number docs/transport.md publishes, so
# it is gated here (smolagents runs it only under --deep, where it sleeps).
GIVE_UP = ("429 x3", [429, 429, 429, 200])
DEEP = [GIVE_UP]
SMOLAGENTS = "smolagents"

# HTTP attempts before giving up on three 429s = 1 + the framework's retry count.
# vanilla: no retry. langgraph: one. everyone else: two. From docs/transport.md.
GIVE_UP_ATTEMPTS = {
    "vanilla": 1,
    "langgraph": 2,
    "pydantic_ai": 3,
    "openai_agents": 3,
    "microsoft_af": 3,
    "google_adk": 3,
}


def arena():
    return ArenaSpec(
        id="transport",
        description="transport faults",
        tools=["search"],
        system_prompt_intent="\nAnswer the question concisely.\n",
        dataset=[],
        mock_script_path="",
    )


def run(name, faults):
    with MockServer(SCRIPT, arena_tools=["search"], faults=faults) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=6,
        )
        started = time.perf_counter()
        try:
            result = load_framework(name).build(arena(), config).run(ITEM)
            outcome = "ok" if ANSWER in (result.output_text or "") else "gave up"
        except Exception as exc:  # noqa: BLE001 - the outcome being reported
            outcome = f"raised {type(exc).__name__}"
        elapsed = time.perf_counter() - started
        # Pairing a list with its own tail, so the lengths differ by one by
        # construction - strict=False is correct here, not a shortcut.
        pairs = zip(server.attempts, server.attempts[1:], strict=False)
        gaps = [round(b - a, 2) for a, b in pairs]
        return outcome, len(server.attempts), gaps, elapsed


def buildable():
    out = []
    for name in available_frameworks():
        if name in STUBS or name.endswith("_multi"):
            continue
        try:
            config = replace(ArenaConfig(mode="mock"), base_url="http://127.0.0.1:1", api_key="k")
            load_framework(name).build(arena(), config)
        except Exception:  # noqa: BLE001 - not installed here
            continue
        out.append(name)
    return out


deep = "--deep" in sys.argv
# smolagents runs the give-up plan only under --deep (it sleeps 2-4 min there).
plans = FAST + [GIVE_UP] + (DEEP if deep else [])
names = buildable()
print("\ntransport faults - what each framework does when the GATEWAY fails\n")
print(f"  {'framework':16}" + "".join(f"  {label:<26}" for label, _ in plans))
for name in sorted(names):
    cells = []
    for label, faults in plans:
        if label == GIVE_UP[0] and name == SMOLAGENTS and not deep:
            cells.append("(skipped - sleeps)")
            continue
        outcome, attempts, gaps, elapsed = run(name, list(faults))
        slow = f" +{elapsed:.0f}s" if elapsed > 5 else ""
        cells.append(f"{outcome} ({attempts}){slow}")
    print(f"  {name:16}" + "".join(f"  {c:<26}" for c in cells))

print("\n  Bracketed number is HTTP attempts that reached the wire, retries included.")
print("  Outcome differences are findings; the give-up attempt counts are gated.")

# --- gates -----------------------------------------------------------------
drifted: list[str] = []
if "vanilla" in names:
    _, attempts, _, _ = run("vanilla", [429, 200])
    if attempts != 1:
        sys.exit(f"\nBASELINE CHANGED: vanilla made {attempts} attempts on one 429, expected 1")

for name in sorted(names):
    if name == SMOLAGENTS or name not in GIVE_UP_ATTEMPTS:
        continue
    _, attempts, _, _ = run(name, list(GIVE_UP[1]))
    if attempts != GIVE_UP_ATTEMPTS[name]:
        drifted.append(
            f"{name}: gave up after {attempts} attempts on 429 x3, docs say {GIVE_UP_ATTEMPTS[name]}"
        )

if drifted:
    sys.exit(
        "\nretry behaviour drifted from the published table:\n  "
        + "\n  ".join(drifted)
        + "\nIf intended, correct docs/transport.md, docs/feature-matrix.md and "
        "GIVE_UP_ATTEMPTS in this file together."
    )
print("\n  gates: vanilla still has no retry; every retry count matches docs/transport.md.")
