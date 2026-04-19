"""Cookiecutter pre-generation hook for the Iocane brownfield template.

Runs with cwd set to the target directory before any template files are
copied. Archives pre-existing harness artifacts by renaming them with an
``OLD_`` prefix so cookiecutter emits onto clean ground. Aborts non-zero
on any rename failure rather than leaving a half-archived target.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ARTIFACTS: tuple[str, ...] = (".claude", "CLAUDE.md", "AGENTS.md", "plans")


def _archive_name(source: Path) -> Path:
    """Return a non-colliding ``OLD_``-prefixed sibling path for *source*."""
    primary = source.with_name(f"OLD_{source.name}")
    if not primary.exists():
        return primary
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return source.with_name(f"OLD_{source.name}.{stamp}")


def _archive(source: Path) -> None:
    """Rename *source* to its archive name, logging the move to stdout."""
    target = _archive_name(source)
    source.rename(target)
    print(f"archived {source.name} -> {target.name}")


def main() -> int:
    """Archive any pre-existing harness artifacts in the target directory."""
    cwd = Path.cwd()
    found = [cwd / name for name in ARTIFACTS if (cwd / name).exists()]
    if not found:
        return 0
    for source in found:
        try:
            _archive(source)
        except OSError as exc:
            print(
                f"ERROR: failed to archive {source.name}: {exc}",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
