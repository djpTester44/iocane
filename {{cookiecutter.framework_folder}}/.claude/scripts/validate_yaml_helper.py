#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml", "pydantic>=2"]
# ///
"""Line-aware Pydantic validation helper for validate-yaml.sh.

Loads a YAML file, calls a parser's load_X() function (or a Pydantic
model's .model_validate classmethod), and on ValidationError reformats
the error with YAML line numbers and the offending field's current
value -- not just the Pydantic field path.

Invoked by validate-yaml.sh in place of raw uv run python -c "...
load_X(...)" calls. Without line context the agent retry-loops on the
same Pydantic error per .claude/rules/HARNESS-plan-mode.md ("A hook
that blocks without the agent understanding why produces retry loops").

Invocation:
    uv run python .claude/scripts/validate_yaml_helper.py \\
        --path <yaml-file> \\
        --module <parser-module> \\
        --function <loader-function-or-Model.model_validate>

Examples:
    --module contract_parser --function load_contracts
    --module schemas --function FindingFile.model_validate
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError


class _LineLoader(yaml.SafeLoader):
    """SafeLoader that decorates parsed mapping nodes with __line__ keys."""


def _construct_mapping_with_lines(
    loader: yaml.SafeLoader, node: yaml.MappingNode,
) -> dict[Any, Any]:
    mapping = loader.construct_mapping(node, deep=True)
    mapping["__line__"] = node.start_mark.line + 1
    return mapping


_LineLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_with_lines,
)


def _resolve_line(payload: object, loc: tuple[Any, ...]) -> int | None:
    """Walk loc path through payload; return nearest __line__ found."""
    cur: object = payload
    line: int | None = None
    if isinstance(cur, dict):
        line = cur.get("__line__")
    for key in loc:
        if isinstance(cur, dict):
            line = cur.get("__line__", line)
            cur = cur.get(key) if key in cur else None
        elif isinstance(cur, list) and isinstance(key, int):
            cur = cur[key] if 0 <= key < len(cur) else None
        else:
            break
        if cur is None:
            break
    return line


def _format_error(
    exc: ValidationError, source_path: Path, payload: object,
) -> str:
    """Format a ValidationError with YAML line + value context."""
    lines = [f"{source_path}: schema validation failed"]
    for err in exc.errors():
        loc_filtered = tuple(p for p in err["loc"] if p != "__line__")
        loc_path = ".".join(str(p) for p in loc_filtered)
        line = _resolve_line(payload, loc_filtered)
        value = err.get("input", "<unknown>")
        msg = err.get("msg", "")
        line_str = f" (line {line})" if line else ""
        lines.append(f"  {loc_path}{line_str}: {msg} -- got {value!r}")
    return "\n".join(lines)


def _resolve_callable(module_name: str, function_spec: str) -> Any:
    """Resolve module.attr or module.Class.classmethod to a callable."""
    sys.path.insert(0, ".claude/scripts")
    mod = importlib.import_module(module_name)
    parts = function_spec.split(".")
    obj: Any = mod
    for part in parts:
        obj = getattr(obj, part)
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="validate_yaml_helper",
        description=(
            "Validate a YAML file via a parser's load_X() or "
            "Model.model_validate; emit line-aware errors on failure."
        ),
    )
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument(
        "--module",
        required=True,
        help="Parser module (e.g., contract_parser, schemas)",
    )
    parser.add_argument(
        "--function",
        required=True,
        help=(
            "Loader function or Model.classmethod "
            "(e.g., load_contracts, FindingFile.model_validate)"
        ),
    )
    args = parser.parse_args()

    try:
        text = args.path.read_text(encoding="utf-8")
        payload = yaml.load(text, Loader=_LineLoader)
    except Exception as exc:
        sys.stderr.write(f"{args.path}: YAML parse failed: {exc}\n")
        return 2

    try:
        callable_obj = _resolve_callable(args.module, args.function)
    except Exception as exc:
        sys.stderr.write(
            f"{args.path}: cannot resolve {args.module}.{args.function}: "
            f"{exc}\n",
        )
        return 2

    try:
        # Loader functions take a path string; model_validate takes a payload.
        if args.function.endswith("model_validate"):
            # Strip __line__ keys before validating (they're not schema fields).
            cleaned = _strip_line_markers(payload)
            callable_obj(cleaned)
        else:
            callable_obj(str(args.path))
    except ValidationError as exc:
        sys.stderr.write(_format_error(exc, args.path, payload) + "\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"{args.path}: validation failed: {exc}\n")
        return 2

    return 0


def _strip_line_markers(obj: object) -> object:
    """Recursively remove __line__ keys from a parsed payload."""
    if isinstance(obj, dict):
        return {
            k: _strip_line_markers(v)
            for k, v in obj.items()
            if k != "__line__"
        }
    if isinstance(obj, list):
        return [_strip_line_markers(v) for v in obj]
    return obj


if __name__ == "__main__":
    sys.exit(main())
