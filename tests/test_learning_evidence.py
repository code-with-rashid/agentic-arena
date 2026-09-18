from copy import deepcopy
from arena.evidence import audit
from examples.harness.evaluate import compare


def test_two_designs_same_fixture_independent_oracle():
    report = compare()
    good, broken = report["results"]
    assert good["correctness"]
    assert not broken["correctness"]
    assert all(all(row["audit"].values()) for row in report["results"])
    assert report["provenance"]["mode"] == "offline-fixture"
    assert len(report["provenance"]["identities"]) == 3


def test_missing_event_and_false_effect_report_detected():
    good = compare()["results"][0]
    missing = good["events"][1:]
    assert not audit(missing, good["actual_effects"], ["0", "1"])["trace_complete"]
    misleading = deepcopy(good["events"])
    next(e for e in misleading if e["kind"] == "effect")["value"] = "invented"
    assert not audit(misleading, good["actual_effects"], ["0", "1"])["effects_match"]
