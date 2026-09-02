"""Report how the prompt grows as a tool loop gets longer.

docs/overhead.md measures a two-call task. That is where framework overhead looks
largest, because a fixed per-request cost is being divided by two requests. This
runs the same identical scripted conversation out to N turns and prints the whole
curve, which is what says whether that overhead ever stops mattering.

Report-only, like report_overhead.py and report_transport.py: the constants are
findings. It fails only if the *shape* changes - if some framework starts
truncating history, the comparison stops being between identical conversations
and every number in docs/overhead.md is measuring something else.

    python .github/scripts/report_growth.py        # 12 turns
    python .github/scripts/report_growth.py 30     # longer curve
"""

import json
import sys
from dataclasses import replace

sys.path.insert(0, ".")

from arena.config import ArenaConfig  # noqa: E402
from arena.llm.mockserver import MockScript, MockServer  # noqa: E402
from arena.registry import available_frameworks, load_framework  # noqa: E402
from arena.types import ArenaSpec, EvalItem  # noqa: E402

STUBS = {"claude_agent_sdk"}
ANSWER = "The Eiffel Tower is 330 metres tall."
# Rotated so the tool results differ turn to turn, the way a real loop's would.
QUERIES = ["eiffel tower", "great wall", "amazon river", "mount everest", "sahara"]
ITEM = EvalItem(id="g-01", input="How tall is the Eiffel Tower?", checks=[])


def arena():
    return ArenaSpec(
        id="growth",
        description="prompt growth over a long tool loop",
        tools=["search"],
        system_prompt_intent="\nAnswer the question concisely.\n",
        dataset=[],
        mock_script_path="",
    )


def script(turns):
    """`turns` scripted search calls, then an answer. Identical for every client."""
    steps = [
        {"tool_calls": [{"name": "search", "arguments": {"query": QUERIES[i % len(QUERIES)]}}]}
        for i in range(turns)
    ]
    return MockScript({"default": {"turns": [*steps, {"content": ANSWER}]}})


def sizes(name, turns):
    """Estimated prompt tokens for each request the framework sent."""
    with MockServer(script(turns), arena_tools=["search"]) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=turns + 4,
        )
        try:
            load_framework(name).build(arena(), config).run(ITEM)
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            print(f"  {name:16}  raised {type(exc).__name__}: {exc}")
            return []
        out = []
        for req in server.requests:
            chars = len(json.dumps(req.get("messages", [])))
            chars += len(json.dumps(req.get("tools", []))) if req.get("tools") else 0
            out.append(chars // 4)
        return out


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


turns = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 12
names = sorted(buildable())

print(f"\nprompt growth over a {turns}-turn scripted tool loop\n")

rows = {}
for name in names:
    curve = sizes(name, turns)
    if len(curve) >= 3:
        rows[name] = curve

base = rows.get("vanilla")
print(
    f"  {'framework':16}  {'first':>6}  {'last':>6}  {'per turn':>8}  {'total':>8}  {'vs base':>8}"
)
for name, curve in rows.items():
    deltas = [b - a for a, b in zip(curve, curve[1:], strict=False)]
    per = sum(deltas) / len(deltas)
    ratio = f"{sum(curve) / sum(base):7.2f}x" if base else "        "
    print(f"  {name:16}  {curve[0]:6}  {curve[-1]:6}  {per:8.1f}  {sum(curve):8}  {ratio}")

if base:
    print("\n  ratio to the stdlib baseline, request by request:\n")
    print(f"  {'framework':16}" + "".join(f"  #{i + 1:<5}" for i in range(min(len(base), 6))))
    for name, curve in rows.items():
        cells = [f"{curve[i] / base[i]:.2f}x" for i in range(min(len(base), len(curve), 6))]
        print(f"  {name:16}" + "".join(f"  {c:<6}" for c in cells))

print("\n  Constants are findings - see docs/overhead.md.")

# The one thing that is not a finding: a framework that dropped history would
# make every comparison in docs/overhead.md a comparison of different
# conversations. Fail loudly rather than print a wrong table.
for name, curve in rows.items():
    if any(b <= a for a, b in zip(curve, curve[1:], strict=False)):
        sys.exit(f"\nSHAPE CHANGED: {name}'s prompt stopped growing monotonically: {curve}")
print("  shape check: every framework still resends the full history. ok")
