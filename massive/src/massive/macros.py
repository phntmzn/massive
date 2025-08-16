from __future__ import annotations

"""
Map a Massive-style patch JSON -> 8 macro values (0..127) using configs/macro_map.yaml.

YAML schema (example)
---------------------
macros:
  - idx: 1                      # 1..8 (or 0..7); where to place the computed value
    name: "Intensity"           # optional, informational
    source:
      path: "env1.attack"       # dot path into the patch JSON
      default: 0.5              # used if path missing / not numeric
    mapping:
      in: [0.0, 1.0]            # input domain of the source value
      out: [0, 127]             # output CC range (integerized)
      curve: "linear"           # "linear" (default) or "pow:2.0" (gamma curve)
      invert: false             # optional; invert after curve
      clamp: true               # clamp to the input domain before mapping

  - idx: 2
    name: "Cutoff mix"
    # Optional expression instead of single path:
    #   vars: map variable -> path, then use "expr" with allowed ops
    source:
      expr: "0.7*a + 0.3*b"
      vars:
        a: "filter.cutoff"
        b: "env1.decay"
      default: 0.5
    mapping:
      in: [0.0, 1.0]
      out: [0, 127]
      curve: "pow:0.5"          # sqrt-like
      invert: false

  # Constant macro:
  - idx: 3
    source:
      constant: 0.25            # value in input domain before mapping
    mapping:
      in: [0.0, 1.0]
      out: [0, 127]

If the YAML is missing or invalid, we fall back to eight zeros.
"""

from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union
import logging
import math
import ast

import yaml

PathLike = Union[str, Path]

__all__ = [
    "map_to_macros",
    "load_macro_map",
    "resolve_path",
]

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# YAML loading
# --------------------------------------------------------------------------- #


def load_macro_map(path: PathLike = "configs/macro_map.yaml") -> Dict[str, Any]:
    """
    Load macro map YAML. Returns a dict with key 'macros' -> list of entries.
    """
    p = Path(path)
    if not p.exists():
        log.warning("macro_map.yaml not found at %s; returning defaults.", p)
        return {"macros": []}
    try:
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise TypeError("Top-level YAML must be a mapping.")
        macros = data.get("macros") or []
        if not isinstance(macros, list):
            raise TypeError("`macros` must be a list.")
        return {"macros": macros}
    except Exception as e:
        log.exception("Failed to load macro map: %s", e)
        return {"macros": []}


# --------------------------------------------------------------------------- #
# Patch navigation
# --------------------------------------------------------------------------- #


