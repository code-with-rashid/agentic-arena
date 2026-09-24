"""Build a framework-neutral, versioned harness design record."""

from __future__ import annotations

import argparse
import json

SCHEMA = "agentic-arena.harness-design/v1"


def build_design(
    *,
    workload: str = "coding",
    effect_risk: str = "reversible",
    restart: str = "resumable",
    approval: str = "risky",
    delegation: bool = False,
) -> dict:
    choices = {
        "workload": {"research", "coding", "operations"},
        "effect_risk": {"read_only", "reversible", "irreversible"},
        "restart": {"stateless", "resumable", "effect_safe"},
        "approval": {"none", "risky", "every_effect"},
    }
    values = {
        "workload": workload,
        "effect_risk": effect_risk,
        "restart": restart,
        "approval": approval,
    }
    for name, allowed in choices.items():
        if values[name] not in allowed:
            raise ValueError(f"{name} must be one of {', '.join(sorted(allowed))}")

    components = [
        _component("model_port", "Bounded requests and correlated action proposals"),
        _component("context_builder", "Select evidence without granting authority"),
        _component("scheduler", "Own task, call, action, and deadline budgets"),
        _component("tool_dispatcher", "Validate requests and return one result per call"),
        _component("executor", "Apply allowed operations in an explicit runtime"),
        _component("trace_and_eval", "Record events and check effects independently"),
    ]
    requirements = ["R1", "R2", "R4", "R7", "R8", "R10"]

    if restart != "stateless":
        components.append(_component("checkpoint_store", "Restore serializable run state"))
        requirements.extend(["R3", "R12"])
    if approval != "none" or effect_risk != "read_only":
        components.append(_component("policy_and_approval", "Bind authority to an exact operation"))
        requirements.extend(["R5", "R9"])
    if restart == "effect_safe" or effect_risk == "irreversible":
        components.append(
            _component("effect_journal", "Keep stable operation identity and reconcile ambiguity")
        )
        requirements.extend(["R6", "R13"])
    if delegation:
        components.append(
            _component("delegation_supervisor", "Own child budgets, provenance, and cancellation")
        )
        requirements.append("R11")
    if workload == "coding":
        components.append(
            _component(
                "workspace_boundary", "Scope repository reads, writes, commands, and cleanup"
            )
        )
        requirements.append("R14")

    experiments = [
        "Reject malformed and unknown tool calls without losing correlation.",
        "Fail visibly when required context cannot fit the request budget.",
        "Verify allowed and denied effects through an independent sink.",
    ]
    if restart != "stateless":
        experiments.append("Resume in a fresh process from serialized state.")
    if restart == "effect_safe" or effect_risk == "irreversible":
        experiments.append("Crash after effect commit and prove replay creates one effect.")
    if delegation:
        experiments.append("Cancel a parent during child work and account for the child outcome.")

    return {
        "schema": SCHEMA,
        "evidence_level": "design-guidance",
        "decisions": {**values, "delegation": delegation},
        "components": components,
        "requirements": sorted(set(requirements), key=lambda item: int(item[1:])),
        "acceptance_experiments": experiments,
        "boundary": "This record proposes contracts; it does not prove production behavior.",
    }


def render_markdown(record: dict) -> str:
    decisions = record["decisions"]
    lines = [
        "## Generated harness design",
        "",
        f"Schema: `{record['schema']}`",
        "",
        "### Decisions",
        "",
        *[f"- **{key.replace('_', ' ').title()}:** {value}" for key, value in decisions.items()],
        "",
        "### Components",
        "",
        *[f"- **{item['id']}:** {item['responsibility']}" for item in record["components"]],
        "",
        "### Acceptance experiments",
        "",
        *[f"- {item}" for item in record["acceptance_experiments"]],
        "",
        f"> {record['boundary']}",
    ]
    return "\n".join(lines)


def _component(identifier: str, responsibility: str) -> dict[str, str]:
    return {"id": identifier, "responsibility": responsibility}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workload", choices=("research", "coding", "operations"), default="coding"
    )
    parser.add_argument(
        "--effect-risk", choices=("read_only", "reversible", "irreversible"), default="reversible"
    )
    parser.add_argument(
        "--restart", choices=("stateless", "resumable", "effect_safe"), default="resumable"
    )
    parser.add_argument("--approval", choices=("none", "risky", "every_effect"), default="risky")
    parser.add_argument("--delegation", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    record = build_design(
        workload=args.workload,
        effect_risk=args.effect_risk,
        restart=args.restart,
        approval=args.approval,
        delegation=args.delegation,
    )
    print(render_markdown(record) if args.format == "markdown" else json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
