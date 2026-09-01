"""Baseline adapter: a hand-rolled agent loop using only the Python standard library.

This is the control in the experiment. Whatever a real framework does for `tool_use`,
this is the "just write the loop yourself" comparison point for lines of code,
latency overhead, and token overhead.
"""

from __future__ import annotations

from arena import tools
from arena.config import ArenaConfig
from arena.llm.client import ChatClient
from arena.types import AgentResult, ArenaSpec, EvalItem


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        self.config = config
        # Task instruction comes from the arena, not from this file — otherwise
        # the baseline sends a tool_use prompt when run on any other arena.
        self.system_prompt = arena.system_prompt
        self.tool_specs = tools.specs_for(arena.tools)

    def run(self, item: EvalItem) -> AgentResult:
        client = ChatClient(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            model=self.config.model,
            timeout_s=self.config.request_timeout_s,
        )
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": item.input},
        ]
        calls_made: list[dict] = []

        last_content = ""
        for _ in range(self.config.max_tool_iterations):
            resp = client.chat(messages, tools=self.tool_specs, tool_choice="auto")
            last_content = resp.content or last_content

            if not resp.tool_calls:
                return AgentResult(
                    output_text=resp.content or "",
                    tool_calls=calls_made,
                    prompt_tokens=client.prompt_tokens,
                    completion_tokens=client.completion_tokens,
                    llm_calls=client.calls,
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": resp.content or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in resp.tool_calls
                    ],
                }
            )
            for tc in resp.tool_calls:
                calls_made.append({"name": tc["name"], "arguments": tc["arguments"]})
                output = tools.dispatch(tc["name"], tc["arguments"])
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": output})

        return AgentResult(
            output_text=last_content,
            tool_calls=calls_made,
            error="max tool iterations exceeded",
            prompt_tokens=client.prompt_tokens,
            completion_tokens=client.completion_tokens,
            llm_calls=client.calls,
        )


class Adapter:
    name = "vanilla"

    @property
    def lib_version(self) -> str:
        import arena

        return f"stdlib (arena {arena.__version__})"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