def resolve_path(root: Any, dotted: str, default: Optional[float] = None) -> Optional[float]:
    """
    Resolve a dotted path into nested dict/list structures.
    Supports simple list indices via either dots ('.0') or brackets ('osc[0]').

    Returns float if possible; otherwise `default`.
    """
    cur = root
    # Split on dots but keep bracket segments intact
    parts = dotted.split(".") if dotted else []
    try:
        for part in parts:
            # Handle bracketed indices like 'osc[0][1]'
            while "[" in part and part.endswith("]"):
                key, idx_str = part[: part.index("[")], part[part.index("[") + 1 : -1]
                if key:
                    cur = cur[key]
                # Support multi-dimensional (handled by while loop)
                if idx_str == "":
                    return default
                idx = int(idx_str)
                cur = cur[idx]
                part = ""  # consumed
            if part:
                # If current is list and token is int, treat as index
                if isinstance(cur, list) and part.isdigit():
                    cur = cur[int(part)]
                else:
                    cur = cur[part]
        # At the end, try to coerce to float
        if isinstance(cur, (int, float)):
            return float(cur)
        # Sometimes values are strings like "0.5"
        if isinstance(cur, str):
            try:
                return float(cur.strip())
            except ValueError:
                return default
        return default
    except (KeyError, IndexError, TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- #
# Safe expression evaluation
# --------------------------------------------------------------------------- #


_ALLOWED_FUNCS = {
    "min": min,
    "max": max,
    "abs": abs,
    "sqrt": math.sqrt,
}


class _SafeEval(ast.NodeVisitor):
    """Very small, safe subset evaluator for arithmetic expressions."""

    def __init__(self, variables: Mapping[str, float]):
        self.vars = variables

    def visit(self, node):  # type: ignore[override]
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.BinOp):
            left = self.visit(node.left)
            right = self.visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** right
            if isinstance(node.op, ast.Mod):
                return left % right
            raise ValueError("Operator not allowed")
        if isinstance(node, ast.UnaryOp):
            operand = self.visit(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise ValueError("Unary operator not allowed")
        if isinstance(node, ast.Num):  # py3.8 compat
            return float(node.n)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError("Constant type not allowed")
        if isinstance(node, ast.Name):
            if node.id in self.vars:
                return float(self.vars[node.id])
            raise ValueError(f"Unknown variable: {node.id}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise ValueError("Function not allowed")
            func = _ALLOWED_FUNCS[node.func.id]
            args = [self.visit(a) for a in node.args]
            return float(func(*args))
        raise ValueError("Expression not allowed")

    @classmethod
    def eval(cls, expr: str, variables: Mapping[str, float]) -> float:
        tree = ast.parse(expr, mode="eval")
        return float(cls(variables).visit(tree))


# --------------------------------------------------------------------------- #
# Mapping utilities
# --------------------------------------------------------------------------- #


def _parse_curve(curve: Optional[str]) -> Tuple[str, float]:
    """
    Returns (kind, gamma). kind in {"linear", "pow"}.
    For "pow", extract gamma from "pow:2.0". Defaults to ("linear", 1.0).
    """
    if not curve:
        return "linear", 1.0
    c = str(curve).strip().lower()
    if c.startswith("pow:"):
        try:
            gamma = float(c.split(":", 1)[1])
        except Exception:
            gamma = 1.0
        return "pow", gamma
    if c in {"pow", "power"}:
        return "pow", 1.0
    return "linear", 1.0


def _map_value(
    x: float,
    in_min: float,
    in_max: float,
    out_min: float = 0.0,
    out_max: float = 127.0,
    curve: Optional[str] = None,
    invert: bool = False,
    clamp: bool = True,
) -> int:
    """Map x from [in_min,in_max] to [out_min,out_max] with optional curve/invert."""
    if in_max == in_min:
        t = 0.0
    else:
        t = (x - in_min) / (in_max - in_min)
    if clamp:
        t = max(0.0, min(1.0, t))

    kind, gamma = _parse_curve(curve)
    if kind == "pow":
        # Gamma correction: gamma > 1 biases low, gamma < 1 biases high
        t = max(0.0, t) ** max(1e-9, gamma)
    # linear otherwise

    if invert:
        t = 1.0 - t

    y = out_min + t * (out_max - out_min)
    return int(round(y))


def _coerce_float(v: Optional[float], default: float) -> float:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def map_to_macros(
    patch: Mapping[str, Any],
    macro_map_path: PathLike = "configs/macro_map.yaml",
) -> List[int]:
    """
    Compute 8 macro values for a given patch.

    Returns:
        List[int]: length 8, each 0..127.
    """
    cfg = load_macro_map(macro_map_path)
    entries = cfg.get("macros", [])
    values: List[Optional[int]] = [None] * 8

    # Helper to place a value in 1..8 slot; on bad idx, use first empty slot.
    def place(val: int, idx: Optional[int]) -> None:
        nonlocal values
        slot: Optional[int] = None
        if isinstance(idx, int):
            if 1 <= idx <= 8:
                slot = idx - 1
            elif 0 <= idx <= 7:
                slot = idx
        if slot is None:
            try:
                slot = values.index(None)
            except ValueError:
                slot = 0
        values[slot] = max(0, min(127, int(val)))

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        idx = entry.get("idx")
        source = entry.get("source", {}) or {}
        mapping = entry.get("mapping", {}) or {}

        # Source evaluation
        default_val = _coerce_float(source.get("default"), 0.0)

        if "constant" in source:
            src_val = _coerce_float(source.get("constant"), default_val)
        elif "expr" in source and "vars" in source and isinstance(source["vars"], dict):
            # Build variables from patch
            var_map: Dict[str, float] = {}
            for var_name, var_path in source["vars"].items():
                var_map[var_name] = _coerce_float(
                    resolve_path(patch, str(var_path), default=default_val),
                    default_val,
                )
            try:
                src_val = float(_SafeEval.eval(str(source["expr"]), var_map))
            except Exception:
                log.warning("Failed to evaluate expr for macro idx=%s; using default.", idx)
                src_val = default_val
        elif "path" in source:
            src_val = _coerce_float(
                resolve_path(patch, str(source["path"]), default=default_val),
                default_val,
            )
        else:
            src_val = default_val

        # Mapping spec
        in_rng = mapping.get("in", [0.0, 1.0])
        out_rng = mapping.get("out", [0, 127])
        curve = mapping.get("curve")
        invert = bool(mapping.get("invert", False))
        clamp = bool(mapping.get("clamp", True))

        try:
            in_min, in_max = float(in_rng[0]), float(in_rng[1])
        except Exception:
            in_min, in_max = 0.0, 1.0
        try:
            out_min, out_max = float(out_rng[0]), float(out_rng[1])
        except Exception:
            out_min, out_max = 0.0, 127.0

        val = _map_value(
            src_val,
            in_min,
            in_max,
            out_min=out_min,
            out_max=out_max,
            curve=curve,
            invert=invert,
            clamp=clamp,
        )
        place(val, idx if isinstance(idx, int) else None)

    # Fill any remaining None with zeros
    return [v if isinstance(v, int) else 0 for v in values]
