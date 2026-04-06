"""Assign BL-NNN identifiers to backlog items missing an ID.

Replaces assign-backlog-ids.sh. Idempotent -- safe to re-run.

Usage:
    uv run python .claude/scripts/assign_backlog_ids.py [--repo-root PATH]
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backlog_parser import find_max_id, load_backlog, save_backlog
from schemas import BacklogItem


def _resolve_repo_root(cli_root: str | None) -> str | None:
    """Resolve repo root from CLI arg or git rev-parse fallback."""
    if cli_root:
        return cli_root
    result = subprocess.run(
        ["rtk", "git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def main() -> int:
    """Assign IDs to items with empty/missing id fields."""
    cli_root = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--repo-root" and i < len(sys.argv) - 1:
            cli_root = sys.argv[i + 1]

    repo_root = _resolve_repo_root(cli_root)
    if not repo_root:
        print("ERROR: Could not determine repo root.", file=sys.stderr)
        return 1

    backlog_path = str(Path(repo_root) / "plans/backlog.yaml")
    if not Path(backlog_path).is_file():
        print(f"ERROR: {backlog_path} not found.", file=sys.stderr)
        return 1

    backlog = load_backlog(backlog_path)
    max_id = find_max_id(backlog)
    next_id = max_id + 1

    new_items: list[BacklogItem] = []
    assigned = 0
    for item in backlog.items:
        if not item.id or item.id == "":
            bl_id = f"BL-{next_id:03d}"
            new_items.append(item.model_copy(update={"id": bl_id}))
            assigned += 1
            next_id += 1
        else:
            new_items.append(item)

    if assigned > 0:
        from schemas import Backlog
        save_backlog(backlog_path, Backlog(items=new_items))
        print(
            f"Assigned {assigned} new backlog ID(s). "
            f"Range: BL-{max_id + 1:03d} to BL-{next_id - 1:03d}"
        )
    else:
        print("No new IDs needed -- backlog is already fully tagged.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
