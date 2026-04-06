"""Pydantic schemas for YAML-based harness data files.

Defines the canonical structure for plans/backlog.yaml, plans/plan.yaml,
plans/tasks/CP-XX.yaml, and plans/seams.yaml.
Used by backlog_parser.py, plan_parser.py, task_parser.py, seam_parser.py,
hooks, and scripts for validation and serialization.
"""

import re
from enum import StrEnum

from pydantic import BaseModel, field_validator, model_validator


class BacklogTag(StrEnum):
    """Valid backlog item tags."""

    DESIGN = "DESIGN"
    REFACTOR = "REFACTOR"
    CLEANUP = "CLEANUP"
    DEFERRED = "DEFERRED"
    TEST = "TEST"
    CI_REGRESSION = "CI-REGRESSION"
    CI_COLLECTION_ERROR = "CI-COLLECTION-ERROR"
    CI_EXTERNAL = "CI-EXTERNAL"


class Severity(StrEnum):
    """Item severity levels."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ItemStatus(StrEnum):
    """Item lifecycle status."""

    OPEN = "open"
    RESOLVED = "resolved"
    DEFERRED = "deferred"


class Annotation(BaseModel, frozen=True):
    """Structured annotation on a backlog item."""

    type: str
    value: str
    date: str | None = None
    prompt: str | None = None


class BacklogItem(BaseModel, frozen=True):
    """A single backlog entry in plans/backlog.yaml."""

    id: str
    tag: BacklogTag
    title: str
    severity: Severity = Severity.MEDIUM
    status: ItemStatus = ItemStatus.OPEN
    component: str | None = None
    files: list[str] = []
    detail: str | None = None
    contract_impact: str | None = None
    source: str | None = None
    blocked_by: list[str] = []
    routed_to: str | None = None
    routing_prompt: str | None = None
    annotations: list[Annotation] = []
    pre_wave_commit: str | None = None
    post_wave_commit: str | None = None
    error: str | None = None

    @field_validator("id")
    @classmethod
    def validate_bl_id(cls, v: str) -> str:
        """Enforce BL-NNN format."""
        import re

        if not re.fullmatch(r"BL-\d{3}", v):
            msg = f"id must match BL-NNN format, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("blocked_by")
    @classmethod
    def validate_blocked_by_ids(cls, v: list[str]) -> list[str]:
        """Ensure all blocked_by entries are valid BL-IDs."""
        import re

        for bl_id in v:
            if not re.fullmatch(r"BL-\d{3}", bl_id):
                msg = f"blocked_by entry must match BL-NNN format, got '{bl_id}'"
                raise ValueError(msg)
        return v


class Backlog(BaseModel):
    """Top-level backlog container. Mutable -- items list needs append/replace."""

    items: list[BacklogItem] = []


# ---------------------------------------------------------------------------
# Plan schemas (plans/plan.yaml)
# ---------------------------------------------------------------------------

_CP_ID_RE = re.compile(r"^CP-\d{2}(R\d+)?$")
_CT_ID_RE = re.compile(r"^CT-\d{3}$")
_BL_ID_RE = re.compile(r"^BL-\d{3}$")


class CheckpointStatus(StrEnum):
    """Checkpoint lifecycle status."""

    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    COMPLETE = "complete"


class ScopeEntry(BaseModel, frozen=True):
    """A single scope line within a checkpoint."""

    component: str
    protocol: str | None = None
    methods: list[str] = []


class Checkpoint(BaseModel, frozen=True):
    """A single checkpoint in plans/plan.yaml."""

    id: str
    title: str
    feature: str
    description: str
    status: CheckpointStatus = CheckpointStatus.PENDING
    scope: list[ScopeEntry] = []
    write_targets: list[str] = []
    context_files: list[str] = []
    gate_command: str = ""
    depends_on: list[str] = []
    parallelizable_with: list[str] = []

    # Remediation-only fields (optional, co-occurrence enforced)
    remediates: str | None = None
    source: str | None = None
    source_bl: list[str] | None = None
    severity: Severity | None = None

    @field_validator("id")
    @classmethod
    def validate_cp_id(cls, v: str) -> str:
        """Enforce CP-NN or CP-NNR{n} format."""
        if not _CP_ID_RE.fullmatch(v):
            msg = f"id must match CP-NN or CP-NNR{{n}} format, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("source_bl")
    @classmethod
    def validate_source_bl_ids(cls, v: list[str] | None) -> list[str] | None:
        """Ensure all source_bl entries are valid BL-IDs."""
        if v is None:
            return v
        for bl_id in v:
            if not _BL_ID_RE.fullmatch(bl_id):
                msg = f"source_bl entry must match BL-NNN format, got '{bl_id}'"
                raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def check_remediation_co_occurrence(self) -> "Checkpoint":
        """If remediates is set, source/source_bl/severity must all be set."""
        if self.remediates is not None:
            missing = []
            if self.source is None:
                missing.append("source")
            if self.source_bl is None:
                missing.append("source_bl")
            if self.severity is None:
                missing.append("severity")
            if missing:
                msg = (
                    f"Remediation checkpoint {self.id} has 'remediates' set "
                    f"but is missing: {', '.join(missing)}"
                )
                raise ValueError(msg)
        return self


class ConnectivityTest(BaseModel, frozen=True):
    """A connectivity test specification in plans/plan.yaml."""

    test_id: str
    source_cps: list[str]
    target_cp: str
    function: str
    file: str
    fixture_deps: list[str] = []
    contract_under_test: str
    assertion: str
    gate: str

    @field_validator("test_id")
    @classmethod
    def validate_ct_id(cls, v: str) -> str:
        """Enforce CT-NNN format."""
        if not _CT_ID_RE.fullmatch(v):
            msg = f"test_id must match CT-NNN format, got '{v}'"
            raise ValueError(msg)
        return v


class SelfHealingEntry(BaseModel, frozen=True):
    """An entry in the plan's self-healing log."""

    tag: str
    iteration: int
    flag: str
    checkpoint: str
    description: str


