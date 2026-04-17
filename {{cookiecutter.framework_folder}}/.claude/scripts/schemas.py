"""Pydantic schemas for YAML-based harness data files.

Defines the canonical structure for plans/backlog.yaml, plans/plan.yaml,
plans/tasks/CP-XX.yaml, plans/seams.yaml, and plans/component-contracts.yaml.
Used by backlog_parser.py, plan_parser.py, task_parser.py, seam_parser.py,
contract_parser.py, hooks, and scripts for validation and serialization.
"""

import re
from enum import StrEnum
from typing import ClassVar

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

    def get_routing_prompt(self) -> str | None:
        """Return the routing prompt from the first Routed annotation with a prompt."""
        for ann in self.annotations:
            if ann.type == "Routed" and ann.prompt is not None:
                return ann.prompt
        return None

    def get_routed_to(self) -> str | None:
        """Return the routed-to CP-ID from the first Routed annotation."""
        for ann in self.annotations:
            if ann.type == "Routed":
                return ann.value
        return None


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

    # Appendix A §A.6d -- pre-existing artifacts referenced by this CP's
    # acceptance criteria or gate but not produced by it. Consumed by
    # validate_path_refs.py to suppress orphan warnings for files already
    # on disk at planning time.
    relies_on_existing: list[str] = []

    # Task-file bridging fields (populated by /io-checkpoint)
    acceptance_criteria: list[str] = []
    contract: str | None = None

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
    """A connectivity test specification in plans/plan.yaml.

    The CT file (``file`` field) is owned by ``target_cp``. Only the target
    checkpoint writes the test file and lists it in ``write_targets``.
    """

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


# Appendix A §A.4c -- behavior-observable keyword sets for CT assertions.
# Case-insensitive substring match; an assertion must contain at least one
# keyword from each set or the lexical validator emits a warning.
# The "invoke" stem matches "invoke", "invoked", and "invokes".
CT_ASSERTION_KEYWORDS: dict[str, frozenset[str]] = {
    "call binding": frozenset(
        {"called", "invoke", "with argument", "passes", "passed to"},
    ),
    "cardinality": frozenset(
        {"once", "exactly", "per", "times", "each", "for every"},
    ),
    "error propagation": frozenset(
        {"raises", "propagates", "re-raises", "error", "exception"},
    ),
}


def ct_assertion_warnings(assertion: str) -> list[str]:
    """Return the observable-set labels missing from a CT assertion.

    Soft lexical validator per Appendix A §A.4c. Checks the assertion
    string (case-insensitive substring match) for at least one keyword
    from each of three sets in ``CT_ASSERTION_KEYWORDS``: call binding,
    cardinality, and error propagation. Returns the labels of missing
    sets; an empty list means all three observables are covered. Never
    raises -- warnings are non-blocking and surfaced by
    ``validate_ct_assertions.py`` under ``/validate-plan``.
    """
    text = assertion.lower()
    return [
        label
        for label, keywords in CT_ASSERTION_KEYWORDS.items()
        if not any(kw in text for kw in keywords)
    ]


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
    """Seam context entry describing a component boundary.

    Appendix A §A.3a: ``receives_di_protocols`` is the canonical field for
    Protocol-level DI graph. ``receives_di`` is a deprecated alias carrying
    collaborator component names from pre-A.3 seams files; readers migrating
    the graph to Protocol names should prefer ``receives_di_protocols`` and
    fall back to ``receives_di`` only when the new field is empty.
    """

    component: str
    receives_di: list[str] = []
    receives_di_protocols: list[str] = []
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


# ---------------------------------------------------------------------------
# Component contracts (plans/component-contracts.yaml)
# ---------------------------------------------------------------------------


