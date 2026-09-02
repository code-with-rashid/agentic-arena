"""Baseline adapter: a hand-rolled agent loop using only the Python standard library.

This is the control in the experiment. Whatever a real framework does for `tool_use`,
this is the "just write the loop yourself" comparison point for lines of code,
latency overhead, and token overhead.

It also implements the optional suspend/resume contract
(`arena.types.ResumableRunner`) by **emulation**: there is no durable checkpoint
here, just a dict carrying the transcript back in. That is a real distinction from
a framework with native interrupts, and the feature matrix records it as emulated.
"""

from __future__ import annotations

from typing import Any

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

    def _client(self) -> ChatClient:
        return ChatClient(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            model=self.config.model,
            timeout_s=self.config.request_timeout_s,
        )

    def _loop(self, messages: list[dict], client: ChatClient) -> AgentResult:
        """Drive the tool loop until the model answers, pauses, or runs out of budget.

        Every leg reports only the calls *it* made; the harness concatenates legs,
        so accumulating across a resume here would double-count.
        """
        calls_made: list[dict] = []
        last_content = ""

        def _finish(**kw: Any) -> AgentResult:
            return AgentResult(
                tool_calls=calls_made,
                prompt_tokens=client.prompt_tokens,
                completion_tokens=client.completion_tokens,
                llm_calls=client.calls,
                **kw,
            )

        for _ in range(self.config.max_tool_iterations):
            resp = client.chat(messages, tools=self.tool_specs, tool_choice="auto")
            last_content = resp.content or last_content

            if not resp.tool_calls:
                return _finish(output_text=resp.content or "")

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
            for i, tc in enumerate(resp.tool_calls):
                if tc["name"] == tools.SUSPEND_TOOL:
                    # Do not execute it and do not log it as a tool call: asking
                    # for permission is the pause, not an action taken.
                    args = tc["arguments"]
                    summary = args.get("summary", "") if isinstance(args, dict) else str(args)
                    return _finish(
                        output_text=last_content,
                        suspended=True,
                        suspend_request=str(summary),
                        resume_state={
                            "messages": messages,
                            "approval_id": tc["id"],
                            # Siblings queued behind the pause still need a reply
                            # or the transcript is invalid on the next request.
                            "pending_ids": [t["id"] for t in resp.tool_calls[i + 1 :]],
                        },
                    )
                calls_made.append({"name": tc["name"], "arguments": tc["arguments"]})
                output = tools.dispatch(tc["name"], tc["arguments"])
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": output})

        return _finish(output_text=last_content, error="max tool iterations exceeded")

    def run(self, item: EvalItem) -> AgentResult:
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": item.input},
        ]
        return self._loop(messages, self._client())

    def resume(self, item: EvalItem, state: Any, decision: str) -> AgentResult:
        """Feed the human decision back in and carry on from the same transcript."""
        if not isinstance(state, dict) or "messages" not in state:
            return AgentResult(error=f"cannot resume: unusable state {type(state).__name__}")
        messages = list(state["messages"])
        messages.append(
            {
                "role": "tool",
                "tool_call_id": state["approval_id"],
                "content": f"Decision: {decision}.",
            }
        )
        for pending in state.get("pending_ids", []):
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": pending,
                    "content": "Not executed - the run paused for an approval decision.",
                }
            )
        return self._loop(messages, self._client())


class Adapter:
    name = "vanilla"

    @property
    def lib_version(self) -> str:
        import arena

        return f"stdlib (arena {arena.__version__})"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
