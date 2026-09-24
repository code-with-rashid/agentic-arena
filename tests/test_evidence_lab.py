from examples.harness.evidence_lab import SCHEMA, build_record, compare_records


def test_mock_record_cannot_support_real_model_claim():
    record = build_record(claim="real_model", mode="mock")
    assert record["schema"] == SCHEMA
    assert record["evidence"]["supports_claim"] is False
    assert "not model capability" in record["evidence"]["limitation"]


def test_codex_is_functional_evidence_but_not_provider_benchmark():
    functional = build_record(claim="real_model", mode="codex", model="subscription-model")
    benchmark = build_record(claim="provider_comparison", mode="codex", model="subscription-model")
    assert functional["evidence"]["supports_claim"] is True
    assert benchmark["evidence"]["supports_claim"] is False


def test_comparison_rejects_different_modes_and_scorers():
    left = build_record(claim="recovery", mode="offline-fixture", scorer="effects/v1")
    right = build_record(claim="recovery", mode="live", scorer="answer/v1")
    comparison = compare_records(left, right)
    assert comparison["comparable"] is False
    assert comparison["blocking_differences"] == ["mode", "scorer"]


def test_native_records_are_comparable_only_under_shared_model_and_contract():
    left = build_record(claim="provider_comparison", mode="live", model="model-a", repetitions=5)
    right = build_record(claim="provider_comparison", mode="live", model="model-a", repetitions=5)
    assert compare_records(left, right)["comparable"] is True
    right["provenance"]["model"] = "model-b"
    assert compare_records(left, right)["blocking_differences"] == ["model"]


def test_observations_and_design_guidance_stay_separate():
    record = build_record(claim="wiring", mode="mock", observations=("tool result correlated",))
    assert record["observations"] == ["tool result correlated"]
    assert record["design_guidance"] == []
