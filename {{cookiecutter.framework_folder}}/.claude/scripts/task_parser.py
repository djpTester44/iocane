"""Task file parsing utilities for plans/tasks/CP-XX.yaml.

YAML-based task I/O with Pydantic validation. Provides query and mutation
functions that replace grep/sed/regex patterns previously used by scripts,
hooks, and commands against the former CP-XX.md (now CP-XX.yaml).

Used by hooks, scripts, dispatch-agents.sh, and commands via
``uv run python -c "..."``.
"""

from pathlib import Path

import yaml
from schemas import (
    ExecutionFinding,
    StepProgress,
    TaskFile,
)

# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

# Fields that must always appear in output, even when empty (D8).
_ALWAYS_EMIT = {"step_progress", "execution_findings"}

# Fields where empty lists can be stripped for readability.
_STRIPPABLE_LISTS = {
    "acceptance_criteria",
    "write_targets",
    "context_files",
    "connectivity_tests",
    "refactor_commands",
    "seam_context",
}


def load_task(path: str) -> TaskFile:
    """Load and validate a task YAML file."""
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        msg = f"Task file is empty: {path}"
        raise ValueError(msg)
    raw = yaml.safe_load(text)
    if raw is None:
        msg = f"Task file parsed as None: {path}"
        raise ValueError(msg)
    return TaskFile.model_validate(raw)


def save_task(path: str, task: TaskFile) -> None:
    """Serialize task to YAML and write to disk.

    Uses ``exclude_none=True`` so optional fields are omitted when unset.
    Always emits ``step_progress`` and ``execution_findings`` (D8).
    """
    data = task.model_dump(mode="json", exclude_none=True)
    # Strip empty lists for readability -- except always-emit fields
    for key in _STRIPPABLE_LISTS:
        if key in data and not data[key]:
            del data[key]
    # Clean empty sub-lists within structured objects
    for ct in data.get("connectivity_tests", []):
        if "fixture_deps" in ct and not ct["fixture_deps"]:
            del ct["fixture_deps"]
    for seam in data.get("seam_context", []):
        if (
            "injected_contracts" in seam
            and not seam["injected_contracts"]
        ):
            del seam["injected_contracts"]
        if "key_failure_modes" in seam and not seam["key_failure_modes"]:
            del seam["key_failure_modes"]
    # Ensure always-emit fields exist
    for key in _ALWAYS_EMIT:
        if key not in data:
            data[key] = []
    output = yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    Path(path).write_text(output, encoding="utf-8")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def extract_ct_files(task: TaskFile) -> list[str]:
    """Return all connectivity test file paths.

    These are CT files owned by this checkpoint as target_cp.
    """
    return [ct.file for ct in task.connectivity_tests]


def extract_ct_gates(task: TaskFile) -> list[str]:
    """Return all connectivity test gate commands."""
    return [ct.gate for ct in task.connectivity_tests]


# ---------------------------------------------------------------------------
# Mutations (return new TaskFile)
# ---------------------------------------------------------------------------


def reset_step_progress(task: TaskFile) -> TaskFile:
    """Return a new TaskFile with all steps marked done=False."""
    new_steps = [
        StepProgress(step=sp.step, done=False) for sp in task.step_progress
    ]
    return task.model_copy(update={"step_progress": new_steps})


def mark_step_done(task: TaskFile, step_prefix: str) -> TaskFile:
    """Return a new TaskFile with the matching step marked done=True.

    Matches by prefix: step_prefix="B" matches "B: Red -- write failing test".
    """
    new_steps: list[StepProgress] = []
    for sp in task.step_progress:
        if sp.step.startswith(step_prefix):
            new_steps.append(StepProgress(step=sp.step, done=True))
        else:
            new_steps.append(sp)
    return task.model_copy(update={"step_progress": new_steps})


def add_execution_finding(
    task: TaskFile, finding: ExecutionFinding
) -> TaskFile:
    """Return a new TaskFile with the finding appended."""
    return task.model_copy(
        update={
            "execution_findings": [*task.execution_findings, finding],
        }
    )


def set_execution_findings(
    task: TaskFile, findings: list[ExecutionFinding]
) -> TaskFile:
    """Return a new TaskFile with execution_findings replaced (batch)."""
    return task.model_copy(update={"execution_findings": findings})
