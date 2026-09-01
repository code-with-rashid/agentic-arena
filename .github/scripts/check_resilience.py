"""Report the resilience comparison; fail only if the baseline itself broke.

Frameworks are expected to score differently on this arena — that difference is
the measurement. The only thing that must hold is that the stdlib `vanilla`
baseline recovers from every scripted fault; if it does not, the arena is broken
rather than the framework.
"""

import json
import pathlib
import sys

runs = sorted(pathlib.Path("runs").glob("*__resilience__mock.json"))
if not runs:
    sys.exit("no resilience run found")

record = json.loads(runs[-1].read_text())
total = record["dataset_size"] * record["repeat"]

print(f"\nresilience - {total} scripted faults, {record['repeat']} repeat(s)\n")
baseline_ok = False
for fw in record["frameworks"]:
    name = fw["framework"]
    if not fw.get("available"):
        print(f"  {name:<18} unavailable - {fw.get('reason', '')[:70]}")
        continue

    passed = sum(1 for item in fw["items"] if item["passed"])
    failures = [item for item in fw["items"] if not item["passed"]]
    print(f"  {name:<18} {passed}/{len(fw['items'])} recovered")
    for item in failures:
        why = item["error"] or "gave up (no answer, no error raised)"
        print(f"       ! {item['item_id']}  {why[:90]}")

    if name == "vanilla":
        baseline_ok = passed == len(fw["items"])

if not baseline_ok:
    sys.exit("\nthe stdlib baseline failed a scripted fault — the arena is broken")
print("\nbaseline recovered from every fault; per-framework differences above are the result")
