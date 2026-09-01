"""Command-line entry point: `python -m arena ...` (also installed as `arena`)."""

from __future__ import annotations

import argparse
import sys

from .config import ArenaConfig
from .registry import available_arenas, available_frameworks
from .runner import run as run_arena
from .scorecard import latest_run, write_scorecard


def _cmd_list(_args: argparse.Namespace) -> int:
    print("Arenas:")
    for name in available_arenas():
        print(f"  - {name}")
    print("\nFramework adapters:")
    for name in available_frameworks():
        print(f"  - {name}")
    return 0


def _resolve_frameworks(values: list[str]) -> list[str]:
    if not values or "all" in values:
        return available_frameworks()
    unknown = sorted(set(values) - set(available_frameworks()))
    if unknown:
        raise SystemExit(f"unknown framework(s): {', '.join(unknown)}")
    return values


def _cmd_run(args: argparse.Namespace) -> int:
    frameworks = _resolve_frameworks(args.framework)
    config = ArenaConfig.from_env(mode=args.mode, repeat=args.repeat)
    if config.mode == "live" and config.api_key in ("", "mock-key"):
        print(
            "refusing live run: set OPENAI_API_KEY (and OPENAI_BASE_URL / ARENA_MODEL)",
            file=sys.stderr,
        )
        return 2

    print(f"arena={args.arena} mode={config.mode} model={config.model} repeat={config.repeat}")
    print(f"frameworks: {', '.join(frameworks)}")
    record = run_arena(args.arena, frameworks, config=config)

    for fw in record["frameworks"]:
        if not fw.get("available"):
            print(f"  {fw['framework']:<20} unavailable - {fw.get('reason')}")
            continue
        items = fw["items"]
        passed = sum(1 for it in items if it["passed"])
        print(f"  {fw['framework']:<20} {passed}/{len(items)} passed")

    if not args.no_scorecard:
        path = write_scorecard(record)
        print(f"\nscorecard: {path}")
    print(f"raw run:   {record['_path']}")
    return 0


def _cmd_scorecard(args: argparse.Namespace) -> int:
    record = latest_run(args.arena, mode=args.mode)
    path = write_scorecard(record)
    print(f"scorecard: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arena", description="agentic-arena harness")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list arenas and framework adapters")
    p_list.set_defaults(func=_cmd_list)

    p_run = sub.add_parser("run", help="run one arena against one or more adapters")
    p_run.add_argument("--arena", required=True)
    p_run.add_argument(
        "--framework", action="append", default=[], help="repeatable; 'all' for every adapter"
    )
    p_run.add_argument("--mode", choices=["mock", "live"], default=None)
    p_run.add_argument("--repeat", type=int, default=1)
    p_run.add_argument("--no-scorecard", action="store_true")
    p_run.set_defaults(func=_cmd_run)

    p_sc = sub.add_parser("scorecard", help="regenerate a scorecard from the latest run")
    p_sc.add_argument("--arena", required=True)
    p_sc.add_argument("--mode", choices=["mock", "live"], default=None)
    p_sc.set_defaults(func=_cmd_scorecard)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
