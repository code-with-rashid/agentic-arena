"""Claude Agent SDK adapter for agentic-arena - STUB (deliberately).

`claude-agent-sdk` installs on 3.14 but does not fit the shared-gateway design:
it drives the `claude` CLI (Node) as a subprocess and speaks the Anthropic
Messages API, not one OpenAI-compatible `/chat/completions` endpoint, so it can't
run against the mock server. See README.md in this directory for the blocker and
the three ways a contributor could close it.
"""

from __future__ import annotations

from arena.config import ArenaConfig
from arena.types import ArenaSpec

_PKG = "claude-agent-sdk"


class Adapter:
    name = "claude_agent_sdk"

    @property
    def lib_version(self) -> str:
        try:
            from importlib.metadata import PackageNotFoundError, version

            try:
                return f"{_PKG} {version(_PKG)}"
            except PackageNotFoundError:
                return f"{_PKG} (not installed)"
        except Exception:  # noqa: BLE001
            return f"{_PKG} (unknown)"

    def build(self, arena: ArenaSpec, config: ArenaConfig):
        raise NotImplementedError(
            "claude_agent_sdk does not fit the shared OpenAI-compatible gateway "
            "(CLI subprocess + Anthropic Messages API). See "
            "frameworks/claude_agent_sdk/README.md."
        )
