"""Discovery and loading of arenas (data) and framework adapters (code)."""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib

from .config import REPO_ROOT
from .types import ArenaSpec, EvalItem, Framework

ARENAS_DIR = REPO_ROOT / "arenas"
FRAMEWORKS_DIR = REPO_ROOT / "frameworks"


def available_arenas() -> list[str]:
    return sorted(p.name for p in ARENAS_DIR.iterdir() if (p / "arena.toml").exists())


def available_frameworks() -> list[str]:
    return sorted(p.name for p in FRAMEWORKS_DIR.iterdir() if (p / "adapter.py").exists())


def load_arena(arena_id: str) -> ArenaSpec:
    base = ARENAS_DIR / arena_id
    spec_path = base / "arena.toml"
    if not spec_path.exists():
        raise FileNotFoundError(f"no arena {arena_id!r} (looked in {spec_path})")
    meta = tomllib.loads(spec_path.read_text(encoding="utf-8"))

    dataset: list[EvalItem] = []
    ds_path = base / "dataset.jsonl"
    for line in ds_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            dataset.append(EvalItem.from_json(json.loads(line)))

    return ArenaSpec(
        id=meta["id"],
        description=meta.get("description", ""),
        tools=list(meta.get("tools", [])),
        system_prompt_intent=meta.get("system_prompt_intent", ""),
        dataset=dataset,
        mock_script_path=str(base / "mock_script.json"),
        durable=bool(meta.get("durable", False)),
    )


def load_framework(name: str) -> Framework:
    adapter_path = FRAMEWORKS_DIR / name / "adapter.py"
    if not adapter_path.exists():
        raise FileNotFoundError(f"no framework adapter {name!r} (looked in {adapter_path})")

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    mod_name = f"_arena_adapter_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, adapter_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {adapter_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, "Adapter"):
        raise AttributeError(f"{adapter_path} must define a class named `Adapter`")
    return module.Adapter()  # type: ignore[no-any-return]
