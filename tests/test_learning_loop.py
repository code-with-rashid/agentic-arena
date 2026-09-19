import pytest

from examples.harness.loop import ScriptedModel, run


def test_result_reaches_next_model_request():
    result = run(ScriptedModel(), "calculate")
    assert result.status == "completed"
    assert float(result.output) == 395
    assert result.messages[-1]["tool_call_id"] == "call-1"
    assert result.model_calls == 2


@pytest.mark.parametrize(
    "name,args", [("missing", "{}"), ("calculator", "{"), ("calculator", "[]")]
)
def test_invalid_calls_are_visible(name, args):
    class BadOnce(ScriptedModel):
        def complete(self, messages, tools):
            if messages[-1]["role"] == "tool":
                assert "ERROR" in messages[-1]["content"]
                return {"content": "request rejected", "calls": []}
            return {"calls": [{"id": "bad", "name": name, "arguments": args}]}

    assert run(BadOnce(), "task").output == "request rejected"


def test_repetition_terminates_without_fabricating_completion():
    class Forever:
        def complete(self, messages, tools):
            return {
                "calls": [
                    {"id": str(len(messages)), "name": "calculator", "arguments": '{"expr":"1"}'}
                ]
            }

    result = run(Forever(), "task", max_steps=3)
    assert result.status == "exhausted"
    assert result.model_calls == 3
    assert len(result.events) == 3
    assert run(Forever(), "task", max_actions=0).status == "action_budget"


def test_duplicate_ids_reject_batch_before_dispatch():
    class Duplicate:
        def complete(self, messages, tools):
            call = {"id": "x", "name": "calculator", "arguments": '{"expr":"1"}'}
            return {"calls": [call, call]}

    result = run(Duplicate(), "task")
    assert result.status == "model_error"
    assert result.events == []
