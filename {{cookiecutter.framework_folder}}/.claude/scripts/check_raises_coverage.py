#!/usr/bin/env python3
"""check_raises_coverage.py

Verifies that Protocol Raises: declarations in .pyi files have corresponding
pytest.raises() coverage in test files.

1. Scans interfaces/*.pyi for Protocol method docstrings with Raises: sections.
2. Extracts exception types from those sections (Google-style docstrings).
3. Searches tests/ for pytest.raises(ExceptionType) patterns.
4. Reports violations at two severity levels:
   - [CRITICAL]: Raises: declaration with no pytest.raises() coverage in tests.
   - [INFO]: Deferred -- method has ``# noqa: RAISES`` on its def line in .pyi.

Exit codes (strict binary gate):
  0 -- All raises declarations have test coverage, or all uncovered are deferred.
  1 -- Any CRITICAL remains unresolved.

Escape hatch:
  ``# noqa: RAISES``  -- on the method's ``def`` line in the .pyi file.
                         Defers all Raises: entries for that method. Reported as INFO.

Usage:
    uv run python .claude/scripts/check_raises_coverage.py [target_paths...]

    target_paths are accepted for CLI compatibility with run-compliance.sh
    but not used -- the script derives its file set from interfaces/ and tests/.
"""

import ast
import re
import sys
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

RAISES_SECTION_RE = re.compile(r"^\s*Raises:\s*$", re.MULTILINE)
RAISES_ENTRY_RE = re.compile(r"^\s{4,}(\w+(?:\.\w+)*)\s*:")
PYTEST_RAISES_RE = re.compile(r"pytest\.raises\(\s*(\w+(?:\.\w+)*)")
NOQA_RAISES_RE = re.compile(r"#\s*noqa:\s*RAISES\b")


class RaisesDeclaration(NamedTuple):
    """A single Raises: entry from a Protocol method docstring."""

    protocol: str
    method: str
    exception_type: str
    pyi_file: Path
    description: str


class Finding(NamedTuple):
    """Single compliance finding."""

    protocol: str
    method: str
    exception_type: str
    pyi_file: Path
    severity: str
    issue: str


SEVERITY_ORDER = {"CRITICAL": 0, "INFO": 2}


# ---------------------------------------------------------------------------
# Docstring parsing
# ---------------------------------------------------------------------------


def parse_raises_from_docstring(docstring: str) -> list[tuple[str, str]]:
    """Extract (exception_type, description) pairs from a Google-style Raises: section.

    Args:
        docstring: The method's docstring text.

    Returns:
        List of (exception_type, description) tuples.
    """
    if not docstring:
        return []

    lines = docstring.split("\n")
    in_raises = False
    entries: list[tuple[str, str]] = []

    for line in lines:
        if RAISES_SECTION_RE.match(line):
            in_raises = True
            continue

        if in_raises:
            entry_match = RAISES_ENTRY_RE.match(line)
            if entry_match:
                exc_type = entry_match.group(1)
                desc = line[entry_match.end():].strip()
                entries.append((exc_type, desc))
            elif line.strip() and not line.startswith(" " * 8):
                # Non-indented, non-empty line means end of Raises section
                # (next section header or end of docstring)
                if not line.startswith(" " * 4) or (
                    line.strip().endswith(":") and not line.strip().startswith("-")
                ):
                    break

    return entries


# ---------------------------------------------------------------------------
# .pyi scanning
# ---------------------------------------------------------------------------


