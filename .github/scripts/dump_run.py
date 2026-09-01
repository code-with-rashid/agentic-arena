"""Print the most recent run record's failures, with tracebacks."""

import json
import pathlib

runs = sorted(pathlib.Path("runs").glob("*__mock.json"))
if not runs:
    print("no run file")
    raise SystemExit(0)

rec = json.loads(runs[-1].read_text())
fw = rec["frameworks"][0]
print("available:", fw.get("available"), "| reason:", fw.get("reason"))
print("build traceback:", (fw.get("traceback") or "")[:2000])
for item in fw.get("items", [])[:2]:
    print("---", item["item_id"], "passed:", item["passed"])
    print("  error :", item["error"])
    print("  output:", repr(item["output_text"])[:300])
    print("  tools :", item["tool_calls"])
    print("  TB    :\n", (item.get("traceback") or "(none)")[-3000:])
