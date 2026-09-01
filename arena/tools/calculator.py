"""A deliberately small, safe arithmetic evaluator.

Handed to every adapter unchanged so that "can the framework call a tool and use
the result" is what's measured, not the tool itself.
"""

from __future__ import annotations

import ast
import operator

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def calculator(expr: str) -> str:
    """Evaluate a basic arithmetic expression and return the result as a string."""
    try:
        tree = ast.parse(expr, mode="eval")
        value = _eval(tree)
    except Exception as exc:  # noqa: BLE001 - report any failure back to the agent
        return f"ERROR: could not evaluate {expr!r} ({exc})"
    if value == int(value):
        return str(int(value))
    return f"{value:.6g}"
