"""Shared tools handed to every adapter.

`OPENAI_TOOL_SPECS` is the JSON-schema tool list in OpenAI "tools" format; adapters
that speak that format can pass it straight through. `dispatch` executes a tool call
by name and is what the vanilla loop (and the mock server's expectations) rely on.
"""

from __future__ import annotations

import json
from typing import Any

from .calculator import calculator
from .search import search

__all__ = ["search", "calculator", "OPENAI_TOOL_SPECS", "dispatch", "TOOL_FUNCS"]

TOOL_FUNCS = {
    "search": lambda args: search(str(args.get("query", "")), int(args.get("k", 3))),
    "calculator": lambda args: calculator(str(args.get("expr", ""))),
}

OPENAI_TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search a knowledge base of general facts. Returns up to k text snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to look up."},
                    "k": {"type": "integer", "description": "How many snippets.", "default": 3},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression, e.g. '330 / 0.3048'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expr": {"type": "string", "description": "Arithmetic expression."},
                },
                "required": ["expr"],
            },
        },
    },
]


def dispatch(name: str, arguments: Any) -> str:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return f"ERROR: tool arguments for {name!r} were not valid JSON"
    if not isinstance(arguments, dict):
        arguments = {}
    func = TOOL_FUNCS.get(name)
    if func is None:
        return f"ERROR: unknown tool {name!r}"
    try:
        return str(func(arguments))
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: tool {name!r} raised {exc}"
