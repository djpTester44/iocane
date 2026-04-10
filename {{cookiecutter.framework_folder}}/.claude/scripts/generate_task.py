"""Deterministic task file generator.

Reads plan.yaml + seams.yaml and produces schema-valid TaskFile objects
by construction. Eliminates non-deterministic agent reasoning for the
14 mechanical fields; leaves 3 agent-crafted fields (acceptance_criteria,
execution_notes, refactor_commands) for caller review.

Usage:
    uv run python .claude/scripts/generate_task.py CP-01 --plan plans/plan.yaml --seams plans/seams.yaml
    uv run python .claude/scripts/generate_task.py --batch CP-01 CP-02 --plan plans/plan.yaml --seams plans/seams.yaml --write
"""

import logging
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_parser import (
    connectivity_tests_for_cp,
    find_checkpoint,
    resolve_feature,
    resolved_contract,
    resolved_criteria,
)
from schemas import (
    ConnectivityTest,
    Plan,
    SeamEntry,
    SeamsFile,
    StepProgress,
    TaskConnectivityTest,
    TaskFile,
)
from seam_parser import find_by_component, load_seams, to_seam_entry
from task_parser import save_task

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# Canonical 6-step progress list (B through G), all incomplete.
CANONICAL_STEPS: list[StepProgress] = [
    StepProgress(step="B: Red -- write failing test"),
    StepProgress(step="C: Green -- minimum implementation"),
    StepProgress(step="D: Gate -- run checkpoint gate"),
    StepProgress(step="E: Connectivity tests"),
    StepProgress(step="F: Refactor -- DI and compliance"),
    StepProgress(step="G: Commit and write status"),
]


def _project_ct(ct: ConnectivityTest) -> TaskConnectivityTest:
    """Project a plan-level ConnectivityTest to a task-level entry.

    Strips topology fields (source_cps, target_cp), keeps the 7
    fields relevant to the executing sub-agent.
    """
    return TaskConnectivityTest(
        test_id=ct.test_id,
        function=ct.function,
        file=ct.file,
        fixture_deps=list(ct.fixture_deps),
        contract_under_test=ct.contract_under_test,
        assertion=ct.assertion,
        gate=ct.gate,
    )


def _build_refactor_commands(write_targets: list[str]) -> list[str]:
    """Build ruff + mypy refactor commands for .py write targets."""
    commands: list[str] = []
    for target in write_targets:
        if target.endswith(".py"):
            commands.append(f"uv run rtk ruff check --fix {target}")
            commands.append(f"uv run rtk mypy {target}")
    return commands


def _build_source(cp_id: str, source_bl: list[str] | None) -> str | None:
    """Build the source field for remediation checkpoints."""
    if source_bl:
        return f"plans/backlog.yaml {' '.join(source_bl)}"
    return None


