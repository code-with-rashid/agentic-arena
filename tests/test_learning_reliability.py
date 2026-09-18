import asyncio
import pytest
from examples.harness.reliability import Sink, bounded, cancellation_demo, demo, worker


def test_fresh_process_restart_does_not_repeat_effect():
    result = demo()
    assert result["actual_effects"] == 1
    assert result["restart"] == "replayed"
    assert result["cancellation_cleanup"]


def test_oracle_catches_duplicate_and_execution_before_approval(tmp_path):
    assert worker(tmp_path, approved=False) == "rejected"
    sink = Sink(tmp_path / "sink.sqlite")
    assert not sink.effects()
    # Deliberately broken client uses a fresh key after losing its acknowledgement.
    sink.execute("first", "booking")
    sink.execute("retry-with-new-key", "booking")
    assert len(sink.effects()) != 1  # The independent effect count catches duplication.
    assert len(sink.effects()) != 0  # It also catches execution after rejection.
    with pytest.raises(ValueError, match="different payload"):
        sink.execute("first", "different booking")


def test_timeout_retry_and_cancellation_are_bounded():
    async def check():
        calls = 0
        cleaned = 0

        async def slow():
            nonlocal calls, cleaned
            calls += 1
            try:
                await asyncio.Event().wait()
            finally:
                cleaned += 1

        with pytest.raises(TimeoutError):
            await bounded(slow, attempts=2, attempt_timeout=0.01, task_timeout=1)
        assert calls == cleaned == 2
        calls = cleaned = 0
        with pytest.raises(TimeoutError):
            await bounded(slow, attempts=100, attempt_timeout=1, task_timeout=0.02)
        assert calls == cleaned == 1
        assert await cancellation_demo()

    asyncio.run(check())
