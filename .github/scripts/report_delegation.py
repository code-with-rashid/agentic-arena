"""Report what a three-role pipeline costs against its single-agent namesake.

The pipelines are expected to be *more* expensive — that is the measurement, not
a regression. Two things are gated, after `smolagents`' `resilience` count
drifted for iterations with nothing noticing:

  * no pairing collapses to zero cost (the run is broken, not the framework);
  * each pipeline's prompt ratio stays within `RATIO_TOLERANCE` of `EXPECTED`.
    `EXPECTED` mirrors what this script currently measures on a clean CI run;
    `docs/multi-agent.md` publishes the same ratios and lags a release bump of
    `openai-agents` / `smolagents` / `langgraph` — it is being corrected
    separately, and this gate is what stops the next drift going unseen.

The call multipliers (2x, 3x) are gated in `tests/test_delegation_depth.py` and
`tests/test_multi_agent_arena.py`; only the prompt ratios are new here.

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
    ("pydantic_ai", "pydantic_ai_multi", "model-decided, sub-agent as tool"),
]

# prompt-token ratio pipeline/single, from a clean CI run. Update this and
# docs/multi-agent.md together — a drift is a real change or a regression.
EXPECTED_RATIO = {
    "vanilla_multi": 2.50,
    "langgraph_multi": 2.50,
    "openai_agents_multi": 2.64,
    "smolagents_multi": 3.93,
    "pydantic_ai_multi": 3.57,
}
RATIO_TOLERANCE = 0.06

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
drifted: list[str] = []
for single, multi, kind in seen:
    if mean(single, "llm_calls") == 0:
        sys.exit(f"{single} reported zero LLM calls - the run is broken")
    ratio = mean(multi, "prompt_tokens") / mean(single, "prompt_tokens")
    note = ""
    if multi in EXPECTED_RATIO and abs(ratio - EXPECTED_RATIO[multi]) > RATIO_TOLERANCE:
        note = f"  <- expected {EXPECTED_RATIO[multi]:.2f}x"
        drifted.append(f"{multi}: prompt ratio {ratio:.2f}x, expected {EXPECTED_RATIO[multi]:.2f}x")
    print(
        f"  {single} -> {multi} ({kind}): "
        f"prompt {ratio:.2f}x{note}, "
        f"llm calls {mean(multi, 'llm_calls') / mean(single, 'llm_calls'):.2f}x"
    )

if drifted:
    sys.exit(
        "\ndelegation prompt ratio drifted from the published table:\n  "
        + "\n  ".join(drifted)
        + "\nIf intended, correct docs/multi-agent.md and EXPECTED_RATIO here together."
    )

if all(p in by_name for p in ("vanilla_multi", "langgraph_multi")):
    ratio = mean("langgraph_multi", "prompt_tokens") / mean("vanilla_multi", "prompt_tokens")
    print(f"\n  graph machinery alone (vanilla_multi -> langgraph_multi): prompt {ratio:.2f}x")
    print("  i.e. the cost of multi-agent is the structure, not the framework.")

print("\n  Cost only: the mock scripts identical turns, so every entry returns the")
print("  same brief. Mock mode cannot say whether delegation improves the answer.")
