"""Runtime configuration shared by every adapter.

The whole point of the harness is that this object is identical for every framework
in a given run. Adapters read `model`, `base_url`, and `api_key` from here and must
not substitute their own.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class ArenaConfig:
    mode: str = "mock"  # "mock" | "live"
    model: str = "gpt-4.1-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = "mock-key"
    price_input_per_m: float = 0.40
    price_output_per_m: float = 1.60
    repeat: int = 1
    request_timeout_s: float = 60.0
    max_tool_iterations: int = 6
    # Where an adapter may persist checkpoints for a `durable` arena. The harness
    # owns it, hands the same path to every framework, and clears it between runs,
    # so no adapter gets a private store the others do not have.
    checkpoint_dir: str = ""

    @classmethod
    def from_env(cls, *, mode: str | None = None, repeat: int | None = None) -> ArenaConfig:
        resolved_mode = (mode or _env("ARENA_LLM_MODE", "mock")).lower()

        def _float(name: str, default: float) -> float:
            raw = _env(name)
            try:
                return float(raw) if raw else default
            except ValueError:
                return default

        return cls(
            mode=resolved_mode,
            model=_env("ARENA_MODEL", "gpt-4.1-mini"),
            base_url=_env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            api_key=_env("OPENAI_API_KEY", "mock-key") or "mock-key",
            price_input_per_m=_float("ARENA_PRICE_INPUT_PER_M", 0.40),
            price_output_per_m=_float("ARENA_PRICE_OUTPUT_PER_M", 1.60),
            repeat=repeat if repeat is not None else 1,
            request_timeout_s=_float("ARENA_REQUEST_TIMEOUT_S", 60.0),
        )

    def cost_usd(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens / 1_000_000 * self.price_input_per_m
            + completion_tokens / 1_000_000 * self.price_output_per_m
        )
