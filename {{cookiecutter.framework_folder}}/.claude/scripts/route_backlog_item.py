"""Annotate a backlog item with a Routed: annotation.

Replaces route-backlog-item.sh. Deterministic replacement for
instruction-based routing in io-checkpoint.

Usage:
    uv run python .claude/scripts/route_backlog_item.py BL-NNN CP-NNR
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backlog_parser import add_annotation, find_item, load_backlog, save_backlog
from schemas import Annotation


def _resolve_repo_root() -> str | None:
    """Resolve repo root from git rev-parse."""
    result = subprocess.run(
        ["rtk", "git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def main() -> int:
    """Route a backlog item to a checkpoint."""
    # Parse positional args and optional --prompt
    args = sys.argv[1:]
    prompt_text: str | None = None
    positional: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--prompt" and i + 1 < len(args):
            prompt_text = args[i + 1]
            i += 2
        else:
            positional.append(args[i])
            i += 1

    if len(positional) != 2:
        print(
            "Usage: uv run python .claude/scripts/route_backlog_item.py BL-NNN CP-NNR [--prompt TEXT]",
            file=sys.stderr,
        )
        return 1

    bl_id = positional[0]
    cp_id = positional[1]
    today = date.today().isoformat()

    repo_root = _resolve_repo_root()
    if not repo_root:
        print("ERROR: Could not determine repo root.", file=sys.stderr)
        return 1

    backlog_path = str(Path(repo_root) / "plans/backlog.yaml")
    if not Path(backlog_path).is_file():
        print(f"ERROR: {backlog_path} not found.", file=sys.stderr)
        return 1

    backlog = load_backlog(backlog_path)
    item = find_item(backlog, bl_id)
    if item is None:
        print(f"ERROR: {bl_id} not found in {backlog_path}", file=sys.stderr)
        return 1

    # Check for duplicate Routed annotation
    for ann in item.annotations:
        if ann.type == "Routed" and ann.value == cp_id:
            print(
                f"ERROR: {bl_id} already has a Routed annotation for {cp_id}",
                file=sys.stderr,
            )
            return 1

    annotation = Annotation(type="Routed", value=cp_id, date=today, prompt=prompt_text)
    backlog = add_annotation(backlog, bl_id, annotation)
    save_backlog(backlog_path, backlog)

    print(f"Routed {bl_id} -> {cp_id} ({today})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
