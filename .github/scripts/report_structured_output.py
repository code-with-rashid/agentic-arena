"""Report what each framework does with a record that violates the schema.

The `structured_output` arena grades the answer correctly. What it never
exercises is any *framework's* structured-output machinery, because the mock
always replays a valid record. This scripts four ways to violate the schema and
prints what comes back, alongside whether the adapter asked the provider to
constrain the output in the first place.

Report-only, like report_overhead.py and report_transport.py. It fails only if
the scorer stops rejecting a violation, which would mean the arena's whole result
is meaningless rather than a framework being unusual.

    python .github/scripts/report_structured_output.py
"""

import sys
from dataclasses import replace

sys.path.insert(0, ".")

from arena.config import ArenaConfig  # noqa: E402
from arena.llm.mockserver import MockScript, MockServer  # noqa: E402
from arena.registry import available_frameworks, load_arena, load_framework  # noqa: E402
from arena.scorer import score_item  # noqa: E402
from arena.types import AgentResult, EvalItem  # noqa: E402

STUBS = {"claude_agent_sdk"}
ARENA = load_arena("structured_output")
ITEM = EvalItem(id="so-01", input="Eiffel Tower", checks=[])

VALID = '{"name": "Eiffel Tower", "year": 1889, "height_m": 330, "sources": ["Eiffel Tower"]}'
PLANS = {
    "valid": VALID,
    "not json": "The Eiffel Tower was completed in 1889 and is 330 m tall.",
    "wrong types": '{"name": "Eiffel Tower", "year": "eighteen eighty-nine", '
    '"height_m": "330 m", "sources": "Eiffel Tower"}',
    "missing field": '{"name": "Eiffel Tower", "year": 1889}',
    "extra field": '{"name": "Eiffel Tower", "year": 1889, "height_m": 330, '
    '"sources": ["Eiffel Tower"], "confidence": "high"}',
    "fenced": f"```json\n{VALID}\n```",
}


def script(final):
    return MockScript(
        {
            "default": {
                "turns": [
                    {"tool_calls": [{"name": "search", "arguments": {"query": "Eiffel Tower"}}]},
                    *[{"content": final}] * 4,
                ]
            }
        }
    )


def run(name, final):
    with MockServer(script(final), arena_tools=list(ARENA.tools)) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=6,
        )
        try:
            result = load_framework(name).build(ARENA, config).run(ITEM)
            text = (result.output_text or "").strip()
            outcome = "unchanged" if text == final.strip() else "ALTERED"
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            text, outcome = "", f"raised {type(exc).__name__}"
        asked = any(r.get("response_format") for r in server.requests)
        return outcome, len(server.requests), asked


def scored(text):
    result = AgentResult(
        output_text=text,
        tool_calls=[{"name": "search", "arguments": {"query": "Eiffel Tower"}}],
        prompt_tokens=1,
        completion_tokens=1,
        llm_calls=2,
    )
    return score_item(ARENA.dataset[0], result).passed


def buildable():
    out = []
    for name in available_frameworks():
        if name in STUBS or name.endswith("_multi"):
            continue
        try:
            config = replace(ArenaConfig(mode="mock"), base_url="http://127.0.0.1:1", api_key="k")
            load_framework(name).build(ARENA, config)
        except Exception:  # noqa: BLE001 - not installed here
            continue
        out.append(name)
    return out


names = sorted(buildable())
labels = list(PLANS)

print("\nstructured output - what each framework does with a record it was handed\n")
print(f"  {'framework':16}  {'asks provider?':14}" + "".join(f"  {label:<14}" for label in labels))
for name in names:
    cells, asked_any = [], False
    for label in labels:
        outcome, calls, asked = run(name, PLANS[label])
        asked_any = asked_any or asked
        cells.append(f"{outcome} ({calls})")
    flag = "response_format" if asked_any else "no - prompt only"
    print(f"  {name:16}  {flag:14}" + "".join(f"  {c:<14}" for c in cells))

print("\n  'unchanged' means the framework returned the model's text byte-for-byte.")
print("  Bracketed number is LLM calls - a framework that re-prompted would spend more.")
print("  Differences are findings - see docs/structured-output.md.\n")

print("  and what the SCORER makes of the same six records:\n")
for label in labels:
    print(f"    {label:16} {'PASS' if scored(PLANS[label]) else 'fail'}")

# Not a finding: the scorer is the only thing checking these records, because no
# framework does. If it stops rejecting a violation, every run goes green.
bad = [label for label in ("not json", "wrong types", "missing field") if scored(PLANS[label])]
if bad:
    sys.exit(f"\nSCORER BROKEN: accepted {bad} - every structured_output run would pass")
print("\n  scorer check: schema violations still fail. ok")
