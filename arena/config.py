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


def _dotenv(path: Path) -> dict[str, str]:
    """Read simple KEY=value settings without executing shell code.

    Only the project's settings are consumed. Values are literal (no variable
    expansion), with optional matching quotes and whitespace-separated comments.
    """
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, sep, value = line.partition("=")
        name = name.strip()
        if not sep or not (
            name.startswith("ARENA_") or name in {"OPENAI_API_KEY", "OPENAI_BASE_URL"}
        ):
            continue
        value = value.strip()
        if value.startswith(("'", '"')):
            end = value.find(value[0], 1)
            if end < 0 or (
                value[end + 1 :].strip() and not value[end + 1 :].lstrip().startswith("#")
            ):
                raise ValueError(f"invalid quoted value for {name} in .env")
            value = value[1:end]
        else:
            value = value.split(" #", 1)[0].rstrip()
        values[name] = value
    return values


@dataclass(frozen=True)
class ArenaConfig:
    mode: str = "mock"  # "mock" | "live" | "codex" (functional bridge)
    model: str = "gpt-4.1-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = "mock-key"
    price_input_per_m: float = 0.40
    price_output_per_m: float = 1.60
    repeat: int = 1
    request_timeout_s: float = 60.0
    max_tool_iterations: int = 6
    # Sampling temperature, held identical for every adapter in a run. `0.0` is
    # the invariant the comparison rests on (methodology.md 3e); it is a field
    # rather than a per-adapter constant so a determinism sweep is one knob, not
    # ten edits, and so `tests/test_shared_controls.py` can check it reaches the
    # wire.
    temperature: float = 0.0
    # Where an adapter may persist checkpoints for a `durable` arena. The harness
    # owns it, hands the same path to every framework, and clears it between runs,
    # so no adapter gets a private store the others do not have.
    checkpoint_dir: str = ""

    @classmethod
    def from_env(cls, *, mode: str | None = None, repeat: int | None = None) -> ArenaConfig:
        settings = _dotenv(REPO_ROOT / ".env")

        def _env(name: str, default: str = "") -> str:
            return os.environ.get(name, settings.get(name, default)).strip()

        resolved_mode = (mode or _env("ARENA_LLM_MODE", "mock")).lower()

        def _float(name: str, default: float) -> float:
            raw = _env(name)
            try:
                return float(raw) if raw else default
            except ValueError:
                return default

        return cls(
            mode=resolved_mode,
            # A copied .env commonly contains an API-only ARENA_MODEL. Keep the
            # subscription bridge on its own model knob so switching modes does
            # not accidentally ask Codex for an unavailable API model id.
            model=(
                _env("ARENA_CODEX_MODEL", "gpt-6-astra")
                if resolved_mode == "codex"
                else _env("ARENA_MODEL", "gpt-4.1-mini")
            ),
            base_url=_env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            api_key=_env("OPENAI_API_KEY", "mock-key") or "mock-key",
            price_input_per_m=_float("ARENA_PRICE_INPUT_PER_M", 0.40),
            price_output_per_m=_float("ARENA_PRICE_OUTPUT_PER_M", 1.60),
            repeat=repeat if repeat is not None else 1,
            request_timeout_s=_float(
                "ARENA_REQUEST_TIMEOUT_S", 180.0 if resolved_mode == "codex" else 60.0
            ),
            temperature=_float("ARENA_TEMPERATURE", 0.0),
        )

    def cost_usd(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens / 1_000_000 * self.price_input_per_m
            + completion_tokens / 1_000_000 * self.price_output_per_m
        )
