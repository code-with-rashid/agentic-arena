"""Report the resilience comparison, and gate the counts the docs publish.

Frameworks are expected to score differently on this arena — that difference is
the measurement. Two things must hold:

  * the stdlib `vanilla` baseline recovers from every scripted fault (if it does
    not, the arena is broken rather than the framework);
  * every count in `EXPECTED` still matches. `docs/findings.md` §2 and
    `docs/decision-guide.md` §2 publish a per-framework recovery table, and
    nothing was pinning it — `smolagents` silently went from 4/8 to 8/8 (it
    started answering from its last memory step on an exhausted run) and no test
    noticed for iterations. A framework absent from the run is skipped, not
    failed, so this is meaningful in CI's comparison job and harmless anywhere a
    subset is installed.
"""

import json
import pathlib
import sys

# The recovery count docs/findings.md §2 publishes for each framework. Update
# this and the two doc tables in the same commit — a drift here is either a real
# regression or a finding that needs writing down.
EXPECTED = {
    "vanilla": 8,
    "pydantic_ai": 8,
    "microsoft_af": 8,
    "langgraph": 7,
    "openai_agents": 7,
    "google_adk": 6,
    "smolagents": 8,
}

runs = sorted(pathlib.Path("runs").glob("*__resilience__mock.json"))
if not runs:
    sys.exit("no resilience run found")

record = json.loads(runs[-1].read_text())
total = record["dataset_size"] * record["repeat"]

print(f"\nresilience - {total} scripted faults, {record['repeat']} repeat(s)\n")
baseline_ok = False
drifted: list[str] = []
for fw in record["frameworks"]:
    name = fw["framework"]
    if not fw.get("available"):
        print(f"  {name:<18} unavailable - {fw.get('reason', '')[:70]}")
        continue

    passed = sum(1 for item in fw["items"] if item["passed"])
    failures = [item for item in fw["items"] if not item["passed"]]
    note = ""
    if name in EXPECTED and passed != EXPECTED[name]:
        note = f"  <- docs say {EXPECTED[name]}/{len(fw['items'])}"
        drifted.append(f"{name}: ran {passed}/{len(fw['items'])}, docs say {EXPECTED[name]}")
    print(f"  {name:<18} {passed}/{len(fw['items'])} recovered{note}")
    for item in failures:
        why = item["error"] or "gave up (no answer, no error raised)"
        print(f"       ! {item['item_id']}  {why[:90]}")

    if name == "vanilla":
        baseline_ok = passed == len(fw["items"])

if not baseline_ok:
    sys.exit("\nthe stdlib baseline failed a scripted fault — the arena is broken")
if drifted:
    sys.exit(
        "\nresilience recovery count drifted from the published table:\n  "
        + "\n  ".join(drifted)
        + "\nIf this is intended, correct docs/findings.md §2, docs/decision-guide.md §2 "
        "and EXPECTED in this file together."
    )
print("\nbaseline recovered from every fault; every published count still matches")
