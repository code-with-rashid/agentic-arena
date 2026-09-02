"""Report how each framework handles a gateway that fails, not a model that misbehaves.

Report-only, like report_overhead.py: the differences are findings, not
regressions. It fails only if the *baseline* stops behaving as documented, which
would mean the probe is broken rather than a framework being unusual.

    python .github/scripts/report_transport.py           # fast plans only
    python .github/scripts/report_transport.py --deep    # adds 429 x3

`--deep` is separate because smolagents sleeps for over two minutes rather than
give up on three consecutive 429s, which is the most interesting result here and
also far too slow to run on every push.
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
DEEP = [("429 x3", [429, 429, 429, 200])]


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


plans = FAST + (DEEP if "--deep" in sys.argv else [])
names = buildable()
print("\ntransport faults - what each framework does when the GATEWAY fails\n")
print(f"  {'framework':16}" + "".join(f"  {label:<26}" for label, _ in plans))
for name in sorted(names):
    cells = []
    for _, faults in plans:
        outcome, attempts, gaps, elapsed = run(name, list(faults))
        slow = f" +{elapsed:.0f}s" if elapsed > 5 else ""
        cells.append(f"{outcome} ({attempts}){slow}")
    print(f"  {name:16}" + "".join(f"  {c:<26}" for c in cells))

print("\n  Bracketed number is HTTP attempts that reached the wire, retries included.")
print("  Differences are findings, not regressions - see docs/transport.md.")

if "vanilla" in names:
    outcome, attempts, _, _ = run("vanilla", [429, 200])
    if attempts != 1:
        sys.exit(f"\nBASELINE CHANGED: vanilla made {attempts} attempts on one 429, expected 1")
    print("\n  baseline check: vanilla still has no retry (1 attempt on a 429). ok")