class Plan(BaseModel):
    """Top-level plan container for plans/plan.yaml."""

    generated_from: list[str] = []
    validated: bool = False
    validated_date: str | None = None
    validated_note: str | None = None
    checkpoints: list[Checkpoint] = []
    connectivity_tests: list[ConnectivityTest] = []
    self_healing_log: list[SelfHealingEntry] = []


# ---------------------------------------------------------------------------
# Task file schemas (plans/tasks/CP-XX.yaml)
# ---------------------------------------------------------------------------


class StepProgress(BaseModel, frozen=True):
    """A single step completion marker in a task file."""

    step: str
    done: bool = False


class ExecutionFinding(BaseModel, frozen=True):
    """An execution finding recorded during sub-agent checkpoint work."""

    adjacent_file: str
    observation: str
    severity: Severity


class SeamEntry(BaseModel, frozen=True):
    """Seam context entry describing a component boundary."""

    component: str
    receives_di: list[str] = []
    key_failure_modes: list[str] = []
    external_terminal: str | None = None


class MissingCtSeam(BaseModel, frozen=True):
    """A connectivity test seam that is missing coverage."""

    ct_id: str
    seam: str
    status: str

    @field_validator("ct_id")
    @classmethod
    def validate_ct_id(cls, v: str) -> str:
        """Enforce CT-NNN format."""
        if not _CT_ID_RE.fullmatch(v):
            msg = f"ct_id must match CT-NNN format, got '{v}'"
            raise ValueError(msg)
        return v


class SeamComponent(SeamEntry, frozen=True):
    """Full seam component with layer and backlog references.

    Inherits component, receives_di, key_failure_modes, external_terminal
    from SeamEntry. Adds layer placement and backlog cross-references.
    """

    layer: int
    backlog_refs: list[str] = []

    @field_validator("layer")
    @classmethod
    def validate_layer(cls, v: int) -> int:
        """Enforce layer is 1, 2, or 3."""
        if v not in (1, 2, 3):
            msg = f"layer must be 1, 2, or 3, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("backlog_refs")
    @classmethod
    def validate_backlog_refs(cls, v: list[str]) -> list[str]:
        """Ensure all backlog_refs match BL-NNN format."""
        for bl_id in v:
            if not _BL_ID_RE.fullmatch(bl_id):
                msg = f"backlog_refs entry must match BL-NNN format, got '{bl_id}'"
                raise ValueError(msg)
        return v


class SeamsFile(BaseModel, frozen=True):
    """Top-level seams file container for plans/seams.yaml."""

    components: list[SeamComponent] = []
    missing_ct_seams: list[MissingCtSeam] = []


class TaskConnectivityTest(BaseModel, frozen=True):
    """Task-level CT spec -- omits topology fields (source_cps/target_cp)."""

    test_id: str
    function: str
    file: str
    fixture_deps: list[str] = []
    contract_under_test: str
    assertion: str
    gate: str

    @field_validator("test_id")
    @classmethod
    def validate_ct_id(cls, v: str) -> str:
        """Enforce CT-NNN format."""
        if not _CT_ID_RE.fullmatch(v):
            msg = f"test_id must match CT-NNN format, got '{v}'"
            raise ValueError(msg)
        return v


class TaskFile(BaseModel):
    """Top-level task file container for plans/tasks/CP-XX.yaml.

    Mutable -- io-execute updates step_progress and execution_findings.
    """

    id: str
    title: str
    feature: str
    workflow: str = "io-execute"
    objective: str
    acceptance_criteria: list[str] = []
    contract: str
    write_targets: list[str] = []
    context_files: list[str] = []
    gate_command: str = ""
    connectivity_tests: list[TaskConnectivityTest] = []
    refactor_commands: list[str] = []
    source: str | None = None
    execution_notes: str | None = None
    seam_context: list[SeamEntry] = []
    execution_findings: list[ExecutionFinding] = []
    step_progress: list[StepProgress] = []

    @field_validator("id")
    @classmethod
    def validate_cp_id(cls, v: str) -> str:
        """Enforce CP-NN or CP-NNR{n} format."""
        if not _CP_ID_RE.fullmatch(v):
            msg = f"id must match CP-NN or CP-NNR{{n}} format, got '{v}'"
            raise ValueError(msg)
        return v
