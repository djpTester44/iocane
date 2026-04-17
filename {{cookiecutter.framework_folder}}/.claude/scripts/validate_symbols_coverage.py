"""validate_symbols_coverage.py

Verifies that every project-custom exception type referenced by
`interfaces/*.pyi` Protocols is declared in `plans/symbols.yaml`, and
that the symbol registry has no env_var or message_pattern conflicts.

Builtin and stdlib-module exceptions (e.g., ValueError,
subprocess.CalledProcessError, json.JSONDecodeError, socket.gaierror)
are treated as canonical Python vocabulary and skipped -- they are
already shared across CPs by the interpreter and stdlib docs.

Extraction strategy:
- ast.parse the .pyi, walk function defs, ast.get_docstring (which
  dedents correctly).
- Parse Google-style ``Raises:`` sections from the docstring text:
  walk lines from the section header, extract comma-separated type
  names before the first colon on each entry line.
- Terminates on section headers (Args, Returns, Yields, Note, Example,
  Warns, Attributes, See Also, References) or on outdent to the
  Raises: indent.

Exit codes (binary gate):
  0 -- every project-custom Raises type is declared and no conflicts.
  1 -- one or more uncovered customs OR one or more conflicts.

Usage:
    uv run python .claude/scripts/validate_symbols_coverage.py
"""

import argparse
import ast
import builtins
import re
import sys
from pathlib import Path

from symbols_parser import (
    detect_env_var_conflicts,
    detect_message_pattern_conflicts,
    load_symbols,
)
from schemas import SymbolKind

RAISES_SECTION_RE = re.compile(r"^\s*Raises:\s*$")
SECTION_HEADER_RE = re.compile(
    r"^\s*(Args|Arguments|Returns|Yields|Raises|Note|Notes|"
    r"Example|Examples|Warns|Warnings|Attributes|See\s+Also|"
    r"References|Todo|Tip|Important|Caution|Danger):\s*$"
)
TYPE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _builtin_exceptions() -> frozenset[str]:
    """Return all builtin exception class names."""
    return frozenset(
        name
        for name in dir(builtins)
        if isinstance(getattr(builtins, name), type)
        and issubclass(getattr(builtins, name), BaseException)
    )


BUILTIN_EXCEPTIONS = _builtin_exceptions()


def is_stdlib_exception(name: str) -> bool:
    """Return True if ``name`` is a builtin or stdlib-module exception.

    - Bare names like ``ValueError`` -> checked against ``builtins``.
    - Dotted names like ``subprocess.CalledProcessError`` -> first
      segment checked against ``sys.stdlib_module_names`` (Python 3.10+).

    Project-custom exceptions are by construction NOT in ``builtins``
    and not in ``stdlib_module_names``, so they fall through to the
    coverage check.
    """
    if name in BUILTIN_EXCEPTIONS:
        return True
    if "." in name:
        module = name.split(".", 1)[0]
        return module in sys.stdlib_module_names
    return False


def _parse_raises_from_docstring(docstring: str) -> set[str]:
    """Return the set of exception names from the Raises: section.

    Names retain any module qualifier (``foo.Bar``) so the caller can
    decide stdlib vs custom against the full path. Multi-type entries
    on one line (``ValueError, TypeError: when X``) are split.
    """
    raised: set[str] = set()
    lines = docstring.splitlines()
    in_raises = False
    raises_indent = -1
    for line in lines:
        if RAISES_SECTION_RE.match(line):
            in_raises = True
            raises_indent = len(line) - len(line.lstrip())
            continue
        if not in_raises:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if SECTION_HEADER_RE.match(line):
            in_raises = False
            continue
        cur_indent = len(line) - len(line.lstrip())
        if cur_indent <= raises_indent:
            in_raises = False
            continue
        if ":" not in line:
            continue
        type_part = line.split(":", 1)[0].strip()
        for raw in type_part.split(","):
            name = raw.strip()
            if name and TYPE_NAME_RE.match(name):
                raised.add(name)
    return raised


def extract_raises_from_pyi(path: Path) -> set[str]:
    """AST-walk a .pyi and return every Raises: type name."""
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        sys.stderr.write(f"WARN: failed to parse {path}: {exc}\n")
        return set()
    raised: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        docstring = ast.get_docstring(node)
        if not docstring:
            continue
        raised |= _parse_raises_from_docstring(docstring)
    return raised


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Verify project-custom Protocol Raises types are declared "
            "in symbols.yaml and the registry has no conflicts."
        )
    )
    parser.add_argument("--symbols", default="plans/symbols.yaml")
    parser.add_argument("--interfaces", default="interfaces")
    args = parser.parse_args(argv)

    symbols_path = Path(args.symbols)
    if not symbols_path.exists():
        sys.stderr.write(f"FAIL: symbols file not found: {symbols_path}\n")
        return 1
    interfaces_dir = Path(args.interfaces)
    if not interfaces_dir.exists():
        sys.stderr.write(
            f"FAIL: interfaces directory not found: {interfaces_dir}\n"
        )
        return 1

    registry = load_symbols(str(symbols_path))
    declared: set[str] = {
        name
        for name, sym in registry.symbols.items()
        if sym.kind == SymbolKind.EXCEPTION_CLASS
    }

    raised_in_pyi: dict[str, list[Path]] = {}
    for pyi_path in interfaces_dir.glob("*.pyi"):
        for full_name in extract_raises_from_pyi(pyi_path):
            if is_stdlib_exception(full_name):
                continue
            base_name = full_name.rsplit(".", 1)[-1]
            raised_in_pyi.setdefault(base_name, []).append(pyi_path)

    uncovered = sorted(set(raised_in_pyi) - declared)
    env_conflicts = detect_env_var_conflicts(registry)
    msg_conflicts = detect_message_pattern_conflicts(registry)

    failed = False
    for exc in uncovered:
        files = ", ".join(str(p) for p in raised_in_pyi[exc])
        sys.stderr.write(
            f"FAIL: exception '{exc}' raised in {files} but not declared "
            f"in symbols.yaml as kind=exception_class\n"
        )
        failed = True
    for env_var, claimants in env_conflicts.items():
        sys.stderr.write(
            f"FAIL: env_var '{env_var}' claimed by multiple settings_field "
            f"symbols: {', '.join(claimants)}\n"
        )
        failed = True
    for pattern, claimants in msg_conflicts.items():
        sys.stderr.write(
            f"FAIL: error_message pattern '{pattern}' shared by symbols: "
            f"{', '.join(claimants)}\n"
        )
        failed = True

    if not failed:
        sys.stdout.write(
            f"PASS: {len(raised_in_pyi)} project-custom exception type(s) "
            f"declared; no env_var or message_pattern conflicts.\n"
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
