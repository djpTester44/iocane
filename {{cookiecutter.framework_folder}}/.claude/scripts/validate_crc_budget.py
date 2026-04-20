"""validate_crc_budget.py

Mechanical pre-gate for /io-architect -- enforces Appendix A section A.1 of
the reassembly plan. Run immediately before the human approval gate in
Step G of /io-architect.

Checks applied to every component in plans/component-contracts.yaml:
  A.1a: max MAX_RESPONSIBILITIES responsibilities per CRC
  A.1b: max MAX_FEATURES roadmap features per CRC (empty list = skip;
        architects SHOULD populate features, but a missing list does not
        by itself violate the cap)
  A.1c: composition_root components with more than
        MAX_COMP_ROOT_L23_COLLABORATORS Layer-2/3 collaborators must
        decompose into resource-scoped sub-components. When seams.yaml
        is not yet generated (common at the pre-gate), falls back to
        counting every collaborator -- fail-safe so that missing layer
        data cannot silently bypass the cap.

In addition, non-blocking warnings are emitted for behavioral components
(those with a Protocol or marked composition_root) that have
responsibilities but no declared features. A.1b can only evaluate
fan-out when features are declared, so this surfaces the
"did-you-forget-to-declare" case without failing the gate.

Exit codes:
  0 -- all components within budget (warnings may still be printed)
  1 -- one or more budget violations
  2 -- contracts file missing or unreadable

Usage:
    uv run python .claude/scripts/validate_crc_budget.py
    uv run python .claude/scripts/validate_crc_budget.py \\
        --contracts plans/component-contracts.yaml \\
        --seams plans/seams.yaml
"""

import argparse
import logging
import sys
from pathlib import Path

from contract_parser import load_contracts
from schemas import (
    CAP_COUNTED_LAYERS,
    ComponentContractsFile,
    SeamsFile,
)
from seam_parser import load_seams

logger = logging.getLogger(__name__)

# Budget thresholds -- policy constants, exposed for per-project tuning.
MAX_RESPONSIBILITIES: int = 3
MAX_FEATURES: int = 2
MAX_COMP_ROOT_L23_COLLABORATORS: int = 2  # threshold is > cap (i.e. >= 3 fails)


def _build_layer_lookup(seams: SeamsFile | None) -> dict[str, int]:
    """Build a component -> layer mapping from seams.yaml, or empty if absent."""
    if seams is None:
        return {}
    return {sc.component: sc.layer for sc in seams.components}


def _count_l23_collaborators(
    collaborators: list[str],
    layer_by_component: dict[str, int],
) -> int:
    """Count collaborators that sit in Layer 2 or Layer 3.

    Fall-back behavior when seams data is unavailable:
      - If the lookup is entirely empty (seams.yaml not generated), count
        every collaborator. This is the pre-gate scenario.
      - If the lookup is populated but a specific collaborator is missing
        from it, count that collaborator. A missing entry must not
        silently bypass the cap.
    """
    if not layer_by_component:
        return len(collaborators)
    count = 0
    for collab in collaborators:
        layer = layer_by_component.get(collab)
        if layer is None or layer in CAP_COUNTED_LAYERS:
            count += 1
    return count


def check_warnings(contracts: ComponentContractsFile) -> list[str]:
    """Return non-blocking warnings for likely missing feature declarations.

    A component is flagged when it is clearly behavioral (has a Protocol
    or is a composition root) and has responsibilities, but its
    ``features`` list is empty. Leaf infrastructure components (no
    Protocol, no composition_root) are silent.

    Warnings never affect exit codes -- they only surface the
    "did-you-forget-to-declare-features" case to the architect.
    """
    warnings: list[str] = []
    for name in sorted(contracts.components):
        contract = contracts.components[name]
        if contract.features:
            continue
        if not contract.responsibilities:
            continue
        is_behavioral = bool(contract.protocol) or contract.composition_root
        if not is_behavioral:
            continue
        warnings.append(
            f"{name}: behavioral component with empty features -- "
            "declare the roadmap feature IDs this component supports "
            "so A.1b can evaluate feature fan-out",
        )
    return warnings


def check_budget(
    contracts: ComponentContractsFile,
    seams: SeamsFile | None,
) -> list[str]:
    """Check every component against A.1 budget caps.

    Args:
        contracts: Parsed component-contracts.yaml.
        seams: Parsed seams.yaml, or None if not yet generated.

    Returns:
        List of human-readable violation messages. Empty list means pass.
    """
    violations: list[str] = []
    layer_by_component = _build_layer_lookup(seams)

    for name in sorted(contracts.components):
        contract = contracts.components[name]
        resp_count = len(contract.responsibilities)
        if resp_count > MAX_RESPONSIBILITIES:
            violations.append(
                f"A.1a {name}: {resp_count} responsibilities "
                f"(cap {MAX_RESPONSIBILITIES}) -- split the component",
            )

        feat_count = len(contract.features)
        if feat_count > MAX_FEATURES:
            violations.append(
                f"A.1b {name}: touches {feat_count} roadmap features "
                f"(cap {MAX_FEATURES}) -- split by feature boundary",
            )

        if contract.composition_root:
            l23_count = _count_l23_collaborators(
                contract.collaborators, layer_by_component,
            )
            if l23_count > MAX_COMP_ROOT_L23_COLLABORATORS:
                violations.append(
                    f"A.1c {name}: composition_root with {l23_count} "
                    f"Layer-2/3 collaborators "
                    f"(cap {MAX_COMP_ROOT_L23_COLLABORATORS}) -- decompose "
                    "into resource-scoped sub-components",
                )

    return violations


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CRC budget validator."""
    parser = argparse.ArgumentParser(
        description=(
            "Validate CRC budget caps (responsibilities, features, "
            "composition-root collaborators) for /io-architect Step G."
        ),
    )
    parser.add_argument(
        "--contracts",
        default="plans/component-contracts.yaml",
        help="Path to component-contracts.yaml.",
    )
    parser.add_argument(
        "--seams",
        default="plans/seams.yaml",
        help=(
            "Path to seams.yaml. If absent, the A.1c check falls back to "
            "counting every collaborator (fail-safe)."
        ),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    contracts_path = Path(args.contracts)
    if not contracts_path.exists():
        logger.error("contracts file not found: %s", contracts_path)
        return 2

    try:
        contracts = load_contracts(str(contracts_path))
    except Exception:
        logger.exception("failed to load %s", contracts_path)
        return 2

    seams: SeamsFile | None
    seams_path = Path(args.seams)
    if seams_path.exists():
        try:
            seams = load_seams(str(seams_path))
        except Exception:
            logger.warning(
                "failed to load %s -- falling back to total collaborator count",
                seams_path,
            )
            seams = None
    else:
        seams = None

    violations = check_budget(contracts, seams)
    warnings = check_warnings(contracts)
    total = len(contracts.components)

    for w in warnings:
        sys.stderr.write(f"WARN: {w}\n")

    if violations:
        for v in violations:
            sys.stderr.write(f"VIOLATION: {v}\n")
        sys.stderr.write(
            f"FAIL: {len(violations)} budget violation(s) across {total} "
            "component(s).\n",
        )
        return 1

    sys.stdout.write(
        f"PASS: {total} component(s) within CRC budget caps.\n",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