class ComponentContract(BaseModel, frozen=True):
    """A single component entry in plans/component-contracts.yaml."""

    file: str
    collaborators: list[str] = []
    composition_root: bool = False
    protocol: str = ""
    responsibilities: list[str] = []
    must_not: list[str] = []
    features: list[str] = []

    @field_validator("file")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Enforce non-empty .py path."""
        if not v or not v.endswith(".py"):
            msg = f"file must be a non-empty .py path, got '{v}'"
            raise ValueError(msg)
        return v


class ComponentContractsFile(BaseModel, frozen=True):
    """Top-level container for plans/component-contracts.yaml."""

    components: dict[str, ComponentContract] = {}


class TaskConnectivityTest(BaseModel, frozen=True):
    """Task-level CT spec -- omits topology fields (source_cps/target_cp).

    Present only in task files for the ``target_cp`` checkpoint. Source CPs
    do not receive CT entries in their task files.
    """

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


# ---------------------------------------------------------------------------
# Review staging schemas (plans/review-output.yaml)
# ---------------------------------------------------------------------------


class StagingItem(BaseModel, frozen=True):
    """A single finding in the review staging file."""

    tag: BacklogTag
    severity: Severity
    component: str
    files: list[str] = []
    issue: str
    detail: str
    contract_impact: str | None = None


class StagingGroup(BaseModel, frozen=True):
    """A group of findings from one review pass."""

    source: str
    date: str
    items: list[StagingItem]


class ReviewStaging(BaseModel):
    """Top-level staging container for plans/review-output.yaml."""

    groups: list[StagingGroup] = []


# ---------------------------------------------------------------------------
# Symbols registry (plans/symbols.yaml)
# ---------------------------------------------------------------------------

_SYMBOL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


class SymbolKind(StrEnum):
    """The declared kind of a cross-CP symbol.

    Any identifier whose exact spelling, type, or semantics must be
    consistent across more than one checkpoint is registered in
    plans/symbols.yaml under one of these kinds. Downstream generators
    read the registry instead of inferring.
    """

    SETTINGS_FIELD = "settings_field"
    EXCEPTION_CLASS = "exception_class"
    SHARED_TYPE = "shared_type"
    FIXTURE = "fixture"
    LOG_FORMAT = "log_format"
    ERROR_MESSAGE = "error_message"
    ARGUMENT_CONVENTION = "argument_convention"


class Symbol(BaseModel, frozen=True):
    """A single cross-CP symbol declaration.

    Kind-specific fields are optional at the model level; the
    ``check_kind_required_fields`` validator enforces which fields must
    be populated for each ``SymbolKind`` so downstream readers never
    encounter a half-declared symbol.
    """

    kind: SymbolKind
    declared_in: str | None = None
    type_expr: str | None = None
    env_var: str | None = None
    default: str | None = None
    parent: str | None = None
    message_pattern: str | None = None
    fixture_scope: str | None = None
    arg_order: list[str] | None = None
    # Architect-authored: component names that reference this symbol.
    # Populated at /io-architect Step H-6 from CRC collaboration analysis.
    used_by: list[str] = []
    # Checkpoint-backfilled: CP-IDs that touch this symbol. Populated at
    # /io-checkpoint after plan.yaml is authored, by walking each CP's
    # scope and matching component names against `used_by`. Stays empty
    # until checkpoint runs; downstream Tier-3 generators read this slice
    # to scope the symbol pack they receive.
    used_by_cps: list[str] = []

    @model_validator(mode="after")
    def check_kind_required_fields(self) -> "Symbol":
        """Enforce kind-appropriate field presence."""
        required: dict[SymbolKind, tuple[str, ...]] = {
            SymbolKind.SETTINGS_FIELD: ("type_expr", "env_var"),
            SymbolKind.EXCEPTION_CLASS: ("parent",),
            SymbolKind.SHARED_TYPE: ("type_expr",),
            SymbolKind.FIXTURE: ("fixture_scope",),
            SymbolKind.LOG_FORMAT: ("message_pattern",),
            SymbolKind.ERROR_MESSAGE: ("message_pattern",),
            SymbolKind.ARGUMENT_CONVENTION: ("arg_order",),
        }
        missing = [
            field
            for field in required[self.kind]
            if getattr(self, field) in (None, [])
        ]
        if missing:
            msg = (
                f"Symbol of kind {self.kind.value} requires: "
                f"{', '.join(missing)}"
            )
            raise ValueError(msg)
        return self


class SymbolsFile(BaseModel, frozen=True):
    """Top-level container for plans/symbols.yaml.

    Keyed by symbol name for O(1) lookup from downstream consumers.
    """

    symbols: dict[str, Symbol] = {}

    @field_validator("symbols")
    @classmethod
    def validate_symbol_names(cls, v: dict[str, Symbol]) -> dict[str, Symbol]:
        """Enforce identifier-safe symbol names."""
        for name in v:
            if not _SYMBOL_NAME_RE.fullmatch(name):
                msg = f"symbol name must be identifier-safe, got '{name}'"
                raise ValueError(msg)
        return v


# ---------------------------------------------------------------------------
# Test plan (plans/test-plan.yaml)
# ---------------------------------------------------------------------------

_INV_ID_RE = re.compile(r"^INV-\d{3}$")


class InvariantKind(StrEnum):
    """Taxonomy of per-Protocol-method test invariants.

    Tracks the same observable axes used by CT assertion validation but
    at the Protocol-method layer rather than the seam layer.
    """

    CALL_BINDING = "call_binding"
    CARDINALITY = "cardinality"
    ERROR_PROPAGATION = "error_propagation"
    STATE_TRANSITION = "state_transition"
    PROPERTY = "property"
    ADVERSARIAL = "adversarial"


class TestInvariant(BaseModel, frozen=True):
    """A single behavioral invariant on a Protocol method."""

    __test__: ClassVar[bool] = False

    id: str
    kind: InvariantKind
    description: str
    pass_criteria: str

    @field_validator("id")
    @classmethod
    def validate_inv_id(cls, v: str) -> str:
        """Enforce INV-NNN format."""
        if not _INV_ID_RE.fullmatch(v):
            msg = f"id must match INV-NNN format, got '{v}'"
            raise ValueError(msg)
        return v


class TestPlanEntry(BaseModel, frozen=True):
    """Per-Protocol-method test authoring spec.

    The Test Author reads this entry and produces one or more contract
    tests covering each invariant. If any invariant cannot be enforced
    because the Protocol is silent on it, the Test Author emits an
    AmendSignal instead of writing the test.
    """

    __test__: ClassVar[bool] = False

    protocol: str
    method: str
    invariants: list[TestInvariant]

    @field_validator("protocol")
    @classmethod
    def validate_protocol_path(cls, v: str) -> str:
        """Normalize and enforce a .pyi path anchored at interfaces/.

        Accepts ``interfaces/router.pyi``, ``./interfaces/router.pyi``,
        and Windows-style backslash paths; normalizes to a single
        canonical form so downstream lookups are not foiled by
        path-format drift between authoring environments.
        """
        v = v.replace("\\", "/")
        while v.startswith("./"):
            v = v[2:]
        idx = v.rfind("interfaces/")
        if idx >= 0:
            v = v[idx:]
        if not v.endswith(".pyi"):
            msg = f"protocol must be a .pyi path, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("invariants")
    @classmethod
    def validate_non_empty_invariants(
        cls, v: list[TestInvariant]
    ) -> list[TestInvariant]:
        """Reject empty invariants list.

        An entry with zero invariants silently bypasses the
        completeness gate -- the entry exists, so the method counts as
        covered, but no behavioral claim is asserted. The entry must
        be either populated or removed (with a # noqa: TEST_PLAN
        deferral on the .pyi method, which surfaces as an INFO line).
        """
        if not v:
            msg = "invariants must contain at least one TestInvariant"
            raise ValueError(msg)
        return v


class TestPlanFile(BaseModel):
    """Top-level container for plans/test-plan.yaml."""

    __test__: ClassVar[bool] = False

    validated: bool = False
    validated_date: str | None = None
    validated_note: str | None = None
    entries: list[TestPlanEntry] = []


# ---------------------------------------------------------------------------
# Amend signal (.iocane/amend-signals/<protocol>.yaml)
# ---------------------------------------------------------------------------


class AmendSignalKind(StrEnum):
    """Categories of Protocol under-specification a Test Author may surface."""

    MISSING_RAISES = "missing_raises"
    SILENT_RETURN_SEMANTICS = "silent_return_semantics"
    MISSING_PRECONDITION = "missing_precondition"
    UNDECLARED_COLLABORATOR = "undeclared_collaborator"
    SYMBOL_GAP = "symbol_gap"


class AmendSignal(BaseModel, frozen=True):
    """One under-specification the Test Author could not author tests for."""

    method: str
    invariant_id: str
    kind: AmendSignalKind
    description: str
    suggested_amendment: str

    @field_validator("invariant_id")
    @classmethod
    def validate_inv_id(cls, v: str) -> str:
        """Enforce INV-NNN format when present; allow empty for impl-level gaps.

        Tester signals always originate from a specific test-plan
        invariant and carry a non-empty INV-NNN id. Generator
        (io-execute) signals on impl-Protocol gaps may surface
        contract insufficiencies that are not tied to any single
        declared invariant -- e.g., a return shape the Protocol is
        silent on that multiple invariants incidentally depend upon.
        For those cases empty is the correct signal; inventing an
        INV-NNN to satisfy the schema would mislead the architect
        consumer into looking for a specific invariant that does
        not exist.
        """
        if v and not _INV_ID_RE.fullmatch(v):
            msg = f"invariant_id must match INV-NNN format or be empty, got '{v}'"
            raise ValueError(msg)
        return v


class AmendSignalFile(BaseModel, frozen=True):
    """Structured payload written by Test Author when it cannot proceed.

    One file per Protocol, at ``.iocane/amend-signals/<protocol>.yaml``.
    Consumed by ``handle_amend_signal.py`` which re-enters the architect
    amend sub-loop until the attempt counter exceeds the configured cap.
    """

    protocol: str
    attempt: int = 1
    signals: list[AmendSignal]

    @field_validator("protocol")
    @classmethod
    def validate_protocol_path(cls, v: str) -> str:
        """Enforce a .pyi path inside interfaces/."""
        if not v.endswith(".pyi"):
            msg = f"protocol must be a .pyi path, got '{v}'"
            raise ValueError(msg)
        return v
