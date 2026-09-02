"""Report what a three-role pipeline costs against its single-agent namesake.

Report-only. The pipelines are expected to be *more* expensive — that is the
measurement, not a regression. This fails only if a pairing is missing or an
entry collapsed to zero cost, which would mean the run is broken rather than the
framework being slow.

See docs/multi-agent.md for what the numbers mean, and in particular for why
"cheaper" here would be the wrong reading.
"""

import json
import pathlib
import sys

# (single-agent entry, pipeline entry) - the pipeline is the same library and the
# same role wording, differing only in being split across three agents. The two
# kinds of pipeline are marked because they are not the same experiment:
# structural delegation is a property of the wiring, model-decided delegation is
# a choice the model makes.
PAIRS = [
    ("vanilla", "vanilla_multi", "structural"),
    ("langgraph", "langgraph_multi", "structural"),
    ("openai_agents", "openai_agents_multi", "model-decided, speaker swap"),
    ("smolagents", "smolagents_multi", "model-decided, sub-agent as tool"),
]

runs = sorted(pathlib.Path("runs").glob("*__multi_agent__mock.json"))
if not runs:
    sys.exit("no multi_agent run found")

record = json.loads(runs[-1].read_text())
by_name = {fw["framework"]: fw for fw in record["frameworks"] if fw.get("available")}


def mean(name: str, field: str) -> float:
    items = by_name[name]["items"]
    return sum(item[field] for item in items) / len(items) if items else 0.0


print("\nmulti_agent - cost of delegation, mean per item, mock mode\n")
print(f"  {'entry':<18}{'prompt tok':>11}{'completion':>12}{'llm calls':>11}{'tool calls':>12}")
seen = []
for single, multi, kind in PAIRS:
    if single not in by_name or multi not in by_name:
        missing = [n for n in (single, multi) if n not in by_name]
        print(f"  (skipped {single} / {multi}: not in this run - {missing})")
        continue
    for name in (single, multi):
        print(
            f"  {name:<18}{mean(name, 'prompt_tokens'):>11.1f}"
            f"{mean(name, 'completion_tokens'):>12.1f}"
            f"{mean(name, 'llm_calls'):>11.2f}{len(by_name[name]['items'][0]['tool_calls']):>12}"
        )
    seen.append((single, multi, kind))

if not seen:
    sys.exit("no single/pipeline pairing present - cannot report delegation cost")

print()
for single, multi, kind in seen:
    if mean(single, "llm_calls") == 0:
        sys.exit(f"{single} reported zero LLM calls - the run is broken")
    print(
        f"  {single} -> {multi} ({kind}): "
        f"prompt {mean(multi, 'prompt_tokens') / mean(single, 'prompt_tokens'):.2f}x, "
        f"llm calls {mean(multi, 'llm_calls') / mean(single, 'llm_calls'):.2f}x"
    )

if all(p in by_name for p in ("vanilla_multi", "langgraph_multi")):
    ratio = mean("langgraph_multi", "prompt_tokens") / mean("vanilla_multi", "prompt_tokens")
    print(f"\n  graph machinery alone (vanilla_multi -> langgraph_multi): prompt {ratio:.2f}x")
    print("  i.e. the cost of multi-agent is the structure, not the framework.")

print("\n  Cost only: the mock scripts identical turns, so every entry returns the")
print("  same brief. Mock mode cannot say whether delegation improves the answer.")
