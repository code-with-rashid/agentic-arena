"""Core data types and the adapter contract.

An adapter implements `Framework`. `Framework.build(...)` returns an `AgentRunner`
whose `.run(item)` produces an `AgentResult` for a single eval item.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class EvalItem:
    id: str
    input: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""

    @classmethod
    def from_json(cls, obj: dict[str, Any]) -> EvalItem:
        return cls(
            id=str(obj["id"]),
            input=str(obj["input"]),
            checks=list(obj.get("checks", [])),
            note=str(obj.get("note", "")),
        )


@dataclass
class ArenaSpec:
    id: str
    description: str
    tools: list[str]
    system_prompt_intent: str
    dataset: list[EvalItem]
    mock_script_path: str

    @property
    def tool_use_allowed(self) -> bool:
        return bool(self.tools)


@dataclass
class AgentResult:
    output_text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    llm_calls: int = 0
    error: str | None = None
    raw: dict[str, Any] | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ItemOutcome:
    item_id: str
    passed: bool
    checks: list[dict[str, Any]]
    result: AgentResult


@runtime_checkable
class AgentRunner(Protocol):
    def run(self, item: EvalItem) -> AgentResult: ...


@runtime_checkable
class Framework(Protocol):
    name: str

    @property
    def lib_version(self) -> str: ...

    def build(self, arena: ArenaSpec, config: Any) -> AgentRunner: ...
