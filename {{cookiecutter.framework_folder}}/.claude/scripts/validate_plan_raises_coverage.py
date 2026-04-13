"""validate_plan_raises_coverage.py

Appendix A §A.4d -- plan-wide Raises coverage check.

Scans every ``interfaces/*.pyi`` for Protocol ``Raises:`` declarations and
verifies each exception type is named in at least one
``plans/plan.yaml`` ``connectivity_tests[*].assertion``. OBSERVATION-severity
warnings for any uncovered declaration.

Rationale (A.4d tightening): A.4a-c require every ``Raises:`` on the
*source* side of a declared DI seam to appear in the CT assertion. A typed
exception raised inside a component rather than propagated across a seam
escapes A.4a-c's coverage -- no DI seam carries it, so no CT is obligated
to name it. This plan-wide pass closes that gap by checking the full
Protocol-level surface against the full CT assertion surface, regardless of
seam topology.

The match is a case-insensitive substring check. If the Protocol docstring
declares ``Raises: DepotNotConfiguredError`` and any CT assertion contains
the string ``DepotNotConfiguredError`` (case-insensitive), the declaration
is covered.

Distinct from ``check_raises_coverage.py``, which validates test coverage
against ``pytest.raises()`` calls in ``tests/``. A.4d is about seam-surface
observability in CT signatures; ``check_raises_coverage.py`` is about
runtime observability in the test suite. Both are needed; neither subsumes
the other.

Exit codes:
  0 -- always (non-blocking).

Usage:
    uv run python .claude/scripts/validate_plan_raises_coverage.py
    uv run python .claude/scripts/validate_plan_raises_coverage.py \\
        --plan plans/plan.yaml --interfaces-dir interfaces
"""

import argparse
import logging
import sys
from pathlib import Path

from check_raises_coverage import scan_pyi_files
from plan_parser import load_plan

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the plan-wide Raises coverage validator."""
    parser = argparse.ArgumentParser(
        description=(
            "Appendix A §A.4d plan-wide Raises coverage. Cross-references "
            "every interfaces/*.pyi Raises: against every plan.yaml "
            "connectivity_tests[*].assertion. Non-blocking -- always exits 0."
        ),
    )
    parser.add_argument(
        "--plan",
        default="plans/plan.yaml",
        help="Path to plan.yaml.",
    )
    parser.add_argument(
        "--interfaces-dir",
        default="interfaces",
        type=Path,
        help="Directory containing .pyi Protocol definitions.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    plan_path = Path(args.plan)
    if not plan_path.exists():
        sys.stderr.write(f"WARN: plan file not found: {plan_path}\n")
        return 0

    interfaces_dir = args.interfaces_dir
    if not interfaces_dir.is_dir():
        sys.stderr.write(
            f"WARN: interfaces directory not found: {interfaces_dir}\n",
        )
        return 0

    # A.4d does not honor the noqa: RAISES hatch that check_raises_coverage
    # does -- CT coverage is orthogonal to test coverage. Ignore the
    # deferred list; every declaration is in scope here.
    declarations, _ = scan_pyi_files(interfaces_dir)
    if not declarations:
        sys.stdout.write(
            "PASS: no Protocol Raises: declarations to validate.\n",
        )
        return 0

    try:
        plan = load_plan(str(plan_path))
    except Exception as exc:  # noqa: BLE001 -- non-blocking validator
        sys.stderr.write(f"WARN: failed to load {plan_path}: {exc}\n")
        return 0

    assertions_lower = " || ".join(
        ct.assertion for ct in plan.connectivity_tests
    ).lower()

    flagged = 0
    seen: set[tuple[str, str, str]] = set()
    for decl in declarations:
        key = (decl.protocol, decl.method, decl.exception_type)
        if key in seen:
            continue
        seen.add(key)
        if decl.exception_type.lower() in assertions_lower:
            continue
        sys.stderr.write(
            f"WARN: {decl.protocol}.{decl.method} declares "
            f"Raises: {decl.exception_type} -- not named in any CT "
            "assertion in plan.yaml\n",
        )
        flagged += 1

    total = len(seen)
    if flagged:
        sys.stderr.write(
            f"{flagged} of {total} declared Raises: exception(s) missing "
            "from CT assertions. Non-blocking -- OBSERVATION severity.\n",
        )
    else:
        sys.stdout.write(
            f"PASS: {total} declared Raises: exception(s) covered by at "
            "least one CT assertion.\n",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
