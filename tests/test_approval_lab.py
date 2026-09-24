from examples.harness.approval_lab import simulate


def test_denial_leaves_zero_effects_when_dispatch_is_gated():
    result = simulate(decision="deny", gated=True, crash="none")
    assert result["outcome"] == "denied safely"
    assert result["effects"] == 0


def test_advisory_pause_does_not_prevent_unauthorized_effect():
    result = simulate(decision="deny", gated=False, crash="none")
    assert result["outcome"] == "unauthorized effect"
    assert result["effects"] == 1


def test_durable_pause_resumes_in_a_fresh_process():
    result = simulate(decision="approve", gated=True, durable=True, crash="after_pause")
    assert result["outcome"] == "approved once"
    assert result["restarts"] == 1
    assert "restored" in [step["state"] for step in result["timeline"]]


def test_stable_operation_prevents_duplicate_after_effect_crash():
    result = simulate(crash="after_effect", stable_operation=True)
    assert result["outcome"] == "resumed without duplication"
    assert result["effects"] == 1


def test_new_operation_identity_duplicates_after_restart():
    result = simulate(crash="after_effect", stable_operation=False)
    assert result["outcome"] == "duplicate after restart"
    assert result["effects"] == 2
