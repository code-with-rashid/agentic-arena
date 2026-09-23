import pytest

from examples.harness.failure_lab import simulate


def test_stable_operation_key_prevents_duplicate_after_lost_acknowledgement():
    result = simulate("timeout_after_effect", retries=1, stable_key=True, reconcile=True)
    assert result["outcome"] == "recovered without duplication"
    assert result["attempts"] == 2
    assert result["effects"] == 1
    assert [step["state"] for step in result["timeline"]][-2:] == ["replayed", "verified"]


def test_new_key_turns_retry_into_a_second_effect():
    result = simulate("timeout_after_effect", retries=1, stable_key=False, reconcile=False)
    assert result["outcome"] == "silent duplicate"
    assert result["effects"] == 2


@pytest.mark.parametrize("failure", ["malformed_arguments", "unknown_tool"])
def test_model_fault_is_returned_for_correction(failure):
    result = simulate(failure)
    assert result["outcome"] == "recovered"
    assert "rejected" in [step["state"] for step in result["timeline"]]


def test_non_retryable_request_stops_even_with_retry_budget():
    result = simulate("bad_request", retries=3)
    assert result["outcome"] == "failed safely"
    assert result["attempts"] == 1


def test_invalid_policy_is_rejected():
    with pytest.raises(ValueError, match="between 0 and 3"):
        simulate("rate_limit", retries=4)
