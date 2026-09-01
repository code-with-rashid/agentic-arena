"""Microsoft Agent Framework adapter for agentic-arena - STUB.

Filling this in is one of the most useful contributions available right now.
See CONTRIBUTING.md and .github/ISSUE_TEMPLATE/add-framework.md.

The finished adapter must:
  * build its agent using `config.model`, `config.base_url`, `config.api_key`
    (every one of these frameworks can target an OpenAI-compatible endpoint, which
    is what lets the mock server stand in for a real provider);
  * register `arena.tools.search` and `arena.tools.calculator` unchanged;
  * return an `arena.types.AgentResult` with `output_text`, `tool_calls`, tokens.
"""

from __future__ import annotations

from arena.config import ArenaConfig
from arena.types import ArenaSpec

_PKG = "agent-framework"


class Adapter:
    name = "microsoft_af"

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
            "microsoft_af adapter is a stub. See .github/ISSUE_TEMPLATE/add-framework.md "
            "for how to implement it."
        )
