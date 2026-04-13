"""validate_ct_assertions.py

Soft lexical validator for ``ConnectivityTest.assertion`` strings in
``plans/plan.yaml`` -- Appendix A §A.4c of the reassembly plan.

For every CT in the plan, verifies that the assertion contains at
least one keyword from each of the three behavior-observable sets:
  - call binding: called, invoke (stem matches invoke/invoked/invokes),
                  with argument, passes, passed to
  - cardinality:  once, exactly, per, times, each, for every
  - error propagation: raises, propagates, re-raises, error, exception

All findings are non-blocking WARN lines on stderr. The script exits 0
regardless of findings -- ``/validate-plan`` surfaces the WARN lines
as OBSERVATION-severity flags (``CT_ASSERTION_KEYWORDS``) without
failing the gate.

Exit codes:
  0 -- always (non-blocking, including on plan-load failure)

Usage:
    uv run python .claude/scripts/validate_ct_assertions.py
    uv run python .claude/scripts/validate_ct_assertions.py \\
        --plan plans/plan.yaml
"""

import argparse
import logging
import sys
from pathlib import Path

from plan_parser import load_plan
from schemas import ct_assertion_warnings

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CT-assertion lexical validator."""
    parser = argparse.ArgumentParser(
        description=(
            "Soft lexical validator for ConnectivityTest.assertion "
            "keywords (call binding, cardinality, error propagation). "
            "Non-blocking -- always exits 0."
        ),
    )
    parser.add_argument(
        "--plan",
        default="plans/plan.yaml",
        help="Path to plan.yaml.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    plan_path = Path(args.plan)
    if not plan_path.exists():
        sys.stderr.write(f"WARN: plan file not found: {plan_path}\n")
        return 0

    try:
        plan = load_plan(str(plan_path))
    except Exception as exc:  # noqa: BLE001 -- non-blocking validator
        sys.stderr.write(f"WARN: failed to load {plan_path}: {exc}\n")
        return 0

    flagged = 0
    for ct in plan.connectivity_tests:
        missing = ct_assertion_warnings(ct.assertion)
        if missing:
            sys.stderr.write(
                f"WARN: {ct.test_id} assertion lacks keyword(s) for: "
                f"{', '.join(missing)}\n",
            )
            flagged += 1

    total = len(plan.connectivity_tests)
    if flagged:
        sys.stderr.write(
            f"{flagged} of {total} CT assertion(s) missing behavior "
            "keywords (call binding, cardinality, error propagation). "
            "Non-blocking.\n",
        )
    else:
        sys.stdout.write(
            f"PASS: {total} CT assertion(s) cover all three behavior "
            "observables.\n",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
