"""Report what each framework adds on top of an identical task.

Mock-mode pass rates are not a quality signal, but mock-mode *prompt size* is a
real comparison: every framework is handed the same arena prompt and the same two
tool definitions, and the mock replays byte-identical turns. Whatever difference
shows up is the framework's own serialisation — mostly how verbosely it renders
the tool schemas — and a provider bills for every byte of it.

Report-only. It fails only if the `vanilla` baseline is missing, which would mean
the run itself was wrong rather than any framework being slow.
"""

import json
import pathlib
import sys

arena = sys.argv[1] if len(sys.argv) > 1 else "tool_use"
runs = sorted(pathlib.Path("runs").glob(f"*__{arena}__mock.json"))
if not runs:
    sys.exit(f"no {arena} run found")

record = json.loads(runs[-1].read_text())
rows = []
for fw in record["frameworks"]:
    if not fw.get("available"):
        print(f"  {fw['framework']:<18} unavailable - {fw.get('reason', '')[:60]}")
        continue
    items = fw["items"]
    if not items:
        continue
    n = len(items)
    rows.append(
        {
            "name": fw["framework"],
            "prompt": sum(i["prompt_tokens"] for i in items) / n,
            "completion": sum(i["completion_tokens"] for i in items) / n,
            "calls": sum(i["llm_calls"] for i in items) / n,
        }
    )

baseline = next((r for r in rows if r["name"] == "vanilla"), None)
if baseline is None:
    sys.exit("no vanilla baseline in the run - cannot compute overhead")

print(f"\nframework overhead on '{arena}' - mean per item, mock mode\n")
print(f"  {'framework':<18}{'prompt tok':>11}{'vs base':>10}{'completion':>12}{'llm calls':>11}")
for row in sorted(rows, key=lambda r: r["prompt"]):
    ratio = row["prompt"] / baseline["prompt"]
    print(
        f"  {row['name']:<18}{row['prompt']:>11.0f}{ratio:>9.2f}x"
        f"{row['completion']:>12.1f}{row['calls']:>11.2f}"
    )

spread = max(r["prompt"] for r in rows) / min(r["prompt"] for r in rows)
print(f"\n  spread: {spread:.2f}x between the leanest and the heaviest framework")
print("  These are estimated tokens (chars/4) over messages + tool schemas. Use them to")
print("  compare frameworks with each other, not to predict a provider bill.")
