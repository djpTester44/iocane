# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit>=0.13"]
# ///
"""merge_pyproject.py — Deterministic iocane harness config merger.

Reads existing pyproject.toml, compares against harness-required config,
and reports or applies only the missing pieces.

List-type fields (ruff select/ignore, dev packages) use union merge:
existing entries are preserved, missing harness entries are added.
Scalar fields are add-only: if a key exists at any value it is left
untouched; divergences from harness defaults are reported but never
auto-corrected.

Usage:
    uv run .claude/scripts/merge_pyproject.py            # check (default)
    uv run .claude/scripts/merge_pyproject.py --write    # apply additions
    uv run .claude/scripts/merge_pyproject.py --path path/to/pyproject.toml

Exit codes:
    0 — no gaps (check) or additions applied successfully (write)
    1 — gaps or divergences found (check) / file not found
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.items import Array, Table


# ---------------------------------------------------------------------------
# Harness requirements
# ---------------------------------------------------------------------------

REQUIRED_DEV_PACKAGES: list[str] = [
    "bandit>=1.8",
    "import-linter>=2.10",
    "mypy>=1.19.1",
    "pytest>=9.0.2",
    "pytest-cov>=7.0.0",
    "pytest-mock>=3.15.1",
    "ruff>=0.14.13",
]

REQUIRED_RUFF_SELECT: list[str] = [
    "E", "F", "I", "N", "W", "UP", "B", "C4", "SIM", "D100", "T201",
]
REQUIRED_RUFF_IGNORE: list[str] = ["E501"]

REQUIRED_RUFF_SCALARS: dict[str, Any] = {
    "line-length": 88,
}

REQUIRED_RUFF_FORMAT_SCALARS: dict[str, Any] = {
    "quote-style": "double",
    "indent-style": "space",
}

REQUIRED_PYTEST_SCALARS: dict[str, Any] = {
    "testpaths": ["tests"],
    "python_files": ["test_*.py"],
    "addopts": "-v --tb=short",
    "pythonpath": ["."],
}

REQUIRED_MYPY_SCALARS: dict[str, Any] = {
    "strict": True,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pkg_name(spec: str) -> str:
    """Normalize a PEP 508 spec to a canonical package name for comparison."""
    return re.split(r"[>=<!;\[ ]", spec)[0].strip().lower().replace("-", "_")


def _get(doc: Any, *path: str) -> Any:
    """Safely navigate nested tomlkit tables. Returns None if any key is absent."""
    cur = doc
    for key in path:
        if not hasattr(cur, "__contains__") or key not in cur:
            return None
        cur = cur[key]
    return cur


def _ensure(doc: Any, *path: str) -> Any:
    """Navigate to nested tables, creating them as needed. Returns the leaf table."""
    cur = doc
    for key in path:
        if key not in cur:
            cur.add(key, tomlkit.table())
        cur = cur[key]
    return cur


def _multiline_array(items: list[str]) -> Array:
    arr = tomlkit.array()
    arr.multiline(True)
    for item in items:
        arr.append(item)
    return arr


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.added: list[str] = []
        self.present: list[str] = []
        self.diverged: list[str] = []

    def add(self, loc: str, detail: str) -> None:
        self.added.append(f"  + {loc}: {detail}")

    def ok(self, loc: str, detail: str) -> None:
        self.present.append(f"  = {loc}: {detail}")

    def diverge(self, loc: str, existing: Any, expected: Any) -> None:
        self.diverged.append(
            f"  ! {loc}: existing={existing!r}, harness default={expected!r} — left unchanged"
        )

    @property
    def has_gaps(self) -> bool:
        return bool(self.added)

    @property
    def has_issues(self) -> bool:
        return bool(self.added) or bool(self.diverged)

    def print(self, *, write: bool) -> None:
        verb = "Added" if write else "Missing"
        if self.added:
            print(f"\n{verb}:")
            for line in self.added:
                print(line)
        if self.diverged:
            print("\nDivergences (existing values kept — review manually):")
            for line in self.diverged:
                print(line)
        if self.present and not self.added and not self.diverged:
            print("\nAll harness config present — no changes needed.")
        elif not self.added and not self.diverged:
            print("\nNothing to report.")
        if not write and self.has_gaps:
            print("\nRun with --write to apply missing additions.")


# ---------------------------------------------------------------------------
# Core merge logic
# ---------------------------------------------------------------------------

def process(doc: Any, *, write: bool) -> Report:
    report = Report()

    # --- [dependency-groups].dev -------------------------------------------
    existing_dev: list[str] = []
    dev_node = _get(doc, "dependency-groups", "dev")
    if dev_node is not None:
        existing_dev = [str(s) for s in dev_node]

    existing_names = {_pkg_name(s) for s in existing_dev}
    missing_pkgs = [
        spec for spec in REQUIRED_DEV_PACKAGES
        if _pkg_name(spec) not in existing_names
    ]

    if missing_pkgs:
        for spec in missing_pkgs:
            report.add("[dependency-groups].dev", f"add {spec!r}")
        if write:
            if dev_node is None:
                dg = _ensure(doc, "dependency-groups")
                dg.add("dev", _multiline_array(existing_dev + missing_pkgs))
            else:
                for spec in missing_pkgs:
                    doc["dependency-groups"]["dev"].append(spec)
    else:
        report.ok("[dependency-groups].dev", "all required packages present")

    # --- [tool.ruff] scalars ------------------------------------------------
    for key, val in REQUIRED_RUFF_SCALARS.items():
        ruff = _get(doc, "tool", "ruff")
        if ruff is None or key not in ruff:
            report.add(f"[tool.ruff].{key}", f"add {val!r}")
            if write:
                _ensure(doc, "tool", "ruff").add(key, val)
        elif ruff[key] != val:
            report.diverge(f"[tool.ruff].{key}", ruff[key], val)
        else:
            report.ok(f"[tool.ruff].{key}", repr(val))

    # --- [tool.ruff.lint] list unions ---------------------------------------
    for list_key, required in [
        ("select", REQUIRED_RUFF_SELECT),
        ("ignore", REQUIRED_RUFF_IGNORE),
    ]:
        ruff_lint = _get(doc, "tool", "ruff", "lint")
        if ruff_lint is None or list_key not in ruff_lint:
            report.add(f"[tool.ruff.lint].{list_key}", f"add {required}")
            if write:
                _ensure(doc, "tool", "ruff", "lint").add(
                    list_key, _multiline_array(required)
                )
        else:
            existing_codes = [str(c) for c in ruff_lint[list_key]]
            missing_codes = [c for c in required if c not in existing_codes]
            if missing_codes:
                report.add(
                    f"[tool.ruff.lint].{list_key}",
                    f"union-add {missing_codes}",
                )
                if write:
                    for code in missing_codes:
                        doc["tool"]["ruff"]["lint"][list_key].append(code)
            else:
                report.ok(
                    f"[tool.ruff.lint].{list_key}",
                    "all required codes present",
                )

    # --- [tool.ruff.format] scalars -----------------------------------------
    for key, val in REQUIRED_RUFF_FORMAT_SCALARS.items():
        ruff_fmt = _get(doc, "tool", "ruff", "format")
        if ruff_fmt is None or key not in ruff_fmt:
            report.add(f"[tool.ruff.format].{key}", f"add {val!r}")
            if write:
                _ensure(doc, "tool", "ruff", "format").add(key, val)
        elif ruff_fmt[key] != val:
            report.diverge(f"[tool.ruff.format].{key}", ruff_fmt[key], val)
        else:
            report.ok(f"[tool.ruff.format].{key}", repr(val))

    # --- [tool.pytest.ini_options] scalars ----------------------------------
    # TOML path: tool → pytest → ini_options  ([tool.pytest.ini_options])
    for key, val in REQUIRED_PYTEST_SCALARS.items():
        pytest_opts = _get(doc, "tool", "pytest", "ini_options")
        if pytest_opts is None or key not in pytest_opts:
            report.add(f"[tool.pytest.ini_options].{key}", f"add {val!r}")
            if write:
                _ensure(doc, "tool", "pytest", "ini_options").add(key, val)
        else:
            report.ok(f"[tool.pytest.ini_options].{key}", repr(pytest_opts[key]))

    # --- [tool.mypy] scalars ------------------------------------------------
    for key, val in REQUIRED_MYPY_SCALARS.items():
        mypy = _get(doc, "tool", "mypy")
        if mypy is None or key not in mypy:
            report.add(f"[tool.mypy].{key}", f"add {val!r}")
            if write:
                _ensure(doc, "tool", "mypy").add(key, val)
        elif mypy[key] != val:
            report.diverge(f"[tool.mypy].{key}", mypy[key], val)
        else:
            report.ok(f"[tool.mypy].{key}", repr(val))

    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge iocane harness config into pyproject.toml.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply additions. Default is check mode (report only).",
    )
    parser.add_argument(
        "--path",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: ./pyproject.toml).",
    )
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"ERROR: {path} not found. Run from project root or pass --path.")
        sys.exit(1)

    doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    report = process(doc, write=args.write)
    report.print(write=args.write)

    if args.write and report.has_gaps:
        path.write_text(tomlkit.dumps(doc), encoding="utf-8")
        print(f"\nWrote {path}")
    elif not args.write and report.has_issues:
        sys.exit(1)


if __name__ == "__main__":
    main()
