import json
import subprocess
import sys

import pytest

from examples.harness.context import Fact, Memory, build_context


def test_required_early_evidence_survives_recent_noise():
    facts = [Fact("approval", "Ask first", True), Fact("noise", "x" * 100), Fact("recent", "new")]
    result = build_context(facts, 40)
    assert result["sources"] == ["approval", "recent"]
    assert result["omitted"] == ["noise"]
    assert len(result["text"]) <= 40
    with pytest.raises(ValueError, match="required"):
        build_context(facts, 2)


def test_session_and_tenant_are_both_required(tmp_path):
    memory = Memory(tmp_path / "memory.sqlite")
    memory.put("a", "one", Fact("source", "needle allowed"))
    memory.put("a", "two", Fact("source", "needle other session"))
    memory.put("b", "one", Fact("source", "needle other tenant"))
    assert memory.retrieve("a", "one", "needle") == [Fact("source", "needle allowed")]
    assert memory.retrieve("missing", "one", "") == []


def test_memory_survives_fresh_interpreter(tmp_path):
    path = tmp_path / "memory.sqlite"
    Memory(path).put("a", "one", Fact("evidence-1", "retained"))
    code = "from pathlib import Path; import sys,json; from examples.harness.context import Memory; print(json.dumps([f.source_id for f in Memory(Path(sys.argv[1])).retrieve('a','one','retained')]))"
    result = subprocess.run(
        [sys.executable, "-c", code, str(path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert json.loads(result.stdout) == ["evidence-1"]
