"""Check that every checkpoint touching a Protocol seam has CT coverage.

For each checkpoint with depends_on edges and src/ write targets, verifies
that its Protocol seams are covered by at least one connectivity test's
contract_under_test. CPs with protocol: None on all scope entries are
checked for coverage as a CT target_cp instead.

Usage:
    uv run python .claude/scripts/check_ct_completeness.py

Exits 0 if all seams are covered (or exempt).
Exits 1 if any checkpoint has uncovered Protocol seams.
Exits 2 on load/parse error.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from plan_parser import load_plan
from schemas import Plan


def _extract_covered_protocols(plan: Plan) -> set[str]:
    """Extract protocol paths from all CTs' contract_under_test fields.

    Handles both single and comma-separated entries like:
        "interfaces/geocoder.pyi :: IGeocoder"
        "interfaces/geocoder.pyi :: IGeocoder, interfaces/traffic.pyi :: ITrafficProvider"
    """
    covered: set[str] = set()
    for ct in plan.connectivity_tests:
        for segment in ct.contract_under_test.split(","):
            before_colons = segment.split("::")[0].strip()
            if before_colons:
                covered.add(before_colons)
    return covered


def _extract_ct_target_cps(plan: Plan) -> set[str]:
    """Collect all CP IDs that appear as target_cp in any CT."""
    return {ct.target_cp for ct in plan.connectivity_tests}


def _extract_ct_source_cps(plan: Plan) -> set[str]:
    """Collect all CP IDs that appear in source_cps of any CT.

    A CP whose ID appears as a source in at least one CT has its
    seam exercised from the consumer side -- the downstream CT
    verifies that the consumer correctly uses this CP's output.
    Per CDD principles, a contract is a behavioral specification at
    a module boundary; if a downstream CT exercises the boundary,
    the source Protocol is covered.
    """
    source_cps: set[str] = set()
    for ct in plan.connectivity_tests:
        source_cps.update(ct.source_cps)
    return source_cps


def main() -> int:
    plan_path = Path("plans/plan.yaml")
    if not plan_path.exists():
        print(f"ERROR: {plan_path} not found", file=sys.stderr)
        return 2

    plan = load_plan(str(plan_path))

    covered_protocols = _extract_covered_protocols(plan)
    ct_target_cps = _extract_ct_target_cps(plan)
    ct_source_cps = _extract_ct_source_cps(plan)

    violations: list[tuple[str, list[str]]] = []
    info_messages: list[str] = []

    for cp in plan.checkpoints:
        if not cp.depends_on:
            continue

        has_src_writes = any(t.startswith("src/") for t in cp.write_targets)
        if not has_src_writes:
            info_messages.append(
                f"INFO: {cp.id} — no src/ write targets (verification-only), exempt"
            )
            continue

        # Source-side coverage: if this CP is a source in any CT, a
        # downstream consumer already verifies the seam. The CP's own
        # Protocol is exercised via the CT's contract_under_test on the
        # consumer side.
        if cp.id in ct_source_cps:
            info_messages.append(
                f"INFO: {cp.id} — covered as CT source (provider seam tested by consumer)"
            )
            continue

        cp_protocols = [
            entry.protocol for entry in cp.scope if entry.protocol is not None
        ]

        if cp_protocols:
            uncovered = [p for p in cp_protocols if p not in covered_protocols]
            if uncovered:
                violations.append((cp.id, uncovered))
            else:
                info_messages.append(
                    f"INFO: {cp.id} — all scope protocols covered by existing CTs"
                )
        else:
            # All scope entries have protocol: None -- check as consumer
            if cp.id in ct_target_cps:
                info_messages.append(
                    f"INFO: {cp.id} — covered as CT target (consumer)"
                )
            else:
                violations.append((cp.id, ["(no protocol — not a CT target)"]))

    for msg in info_messages:
        print(msg)

    if not violations:
        total_cps = len(plan.checkpoints)
        print(f"PASS: {total_cps} checkpoints checked, all seams covered")
        return 0

    for cp_id, uncovered in sorted(violations):
        protocols_str = ", ".join(uncovered)
        print(
            f"MISSING_CONNECTIVITY_TEST: {cp_id} — uncovered protocol(s): "
            f"{protocols_str}",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
