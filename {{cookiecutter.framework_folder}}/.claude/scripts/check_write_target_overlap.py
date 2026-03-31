"""Check write-target overlap across a set of checkpoints in plans/plan.md.

Usage:
    uv run python .claude/scripts/check_write_target_overlap.py CP-01 CP-02 ...

Exits 0 if no file path appears in more than one CP's write targets.
Exits 1 if any collision is found; each collision is reported to stderr.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backlog_parser import extract_cp_section, extract_field


def parse_write_targets(raw: str) -> list[str]:
    """Extract backtick-wrapped paths from a Write targets field value."""
    return re.findall(r"`([^`]+)`", raw)


def main(cp_ids: list[str]) -> int:
    plan_path = Path("plans/plan.md")
    if not plan_path.exists():
        print(f"ERROR: {plan_path} not found", file=sys.stderr)
        return 2

    plan_text = plan_path.read_text(encoding="utf-8")

    # file_path -> list of CP-IDs that claim it
    claims: dict[str, list[str]] = {}

    for cp_id in cp_ids:
        section = extract_cp_section(plan_text, cp_id)
        if section is None:
            print(f"ERROR: section for {cp_id} not found in plan.md", file=sys.stderr)
            return 2

        raw_field = extract_field(section, "Write targets")
        if raw_field is None:
            # No write targets declared -- no overlap possible for this CP
            continue

        for path in parse_write_targets(raw_field):
            claims.setdefault(path, []).append(cp_id)

    collisions = {f: cps for f, cps in claims.items() if len(cps) > 1}

    if not collisions:
        total_files = len(claims)
        print(
            f"PASS: {total_files} files across {len(cp_ids)} checkpoints, no overlaps"
        )
        return 0

    for file_path, cps in sorted(collisions.items()):
        cp_list = ", ".join(cps)
        print(f"COLLISION: {file_path} claimed by {{{cp_list}}}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(
            "Usage: check_write_target_overlap.py CP-XX [CP-YY ...]", file=sys.stderr
        )
        sys.exit(2)
    sys.exit(main(args))
