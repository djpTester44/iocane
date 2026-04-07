"""Check that CT dependency invariant holds in plans/plan.yaml.

For every connectivity test, the target_cp's depends_on list must include
all source_cps. A missing dependency means the target checkpoint could be
scheduled before its source completes.

Usage:
    uv run python .claude/scripts/check_ct_depends_on.py

Exits 0 if all target_cp.depends_on include their source_cps.
Exits 1 if any gap is found; each gap is reported to stderr.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from plan_parser import find_checkpoint, load_plan


def main() -> int:
    plan_path = Path("plans/plan.yaml")
    if not plan_path.exists():
        print(f"ERROR: {plan_path} not found", file=sys.stderr)
        return 2

    plan = load_plan(str(plan_path))

    gaps: list[tuple[str, str, str]] = []

    for ct in plan.connectivity_tests:
        target_cp = find_checkpoint(plan, ct.target_cp)
        if target_cp is None:
            print(
                f"ERROR: target_cp {ct.target_cp} not found in plan.yaml",
                file=sys.stderr,
            )
            return 2

        for source_cp in ct.source_cps:
            if source_cp not in target_cp.depends_on:
                gaps.append((ct.test_id, ct.target_cp, source_cp))

    if not gaps:
        total_cts = len(plan.connectivity_tests)
        print(
            f"PASS: {total_cts} connectivity tests, all dependency invariants hold"
        )
        return 0

    for test_id, target_cp, missing_cp in sorted(gaps):
        print(
            f"CT_DEPENDS_ON_GAP: {test_id} — target {target_cp} missing "
            f"dependency on {missing_cp}",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
