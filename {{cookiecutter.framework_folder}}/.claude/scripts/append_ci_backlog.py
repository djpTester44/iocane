"""Append a CI-regression or CI-collection-error backlog entry.

Called by ci-sidecar.sh to add new regressions to plans/backlog.yaml.

Usage:
    uv run python .claude/scripts/append_ci_backlog.py \
        --test-id tests/test_foo.py::test_bar \
        --tag CI-REGRESSION \
        --pre-commit abc123 \
        --post-commit def456 \
        --error "AssertionError: expected 5" \
        [--repo-root PATH]
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backlog_parser import add_item, find_max_id, load_backlog, save_backlog
from schemas import BacklogItem, BacklogTag


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
    """Append a CI backlog entry."""
    parser = argparse.ArgumentParser(description="Append CI backlog entry")
    parser.add_argument("--test-id", required=True)
    parser.add_argument("--tag", required=True, choices=["CI-REGRESSION", "CI-COLLECTION-ERROR"])
    parser.add_argument("--pre-commit", required=True)
    parser.add_argument("--post-commit", required=True)
    parser.add_argument("--error", default="")
    parser.add_argument("--repo-root", default=None)
    args = parser.parse_args()

    repo_root = _resolve_repo_root(args.repo_root)
    if not repo_root:
        print("ERROR: Could not determine repo root.", file=sys.stderr)
        return 1

    backlog_path = str(Path(repo_root) / "plans/backlog.yaml")
    if not Path(backlog_path).is_file():
        # Create empty backlog if it doesn't exist
        save_backlog(backlog_path, __import__("schemas").Backlog())

    backlog = load_backlog(backlog_path)
    next_id = find_max_id(backlog) + 1
    bl_id = f"BL-{next_id:03d}"

    tag = BacklogTag(args.tag)
    if tag == BacklogTag.CI_REGRESSION:
        title = f"{args.test_id} -- new failure after wave merge"
    else:
        title = f"{args.test_id} -- new collection error after wave merge"

    item = BacklogItem(
        id=bl_id,
        tag=tag,
        title=title,
        source="ci-sidecar post-wave",
        pre_wave_commit=args.pre_commit,
        post_wave_commit=args.post_commit,
        error=args.error if args.error else None,
    )

    backlog = add_item(backlog, item)
    save_backlog(backlog_path, backlog)

    print(f"Appended {bl_id} [{args.tag}] {args.test_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
