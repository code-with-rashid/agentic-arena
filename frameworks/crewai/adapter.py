"""CrewAI adapter for agentic-arena.

A single-agent "crew" with the shared search / calculator tools. CrewAI routes LLM
calls through LiteLLM, so the shared gateway is configured as an OpenAI-compatible
provider (`openai/<model>` + base_url + api_key).
"""

from __future__ import annotations

import os
from typing import Any

# Keep CrewAI non-interactive and quiet in CI: no telemetry, no "view execution
# traces? [y/N]" prompt, no OTEL exporter noise. Set before crewai is imported.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CI", "true")

from arena.config import ArenaConfig  # noqa: E402
from arena.tools import calculator as _calculator  # noqa: E402
from arena.tools import names_for as _tool_names  # noqa: E402
from arena.tools import search as _search  # noqa: E402
from arena.types import AgentResult, ArenaSpec, EvalItem  # noqa: E402


def _make_tools(sink: list[dict[str, Any]], names: list[str]) -> list[Any]:
    from crewai.tools import BaseTool

    class SearchTool(BaseTool):
        name: str = "search"
        description: str = (
            "Search a small knowledge base of general facts. Args: query (str), k (int)."
        )

        def _run(self, query: str, k: int = 3) -> str:
            sink.append({"name": "search", "arguments": {"query": query, "k": k}})
            return _search(query, k)

    class CalculatorTool(BaseTool):
        name: str = "calculator"
        description: str = "Evaluate a basic arithmetic expression. Args: expr (str)."

        def _run(self, expr: str) -> str:
            sink.append({"name": "calculator", "arguments": {"expr": expr}})
            return _calculator(expr)

    available = {"search": SearchTool, "calculator": CalculatorTool}
    return [available[name]() for name in names if name in available]


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        from crewai import LLM

        self.config = config
        # Task instruction comes from the arena spec, not from this file.
        self.system_prompt = arena.system_prompt
        self.tool_names = _tool_names(arena.tools)
        self.llm = LLM(
            model=f"openai/{config.model}",
            base_url=config.base_url,
            api_key=config.api_key,
            temperature=config.temperature,
        )

    def run(self, item: EvalItem) -> AgentResult:
        from crewai import Agent, Crew, Process, Task

        calls: list[dict[str, Any]] = []
        tools = _make_tools(calls, self.tool_names)

        agent = Agent(
            role="Research assistant",
            goal="Answer the user's question accurately and concisely.",
            backstory=self.system_prompt,
            tools=tools,
            llm=self.llm,
            verbose=False,
            allow_delegation=False,
            max_iter=self.config.max_tool_iterations,
        )
        task = Task(
            description=item.input,
            expected_output="A concise answer containing the key number or fact.",
            agent=agent,
        )
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        output = crew.kickoff()

        prompt_tokens = completion_tokens = 0
        usage = getattr(crew, "usage_metrics", None)
        if usage is not None:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

        return AgentResult(
            output_text=str(output),
            tool_calls=calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            llm_calls=int(getattr(usage, "successful_requests", 0) or 0) if usage else 0,
        )


class Adapter:
    name = "crewai"

    @property
    def lib_version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return f"crewai {version('crewai')}"
        except PackageNotFoundError:
            return "crewai (not installed)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