def generate_task(
    plan: Plan,
    seams: SeamsFile,
    cp_id: str,
) -> TaskFile:
    """Generate a TaskFile from plan + seams data for a given checkpoint.

    Args:
        plan: Loaded Plan object.
        seams: Loaded SeamsFile object.
        cp_id: Checkpoint ID (e.g. "CP-01").

    Returns:
        A fully populated TaskFile ready for save_task() or agent review.

    Raises:
        ValueError: If checkpoint not found or contract cannot be resolved.
    """
    cp = find_checkpoint(plan, cp_id)
    if cp is None:
        msg = f"Checkpoint {cp_id} not found in plan"
        raise ValueError(msg)

    # Field 3: feature -- chain-walk for remediation CPs
    if cp.remediates is not None:
        feature = resolve_feature(plan, cp_id)
        if feature is None:
            msg = f"Cannot resolve feature for remediation CP {cp_id}"
            raise ValueError(msg)
    else:
        feature = cp.feature

    # Field 6: acceptance_criteria
    criteria = resolved_criteria(cp)
    if not criteria:
        logger.warning("%s: acceptance_criteria empty, caller should synthesize", cp_id)

    # Field 7: contract
    contract = resolved_contract(cp)
    if contract is None:
        msg = f"No contract and no scope for {cp_id} -- cannot resolve contract"
        raise ValueError(msg)

    # Field 11: connectivity_tests (target_cp only) + CT file paths for write_targets
    all_cts = connectivity_tests_for_cp(plan, cp_id)
    target_cts = [ct for ct in all_cts if ct.target_cp == cp_id]
    task_cts = [_project_ct(ct) for ct in target_cts]
    ct_file_paths = [ct.file for ct in target_cts]

    # Field 8: write_targets = CP write_targets + CT file paths
    write_targets = list(cp.write_targets) + ct_file_paths

    # Field 12: refactor_commands
    refactor_commands = _build_refactor_commands(write_targets)

    # Field 13: source (remediation only)
    source: str | None = None
    if cp.remediates and cp.source_bl:
        source = _build_source(cp_id, cp.source_bl)

    # Field 15: seam_context from scope entries
    seam_context: list[SeamEntry] = []
    for entry in cp.scope:
        comp = find_by_component(seams, entry.component)
        if comp is not None:
            seam_context.append(to_seam_entry(comp))

    return TaskFile(
        id=cp.id,
        title=cp.title,
        feature=feature,
        workflow="io-execute",
        objective=cp.description,
        acceptance_criteria=criteria,
        contract=contract,
        write_targets=write_targets,
        context_files=list(cp.context_files),
        gate_command=cp.gate_command,
        connectivity_tests=task_cts,
        refactor_commands=refactor_commands,
        source=source,
        execution_notes=None,
        seam_context=seam_context,
        execution_findings=[],
        step_progress=list(CANONICAL_STEPS),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> dict[str, object]:
    """Parse CLI arguments.

    Returns dict with keys: cp_ids, plan, seams, write, outdir.
    """
    args: dict[str, object] = {
        "cp_ids": [],
        "plan": "plans/plan.yaml",
        "seams": "plans/seams.yaml",
        "write": False,
        "outdir": "plans/tasks",
    }
    i = 0
    batch_mode = False
    while i < len(argv):
        arg = argv[i]
        if arg == "--batch":
            batch_mode = True
            i += 1
            # Consume all following non-flag args as CP IDs
            while i < len(argv) and not argv[i].startswith("--"):
                cp_ids = args["cp_ids"]
                assert isinstance(cp_ids, list)
                cp_ids.append(argv[i])
                i += 1
        elif arg == "--plan" and i + 1 < len(argv):
            args["plan"] = argv[i + 1]
            i += 2
        elif arg == "--seams" and i + 1 < len(argv):
            args["seams"] = argv[i + 1]
            i += 2
        elif arg == "--outdir" and i + 1 < len(argv):
            args["outdir"] = argv[i + 1]
            i += 2
        elif arg == "--write":
            args["write"] = True
            i += 1
        elif not arg.startswith("--") and not batch_mode:
            # Positional CP-ID (single mode)
            cp_ids = args["cp_ids"]
            assert isinstance(cp_ids, list)
            cp_ids.append(arg)
            i += 1
        else:
            logger.error("Unknown argument: %s", arg)
            sys.exit(1)

    cp_ids = args["cp_ids"]
    assert isinstance(cp_ids, list)
    if not cp_ids:
        logger.error("No CP-IDs provided")
        sys.exit(1)

    return args


def main() -> int:
    """CLI entry point."""
    from plan_parser import load_plan

    args = _parse_args(sys.argv[1:])
    cp_ids: list[str] = args["cp_ids"]  # type: ignore[assignment]
    plan_path: str = args["plan"]  # type: ignore[assignment]
    seams_path: str = args["seams"]  # type: ignore[assignment]
    write: bool = args["write"]  # type: ignore[assignment]
    outdir: str = args["outdir"]  # type: ignore[assignment]

    plan = load_plan(plan_path)
    seams = load_seams(seams_path)

    failed = 0
    for cp_id in cp_ids:
        try:
            task = generate_task(plan, seams, cp_id)
        except ValueError as exc:
            logger.error("%s: %s", cp_id, exc)
            failed += 1
            continue

        if write:
            out_path = str(Path(outdir) / f"{cp_id}.yaml")
            save_task(out_path, task)
            logger.info("Wrote %s", out_path)
        else:
            yaml.dump(
                task.model_dump(mode="json", exclude_none=True),
                sys.stdout,
                default_flow_style=False,
                sort_keys=False,
            )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
