"""Plan parsing utilities for plans/plan.yaml.

YAML-based plan I/O with Pydantic validation. Provides query and mutation
functions that replace grep/regex patterns previously used by scripts,
hooks, and commands against the former plan.md (now plan.yaml).

Used by hooks, scripts, auto_checkpoint.py, and commands via
``uv run rtk python -c "..."``.
"""

import re
from pathlib import Path

import yaml
from schemas import (
    Checkpoint,
    CheckpointStatus,
    ConnectivityTest,
    Plan,
)

# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def load_plan(path: str) -> Plan:
    """Load and validate plans/plan.yaml."""
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        return Plan()
    raw = yaml.safe_load(text)
    if raw is None:
        return Plan()
    return Plan.model_validate(raw)


def save_plan(path: str, plan: Plan) -> None:
    """Serialize plan to YAML and write to disk.

    Uses ``exclude_none=True`` so remediation-only fields are omitted
    from regular checkpoints, keeping the YAML clean.
    """
    data = plan.model_dump(mode="json", exclude_none=True)
    # Clean up empty lists to keep YAML readable
    for cp in data.get("checkpoints", []):
        for key in (
            "scope",
            "write_targets",
            "context_files",
            "depends_on",
            "parallelizable_with",
            "acceptance_criteria",
        ):
            if key in cp and not cp[key]:
                del cp[key]
        # Clean empty methods in scope entries
        for entry in cp.get("scope", []):
            if "methods" in entry and not entry["methods"]:
                del entry["methods"]
    for ct in data.get("connectivity_tests", []):
        if "fixture_deps" in ct and not ct["fixture_deps"]:
            del ct["fixture_deps"]
    if not data.get("self_healing_log"):
        data.pop("self_healing_log", None)
    output = yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    Path(path).write_text(output, encoding="utf-8")


# ---------------------------------------------------------------------------
# Task-file bridging helpers
# ---------------------------------------------------------------------------


def resolved_contract(cp: Checkpoint) -> str | None:
    """Return the checkpoint's contract, falling back to scope[0].protocol."""
    if cp.contract:
        return cp.contract
    if cp.scope:
        return cp.scope[0].protocol
    return None


def resolved_criteria(cp: Checkpoint) -> list[str]:
    """Return acceptance criteria. Empty list signals caller to synthesize."""
    return cp.acceptance_criteria


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def find_checkpoint(plan: Plan, cp_id: str) -> Checkpoint | None:
    """Find a checkpoint by CP-ID."""
    for cp in plan.checkpoints:
        if cp.id == cp_id:
            return cp
    return None


def pending_checkpoints(plan: Plan) -> list[Checkpoint]:
    """Return all checkpoints with status == pending."""
    return [cp for cp in plan.checkpoints if cp.status == CheckpointStatus.PENDING]


def completed_checkpoints(plan: Plan) -> list[Checkpoint]:
    """Return all checkpoints with status == complete."""
    return [cp for cp in plan.checkpoints if cp.status == CheckpointStatus.COMPLETE]


def in_progress_checkpoints(plan: Plan) -> list[Checkpoint]:
    """Return all checkpoints with status == in-progress."""
    return [
        cp for cp in plan.checkpoints if cp.status == CheckpointStatus.IN_PROGRESS
    ]


def remediation_checkpoints(plan: Plan) -> list[Checkpoint]:
    """Return all checkpoints that are remediation CPs."""
    return [cp for cp in plan.checkpoints if cp.remediates is not None]


def unblocked_checkpoints(plan: Plan) -> list[Checkpoint]:
    """Return pending checkpoints whose dependencies are all complete."""
    completed_ids = {cp.id for cp in completed_checkpoints(plan)}
    result: list[Checkpoint] = []
    for cp in pending_checkpoints(plan):
        if all(dep in completed_ids for dep in cp.depends_on):
            result.append(cp)
    return result


def write_targets_for_cps(
    plan: Plan, cp_ids: list[str]
) -> dict[str, list[str]]:
    """Return {cp_id: write_targets} for the given CP-IDs."""
    result: dict[str, list[str]] = {}
    for cp_id in cp_ids:
        cp = find_checkpoint(plan, cp_id)
        if cp is not None:
            result[cp_id] = list(cp.write_targets)
    return result


def connectivity_tests_for_cp(
    plan: Plan, cp_id: str
) -> list[ConnectivityTest]:
    """Return connectivity tests where cp_id appears in source_cps or as target_cp."""
    return [
        ct
        for ct in plan.connectivity_tests
        if cp_id in ct.source_cps or ct.target_cp == cp_id
    ]


# ---------------------------------------------------------------------------
# Chain walkers (ported from auto_checkpoint.py)
# ---------------------------------------------------------------------------


def resolve_feature(plan: Plan, cp_id: str) -> str | None:
    """Walk the remediates chain to the root roadmap CP for its Feature field."""
    visited: set[str] = set()
    current = cp_id
    while current and current not in visited:
        visited.add(current)
        cp = find_checkpoint(plan, current)
        if cp is None:
            return None
        if cp.remediates is None:
            return cp.feature
        # Walk to parent: extract base CP-ID from remediates value
        parent_match = re.match(r"(CP-\d+)", cp.remediates)
        if parent_match:
            current = parent_match.group(1)
        else:
            return cp.feature
    return None


def resolve_gate(
    plan: Plan, cp_id: str, override: str | None = None
) -> str | None:
    """Resolve the gate command for a checkpoint.

    If ``override`` is provided and is not an 'inherited from CP-NN' reference,
    it is used directly. Otherwise walks the remediates chain to find the
    nearest gate_command.
    """
    if override:
        inherit_match = re.match(r"inherited from (CP-\d+(?:R\d+)?)", override)
        if inherit_match:
            source_cp = find_checkpoint(plan, inherit_match.group(1))
            if source_cp and source_cp.gate_command:
                return source_cp.gate_command
        else:
            return override

    cp = find_checkpoint(plan, cp_id)
    if cp is None:
        return None
    if cp.gate_command:
        return cp.gate_command

    # Walk remediates chain for inherited gate
    if cp.remediates:
        parent_match = re.match(r"(CP-\d+(?:R\d+)?)", cp.remediates)
        if parent_match:
            parent = find_checkpoint(plan, parent_match.group(1))
            if parent and parent.gate_command:
                return parent.gate_command
    return None


# ---------------------------------------------------------------------------
# Mutations (return new Plan -- frozen checkpoints)
# ---------------------------------------------------------------------------


def update_checkpoint_status(
    plan: Plan, cp_id: str, status: CheckpointStatus
) -> Plan:
    """Return a new Plan with the specified checkpoint's status updated."""
    new_cps: list[Checkpoint] = []
    for cp in plan.checkpoints:
        if cp.id == cp_id:
            new_cps.append(cp.model_copy(update={"status": status}))
        else:
            new_cps.append(cp)
    return plan.model_copy(update={"checkpoints": new_cps})


def add_checkpoint(plan: Plan, cp: Checkpoint) -> Plan:
    """Return a new Plan with the checkpoint appended."""
    return plan.model_copy(update={"checkpoints": [*plan.checkpoints, cp]})


def set_validated(
    plan: Plan,
    validated: bool,
    date: str | None = None,
    note: str | None = None,
) -> Plan:
    """Return a new Plan with validation fields updated."""
    return plan.model_copy(
        update={
            "validated": validated,
            "validated_date": date,
            "validated_note": note,
        }
    )
