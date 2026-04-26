"""validate_test_plan_completeness.py

Verifies that ``plans/test-plan.yaml`` covers every component in
``plans/component-contracts.yaml`` and that every component-level
``raises`` entry has at least one ``error_propagation`` invariant in
its TestPlanEntry.

Two checks:
  (a) Coverage: every component in component-contracts.yaml has a
      matching TestPlanEntry in test-plan.yaml.
  (b) Raises coverage: every component with a non-empty ``raises``
      list has at least one ``error_propagation`` invariant in its
      TestPlanEntry.

Exit codes:
  0 -- both checks pass.
  1 -- one or more components are uncovered, or one or more
       components with raises lack error_propagation coverage, or
       contracts is empty (nothing to validate).

Usage:
    uv run python .claude/scripts/validate_test_plan_completeness.py
"""

import argparse
import sys
from pathlib import Path

from contract_parser import load_contracts
from schemas import ComponentContractsFile
from test_plan_parser import (
    components_missing_entries,
    components_missing_error_propagation,
    load_test_plan,
)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Verify every component has a covering TestPlanEntry "
            "and every component-level raises entry has at least "
            "one error_propagation invariant."
        )
    )
    parser.add_argument(
        "--test-plan",
        default="plans/test-plan.yaml",
        help="Path to test-plan.yaml.",
    )
    parser.add_argument(
        "--contracts",
        default="plans/component-contracts.yaml",
        help="Path to component-contracts.yaml.",
    )
    args = parser.parse_args(argv)

    plan_path = Path(args.test_plan)
    if not plan_path.exists():
        sys.stderr.write(f"FAIL: test-plan file not found: {plan_path}\n")
        return 1

    contracts_path = Path(args.contracts)
    contracts = (
        load_contracts(str(contracts_path))
        if contracts_path.exists()
        else ComponentContractsFile()
    )

    if not contracts.components:
        sys.stderr.write(
            "FAIL: nothing to validate -- no components in "
            f"{contracts_path}. Author ComponentContract entries "
            "before validating test-plan completeness.\n"
        )
        return 1

    plan = load_test_plan(str(plan_path))
    component_names = set(contracts.components)
    raises_by_component = {
        name: list(comp.raises)
        for name, comp in contracts.components.items()
    }

    missing_entries = components_missing_entries(plan, component_names)
    missing_ep = components_missing_error_propagation(
        plan, raises_by_component
    )

    failed = False
    for component in missing_entries:
        sys.stderr.write(
            f"FAIL: no TestPlanEntry for component '{component}'\n"
        )
        failed = True
    for component in missing_ep:
        if component in missing_entries:
            continue  # already reported as missing entry
        sys.stderr.write(
            f"FAIL: component '{component}' declares raises but its "
            "TestPlanEntry has no error_propagation invariant\n"
        )
        failed = True

    if not failed:
        sys.stdout.write(
            f"PASS: every component has a TestPlanEntry "
            f"({len(component_names)} total); every component with "
            "raises has error_propagation coverage.\n"
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
