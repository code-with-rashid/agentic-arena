"""Hand-rolled three-role pipeline, stdlib only. The control for delegation cost.

`vanilla` is the control for "what does a framework buy you?". This is the control
for the question one level down: **what does a multi-agent structure cost that is
inherent to running three stages, and what does a framework's orchestration
machinery add on top?**

Same three roles as `langgraph_multi` — researcher, writer, editor — over one
shared transcript, in about forty lines of `while` loop and list appends:

    researcher (tool loop) -> writer -> editor

Comparing the four entries answers three separate questions on the same 10 items:

    vanilla        -> vanilla_multi       what three stages cost, framework-free
    langgraph      -> langgraph_multi     the same, inside a framework
    vanilla_multi  -> langgraph_multi     what the graph machinery itself adds

As with every mock-mode comparison, this measures the *cost* of the structure and
not its benefit: the scripted turns are identical for all four, so a pipeline
cannot produce a better brief here. See docs/multi-agent.md.

The iteration budget is per item, not per agent — three roles divide one
`max_tool_iterations` between them rather than getting one each.
"""

from __future__ import annotations

from arena import tools
from arena.config import ArenaConfig
from arena.llm.client import ChatClient
from arena.types import AgentResult, ArenaSpec, EvalItem

# Deliberately the same role wording as frameworks/langgraph_multi/adapter.py:
# the comparison between the two is about orchestration machinery, so the prompts
# must not be a second variable.
ROLES = {
    "researcher": (
        "You are the researcher on this pipeline. Use the `search` tool to gather "
        "the facts the brief needs. Do not write the brief yourself."
    ),
    "writer": (
        "You are the writer on this pipeline. Using only the facts already "
        "gathered above, write the brief. Reply with the brief and nothing else."
    ),
    "editor": (
        "You are the editor on this pipeline. Check the draft above against the "
        "task and reply with the final brief, revised if needed and unchanged if "
        "not. Reply with the brief and nothing else."
    ),
}


class _Runner:
    def __init__(self, arena: ArenaSpec, config: ArenaConfig) -> None:
        self.config = config
        # Task instruction comes from the arena, not from this file.
        self.system_prompt = arena.system_prompt
        self.tool_specs = tools.specs_for(arena.tools)

    def _prompt_for(self, role: str) -> dict:
        return {"role": "system", "content": f"{self.system_prompt}\n\n{ROLES[role]}"}

    def run(self, item: EvalItem) -> AgentResult:
        client = ChatClient(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            model=self.config.model,
            timeout_s=self.config.request_timeout_s,
        )
        # One shared transcript, exactly like the graph's shared MessagesState.
        # The system message is swapped per stage rather than accumulated, so each
        # stage sees the same conversation under a different instruction.
        history: list[dict] = [{"role": "user", "content": item.input}]
        calls_made: list[dict] = []
        last_content = ""
        budget = self.config.max_tool_iterations

        def spent() -> int:
            return client.calls

        # Stage 1: the researcher, which is the only stage with tools.
        while spent() < budget:
            resp = client.chat(
                [self._prompt_for("researcher")] + history,
                tools=self.tool_specs,
                tool_choice="auto",
            )
            last_content = resp.content or last_content
            if not resp.tool_calls:
                break
            history.append(
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
                history.append({"role": "tool", "tool_call_id": tc["id"], "content": output})
        else:
            return AgentResult(
                output_text=last_content,
                tool_calls=calls_made,
                prompt_tokens=client.prompt_tokens,
                completion_tokens=client.completion_tokens,
                llm_calls=client.calls,
                error="max tool iterations exceeded",
            )

        if last_content:
            history.append({"role": "assistant", "content": last_content})

        # Stages 2 and 3: writer then editor. Neither gets tools - the division of
        # labour is the point, and handing them tools would make this three
        # researchers rather than a pipeline.
        for role in ("writer", "editor"):
            if spent() >= budget:
                break
            resp = client.chat([self._prompt_for(role)] + history, tools=None)
            if resp.content:
                last_content = resp.content
                history.append({"role": "assistant", "content": resp.content})

        return AgentResult(
            output_text=last_content,
            tool_calls=calls_made,
            prompt_tokens=client.prompt_tokens,
            completion_tokens=client.completion_tokens,
            llm_calls=client.calls,
        )


class Adapter:
    name = "vanilla_multi"
    # A contrast entry, not a general-purpose adapter: `--framework all` runs it
    # only on the arena it was built to contrast on. Naming it explicitly still
    # works anywhere. See arena.registry.frameworks_for_arena.
    arenas = ("multi_agent",)

    @property
    def lib_version(self) -> str:
        import arena

        return f"stdlib (arena {arena.__version__}, 3-role pipeline)"

    def build(self, arena: ArenaSpec, config: ArenaConfig) -> _Runner:
        return _Runner(arena, config)
