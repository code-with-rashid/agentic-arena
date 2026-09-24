from examples.harness.design_lab import SCHEMA, build_design, render_markdown


def component_ids(record):
    return {component["id"] for component in record["components"]}


def test_basic_design_keeps_neutral_core_and_versioned_boundary():
    record = build_design(
        workload="research", effect_risk="read_only", restart="stateless", approval="none"
    )
    assert record["schema"] == SCHEMA
    assert record["evidence_level"] == "design-guidance"
    assert {
        "model_port",
        "context_builder",
        "scheduler",
        "tool_dispatcher",
        "trace_and_eval",
    } <= component_ids(record)
    assert "policy_and_approval" not in component_ids(record)


def test_irreversible_effect_safe_design_adds_authority_and_reconciliation():
    record = build_design(effect_risk="irreversible", restart="effect_safe", approval="risky")
    assert {"checkpoint_store", "policy_and_approval", "effect_journal"} <= component_ids(record)
    assert {"R5", "R6", "R13"} <= set(record["requirements"])
    assert any("one effect" in experiment for experiment in record["acceptance_experiments"])


def test_delegation_and_coding_add_their_owned_boundaries():
    record = build_design(workload="coding", delegation=True)
    assert {"delegation_supervisor", "workspace_boundary"} <= component_ids(record)


def test_markdown_export_carries_schema_decisions_and_limit():
    markdown = render_markdown(build_design())
    assert "agentic-arena.harness-design/v1" in markdown
    assert "Effect Risk" in markdown
    assert "does not prove production behavior" in markdown