def scan_pyi_files(interfaces_dir: Path) -> tuple[list[RaisesDeclaration], list[Finding]]:
    """Scan all .pyi files in interfaces/ for Raises: declarations.

    Returns:
        declarations: All raises declarations found.
        deferred: INFO findings for methods with # noqa: RAISES.
    """
    declarations: list[RaisesDeclaration] = []
    deferred: list[Finding] = []

    if not interfaces_dir.is_dir():
        return declarations, deferred

    for pyi_file in sorted(interfaces_dir.glob("*.pyi")):
        try:
            source = pyi_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception:
            continue

        source_lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Check if this is a Protocol class
            is_protocol = any(
                (isinstance(base, ast.Name) and base.id == "Protocol")
                or (isinstance(base, ast.Attribute) and base.attr == "Protocol")
                for base in node.bases
            )
            if not is_protocol:
                continue

            protocol_name = node.name

            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                docstring = ast.get_docstring(item)
                if not docstring:
                    continue

                raises_entries = parse_raises_from_docstring(docstring)
                if not raises_entries:
                    continue

                # Check for # noqa: RAISES on the def line
                def_line = source_lines[item.lineno - 1] if item.lineno <= len(source_lines) else ""
                is_deferred = bool(NOQA_RAISES_RE.search(def_line))

                for exc_type, desc in raises_entries:
                    if is_deferred:
                        deferred.append(Finding(
                            protocol=protocol_name,
                            method=item.name,
                            exception_type=exc_type,
                            pyi_file=pyi_file,
                            severity="INFO",
                            issue=f"Deferred (noqa): {exc_type} in {item.name}",
                        ))
                    else:
                        declarations.append(RaisesDeclaration(
                            protocol=protocol_name,
                            method=item.name,
                            exception_type=exc_type,
                            pyi_file=pyi_file,
                            description=desc,
                        ))

    return declarations, deferred


# ---------------------------------------------------------------------------
# Test file scanning
# ---------------------------------------------------------------------------


def find_tested_exceptions(tests_dir: Path) -> set[str]:
    """Scan tests/ for all exception types used in pytest.raises() calls.

    Returns:
        Set of exception type names found in pytest.raises() patterns.
    """
    tested: set[str] = set()

    if not tests_dir.is_dir():
        return tested

    for test_file in tests_dir.rglob("*.py"):
        try:
            content = test_file.read_text(encoding="utf-8")
        except Exception:
            continue

        for match in PYTEST_RAISES_RE.finditer(content):
            tested.add(match.group(1))

    return tested


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    # Positional targets accepted for CLI compatibility with run-compliance.sh.
    # The script derives its file set from interfaces/ and tests/.

    root_dir = Path.cwd()
    interfaces_dir = root_dir / "interfaces"
    tests_dir = root_dir / "tests"

    if not interfaces_dir.is_dir():
        print("No interfaces/ directory found. Nothing to check.")
        print("\nGATE PASS")
        sys.exit(0)

    # Scan .pyi files for Raises: declarations
    declarations, deferred_findings = scan_pyi_files(interfaces_dir)

    if not declarations and not deferred_findings:
        print("No Raises: declarations found in interfaces/*.pyi.")
        print("\nGATE PASS")
        sys.exit(0)

    # Scan test files for pytest.raises() coverage
    tested_exceptions = find_tested_exceptions(tests_dir)

    # Cross-reference: find uncovered raises
    all_findings: list[Finding] = list(deferred_findings)

    for decl in declarations:
        if decl.exception_type not in tested_exceptions:
            all_findings.append(Finding(
                protocol=decl.protocol,
                method=decl.method,
                exception_type=decl.exception_type,
                pyi_file=decl.pyi_file,
                severity="CRITICAL",
                issue=(
                    f"No pytest.raises({decl.exception_type}) found in tests/. "
                    f"Protocol {decl.protocol}.{decl.method} declares: "
                    f"Raises {decl.exception_type}: {decl.description}"
                ),
            ))

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    print("\n--- Raises Coverage Report ---\n")

    if not all_findings:
        print("All Protocol Raises: declarations have pytest.raises() coverage.")
        print("\nGATE PASS")
        sys.exit(0)

    all_findings.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 99))

    criticals = [f for f in all_findings if f.severity == "CRITICAL"]
    infos = [f for f in all_findings if f.severity == "INFO"]

    for f in all_findings:
        print(f"[{f.severity}] {f.protocol}.{f.method}: {f.issue}")
        print(f"         {f.pyi_file.as_posix()}")

    print(f"\nSummary: {len(criticals)} critical, {len(infos)} info (deferred)")

    if criticals:
        print(f"\nGATE FAIL - {len(criticals)} critical")
        sys.exit(1)

    print("\nGATE PASS - all uncovered raises are deferred (noqa: RAISES).")
    sys.exit(0)


if __name__ == "__main__":
    main()
