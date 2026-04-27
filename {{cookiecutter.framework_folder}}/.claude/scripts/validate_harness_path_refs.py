"""Strict-ban scanner for `harness/<subdir>/` runtime path literals.

Walks a tree (default `./harness`) and flags any line containing one
of the banned literals (the four subdir names are listed in
``BANNED_SUBDIRS`` below; the full patterns are constructed at runtime
from those names so this source file does not itself contain a
matching substring). Per `feedback_harness_path_references`, runtime
paths inside artifacts that ship into a consumer repo's `.claude/`
directory must be written as `.claude/<subdir>/`. A
`harness/<subdir>/` literal works in neither location -- not in
iocane_build (governance lives under `.claude/`) and not in the
consumer (also `.claude/`). The only place such a path "resolves" is
the iocane_build staging tree, which is never the runtime context.

This is the deterministic gate the recurring agent-reasoning audit
collapses into (per `HARNESS-plan-mode.md` determinism gradient): one
script-tier exit-code check at migration time replaces a per-session
prose audit.

Exit codes:
  0 -- no banned literals found.
  1 -- one or more banned literals found; per-line findings are written
       to stderr.
  2 -- usage / IO error (scan root not a directory).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Subdir names under harness/ whose runtime references inside artifact
# bodies are banned. Patterns are constructed from these parts at
# runtime so this source file does not itself contain a literal
# `harness/<subdir>/` substring (which would self-flag).
BANNED_SUBDIRS: tuple[str, ...] = (
    "scripts",
    "hooks",
    "commands",
    "capability-templates",
)


def banned_patterns() -> tuple[str, ...]:
    """Return the literal substrings whose presence on any line of a
    scanned file constitutes a violation.
    """
    base = "harness" + "/"
    return tuple(base + sub + "/" for sub in BANNED_SUBDIRS)


def scan_file(path: Path, patterns: tuple[str, ...]) -> list[tuple[int, str, str]]:
    """Return per-line hits for a single file.

    Each hit is `(line_no, matched_pattern, line_text)`. Files that
    fail to decode as UTF-8 are treated as binary and yield no hits.

    Args:
        path: File to scan.
        patterns: Banned literals to search for.

    Returns:
        List of (line_no, pattern, line) tuples; one entry per matched
        line (a single line matching multiple patterns reports the
        first match only -- operator sees the line content and can
        infer the rest).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    hits: list[tuple[int, str, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pat in patterns:
            if pat in line:
                hits.append((line_no, pat, line))
                break
    return hits


def scan(root: Path) -> list[tuple[Path, int, str, str]]:
    """Scan `root` recursively for banned literals.

    Args:
        root: Directory to walk. Every regular file beneath it is
            considered; binary files are skipped silently via the
            UnicodeDecodeError path in `scan_file`.

    Returns:
        Flat list of `(path, line_no, pattern, line_text)` findings,
        in `rglob` traversal order.
    """
    patterns = banned_patterns()
    findings: list[tuple[Path, int, str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        for line_no, pat, line in scan_file(path, patterns):
            findings.append((path, line_no, pat, line))
    return findings


def _format_finding(path: Path, line_no: int, pat: str, line: str) -> str:
    """Format a single finding as `path:line: banned 'X': <line>`."""
    try:
        rel = path.relative_to(Path.cwd())
    except ValueError:
        rel = path
    return (
        f"{rel.as_posix()}:{line_no}: banned path literal "
        f"{pat!r}: {line.strip()}\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns exit code (0 clean, 1 violations, 2 usage)."""
    parser = argparse.ArgumentParser(
        description=(
            "Scan a tree for banned harness/<subdir>/ runtime-path "
            "literals. At runtime in a consumer repo the artifact lives "
            "under .claude/, so a harness/<subdir>/ reference inside an "
            "artifact body is broken in both iocane_build and the "
            "consumer. Exits 1 on any hit; 0 when clean."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("harness"),
        help=(
            "Directory to scan recursively. Defaults to ./harness. "
            "This is the only tree the scanner walks; tests/ and "
            ".claude/ are never visited."
        ),
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        sys.stderr.write(f"ERROR: scan root {root} is not a directory\n")
        return 2

    findings = scan(root)
    if not findings:
        return 0

    for path, line_no, pat, line in findings:
        sys.stderr.write(_format_finding(path, line_no, pat, line))
    sys.stderr.write(
        f"\n{len(findings)} banned harness/<subdir>/ runtime-path "
        f"literal(s) flagged. Per `feedback_harness_path_references`, "
        f"replace with .claude/<subdir>/ -- artifacts run from .claude/ "
        f"in consumer repos after migration.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
