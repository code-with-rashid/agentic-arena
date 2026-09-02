"""Shared tools handed to every adapter.

`OPENAI_TOOL_SPECS` is the JSON-schema tool list in OpenAI "tools" format; adapters
that speak that format can pass it straight through. `dispatch` executes a tool call
by name and is what the vanilla loop (and the mock server's expectations) rely on.
"""

from __future__ import annotations

import json
from typing import Any

from .calculator import calculator
from .progress import save_progress
from .rooms import book_room, request_approval, search_rooms
from .search import search

__all__ = [
    "search",
    "calculator",
    "search_rooms",
    "book_room",
    "request_approval",
    "save_progress",
    "OPENAI_TOOL_SPECS",
    "SUSPEND_TOOL",
    "SUSPEND_TOOLS",
    "dispatch",
    "TOOL_FUNCS",
    "specs_for",
    "names_for",
]

# Tools whose invocation means "stop here", rather than "run this". An arena that
# declares one is asking for a suspend/resume cycle; adapters that cannot provide
# one are reported as unsupported for that arena.
#
#   request_approval - stop and ask a human (human_in_the_loop)
#   save_progress    - stop and checkpoint  (durable_state)
#
# Adapters intercept either and suspend. What happens at the pause is the arena's
# business, not the adapter's: `durable = true` in arena.toml makes the harness
# throw the runner away and rebuild it before resuming.
SUSPEND_TOOLS = ("request_approval", "save_progress")
SUSPEND_TOOL = SUSPEND_TOOLS[0]

TOOL_FUNCS = {
    "search": lambda args: search(str(args.get("query", "")), int(args.get("k", 3))),
    "calculator": lambda args: calculator(str(args.get("expr", ""))),
    "search_rooms": lambda args: search_rooms(
        int(args.get("capacity", 0) or 0), str(args.get("day", ""))
    ),
    "book_room": lambda args: book_room(str(args.get("room_id", ""))),
    "request_approval": lambda args: request_approval(str(args.get("summary", ""))),
    "save_progress": lambda args: save_progress(str(args.get("note", ""))),
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
    {
        "type": "function",
        "function": {
            "name": "search_rooms",
            "description": "List meeting rooms that seat at least `capacity` and are free on `day`.",
            "parameters": {
                "type": "object",
                "properties": {
                    "capacity": {"type": "integer", "description": "People to seat."},
                    "day": {"type": "string", "description": "Day of the week, e.g. 'tuesday'."},
                },
                "required": ["capacity", "day"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_approval",
            "description": (
                "Ask a human to approve a consequential action before you take it. "
                "Call this and stop; you will be told the decision."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "What you want approved."},
                },
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_progress",
            "description": (
                "Checkpoint what you have gathered so far, then stop. You will be "
                "resumed and can carry on from where you left off."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {"type": "string", "description": "What you have established so far."},
                },
                "required": ["note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_room",
            "description": "Book a meeting room by id. Only call this after approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_id": {"type": "string", "description": "Room id, e.g. 'R3'."},
                },
                "required": ["room_id"],
            },
        },
    },
]


OPENAI_TOOL_SPECS_BY_NAME: dict[str, dict[str, Any]] = {
    spec["function"]["name"]: spec for spec in OPENAI_TOOL_SPECS
}


def names_for(arena_tools: list[str] | None) -> list[str]:
    """Resolve an arena's declared tool list to known tool names, in a stable order.

    An arena that declares no tools gets all of them (older specs); an arena that
    names tools gets exactly those. Adapters must register only these — handing an
    agent a tool the arena did not declare breaks the "same fight for everyone"
    rule, and lets one framework solve a task in a way another cannot.
    """
    if not arena_tools:
        return list(OPENAI_TOOL_SPECS_BY_NAME)
    return [name for name in OPENAI_TOOL_SPECS_BY_NAME if name in set(arena_tools)]


def specs_for(arena_tools: list[str] | None) -> list[dict[str, Any]]:
    """OpenAI-format tool specs for exactly the tools an arena declares."""
    return [OPENAI_TOOL_SPECS_BY_NAME[name] for name in names_for(arena_tools)]


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
