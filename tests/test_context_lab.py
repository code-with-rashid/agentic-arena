import pytest

from examples.harness.context_lab import simulate


def test_protected_policy_retains_obligations_and_reports_omissions():
    result = simulate("protected", budget_chars=220)
    assert result["outcome"] == "bounded context"
    assert result["missing_required"] == []
    assert {"approval", "database-correction"} <= set(result["selected"])
    assert result["omitted"]


def test_recent_window_can_lose_early_approval():
    result = simulate("recent", budget_chars=170)
    assert result["outcome"] == "obligation lost"
    assert "approval" in result["missing_required"]


def test_full_history_exposes_budget_overflow_instead_of_claiming_fit():
    result = simulate("full", budget_chars=100)
    assert result["outcome"] == "budget exceeded"
    assert result["used_chars"] > result["budget_chars"]


def test_summary_labels_provenance_loss():
    result = simulate("summary", budget_chars=220)
    assert result["outcome"] == "compacted with provenance loss"
    assert "summary" in result["selected"]


def test_required_evidence_that_cannot_fit_fails_visibly():
    result = simulate("protected", budget_chars=40)
    assert result["outcome"] == "failed visibly"
    assert not result["selected"]


def test_invalid_policy_is_rejected():
    with pytest.raises(ValueError, match="unknown policy"):
        simulate("magic")
