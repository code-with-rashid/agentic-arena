"""A bounded, observable tool loop. Run: python -m examples.harness.loop."""

from __future__ import annotations

import argparse
import copy
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from arena.config import ArenaConfig
from arena.llm.client import ChatClient
from arena.tools import dispatch, specs_for


class Model(Protocol):
    def complete(self, messages: list[dict], tools: list[dict]) -> dict: ...


class ScriptedModel:
    """Fixture verifies the model actually receives its previous tool result."""

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        if messages[-1]["role"] == "tool":
            return {"content": messages[-1]["content"], "calls": []}
        return {
            "content": None,
            "calls": [{"id": "call-1", "name": "calculator", "arguments": '{"expr":"17*23+4"}'}],
        }


class NativeModel:
    """Optional native gateway; credentials and limits come from ArenaConfig."""

    def __init__(self, config: ArenaConfig):
        self.client = ChatClient(
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            timeout_s=config.request_timeout_s,
            temperature=config.temperature,
        )

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        response = self.client.chat(messages, tools=tools, tool_choice="auto")
        return {"content": response.content, "calls": response.tool_calls}


@dataclass
class LoopResult:
    status: str
    output: str = ""
    messages: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    model_calls: int = 0


def run(model: Model, task: str, *, max_steps: int = 4, max_actions: int = 8) -> LoopResult:
    if max_steps < 1 or max_actions < 0:
        raise ValueError("budgets must permit at least one model call and nonnegative actions")
    result = LoopResult("exhausted", messages=[{"role": "user", "content": task}])
    schemas = specs_for(["calculator"])
    seen: set[str] = set()
    for _ in range(max_steps):
        result.model_calls += 1
        try:
            reply = model.complete(copy.deepcopy(result.messages), copy.deepcopy(schemas))
            calls = reply.get("calls", [])
            if not isinstance(calls, list):
                raise ValueError("calls must be a list")
            # Validate the batch before any effects. IDs correlate replies, not retries.
            ids = [c["id"] for c in calls]
            if any(not isinstance(i, str) or not i or i in seen for i in ids):
                raise ValueError("call IDs must be fresh nonempty strings")
            if len(set(ids)) != len(ids):
                raise ValueError("duplicate call ID")
            if any(not isinstance(c.get("name"), str) for c in calls):
                raise ValueError("call name must be a string")
        except Exception as exc:
            result.status = "model_error"
            result.output = type(exc).__name__  # Never dump provider credentials/exception bodies.
            return result
        if not calls:
            content = reply.get("content")
            result.status = (
                "completed" if isinstance(content, str) and content.strip() else "invalid"
            )
            result.output = content if isinstance(content, str) else ""
            return result
        if len(result.events) + len(calls) > max_actions:
            result.status = "action_budget"
            return result
        seen.update(ids)
        result.messages.append(
            {
                "role": "assistant",
                "content": reply.get("content"),
                "tool_calls": [
                    {
                        "id": c["id"],
                        "type": "function",
                        "function": {"name": c["name"], "arguments": c.get("arguments", "{}")},
                    }
                    for c in calls
                ],
            }
        )
        for c in calls:
            args: Any = c.get("arguments", "{}")
            try:
                args = json.loads(args) if isinstance(args, str) else args
                if c["name"] != "calculator":
                    raise ValueError("unknown tool")
                if (
                    not isinstance(args, dict)
                    or set(args) != {"expr"}
                    or not isinstance(args["expr"], str)
                ):
                    raise ValueError("expected exactly one string expr")
                output = dispatch(c["name"], args)
            except (ValueError, TypeError):
                output = "ERROR: invalid or unknown tool request"
            result.events.append({"call_id": c["id"], "tool": c["name"], "result": output})
            result.messages.append({"role": "tool", "tool_call_id": c["id"], "content": output})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="explicitly use a configured paid/native provider"
    )
    args = parser.parse_args()
    model: Model = NativeModel(ArenaConfig.from_env()) if args.live else ScriptedModel()
    result = run(model, "What is 17*23+4? Use the calculator.")
    print(json.dumps(asdict(result), indent=2))
    if result.status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
