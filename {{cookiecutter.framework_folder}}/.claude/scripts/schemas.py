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

    Appendix A §A.3a: ``injected_contracts`` is the canonical field for
    the contract-level DI graph. ``receives_di`` is a deprecated alias
    carrying collaborator component names from pre-A.3 seams files;
    readers migrating the graph to contract names should prefer
    ``injected_contracts`` and fall back to ``receives_di`` only when
    the new field is empty.
    """

    component: str
    receives_di: list[str] = []
    injected_contracts: list[str] = []
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


ALLOWED_LAYERS: frozenset[int] = frozenset({1, 2, 3, 4})
FOUNDATION_LAYER: int = 1
COMPOSITION_ROOT_LAYER: int = 4
# Layers counted toward the composition-root decomposition cap (A.1c):
# excludes foundation (nothing below to wire) and composition roots
# themselves (excluded per io-architect.md A.1c prose).
CAP_COUNTED_LAYERS: frozenset[int] = (
    ALLOWED_LAYERS - {FOUNDATION_LAYER, COMPOSITION_ROOT_LAYER}
)


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
        """Enforce layer membership in ALLOWED_LAYERS."""
        if v not in ALLOWED_LAYERS:
            msg = f"layer must be one of {sorted(ALLOWED_LAYERS)}, got {v}"
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

_PY_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_RAISES_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


class ComponentContract(BaseModel, frozen=True):
    """A single component entry in plans/component-contracts.yaml.

    Behavioral commitments live at the component layer: ``responsibilities``
    name what the component owns; ``raises`` declares the component-level
    exception surface (bare class names like ``RouteNotFound`` or dotted
    stdlib names like ``subprocess.CalledProcessError``). Each name in
    ``raises`` must resolve to a Symbol of ``kind=exception_class`` in
    ``plans/symbols.yaml`` (enforced by ``validate_symbols_coverage.py``);
    builtin and stdlib-module exceptions are skipped.
    """

    file: str
    collaborators: list[str] = []
    composition_root: bool = False
    responsibilities: list[str] = []
    must_not: list[str] = []
    features: list[str] = []
    raises: list[str] = []

    @field_validator("file")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Enforce non-empty .py path."""
        if not v or not v.endswith(".py"):
            msg = f"file must be a non-empty .py path, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("raises")
    @classmethod
    def validate_raises_names(cls, v: list[str]) -> list[str]:
        """Enforce identifier-safe exception class names (dotted allowed)."""
        for name in v:
            if not _RAISES_NAME_RE.fullmatch(name):
                msg = (
                    f"raises entry must be an identifier-safe class name "
                    f"(dotted module paths allowed), got '{name}'"
                )
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
    ERROR_MESSAGE = "error_message"


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
    # Architect-authored: component names that reference this symbol.
    # Populated at /io-architect Step F from CRC collaboration analysis.
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
            SymbolKind.EXCEPTION_CLASS: ("parent", "declared_in"),
            SymbolKind.SHARED_TYPE: ("type_expr", "declared_in"),
            SymbolKind.FIXTURE: ("fixture_scope",),
            SymbolKind.ERROR_MESSAGE: ("message_pattern",),
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

    @model_validator(mode="after")
    def check_declared_in_zone(self) -> "Symbol":
        """Enforce runtime-symbol placement in a legitimate import zone.

        exception_class and shared_type manifest as concrete Python class
        bodies at runtime. They live either under the project's ``src/``
        tree OR in an external installable package (``pydantic``,
        ``sqlalchemy.orm``, etc.). ``declared_in`` presence is enforced
        by ``check_kind_required_fields``; this validator constrains
        the zone of any value that is set.

        Accepted shapes:
          * ``src/...`` -- project filesystem path.
          * bare module name without slashes (``pydantic``,
            ``sqlalchemy.orm``) -- external package.

        Rejected shapes:
          * path-shaped without ``src/`` prefix (``domain/types.py``,
            ``../escape``, absolute paths) -- catches typos and escapes.
          * dotted-src forms (``src.domain.types``) -- the most likely
            intuitive authoring mistake; rejected with guidance toward
            the filesystem form.
        """
        if self.kind not in (SymbolKind.EXCEPTION_CLASS, SymbolKind.SHARED_TYPE):
            return self
        declared = self.declared_in
        if declared is None:
            return self
        normalized = declared.replace("\\", "/")
        has_slash = "/" in normalized
        if has_slash and not declared.startswith("src/"):
            msg = (
                f"Symbol of kind {self.kind.value} with path-shaped "
                f"declared_in must start with 'src/'; for external "
                f"packages use a bare module name (e.g., 'pydantic', "
                f"'sqlalchemy.orm'), got '{declared}'"
            )
            raise ValueError(msg)
        if not has_slash and declared.startswith(("src.", "tests.")):
            msg = (
                f"Symbol of kind {self.kind.value} has dotted-path-style "
                f"declared_in ('{declared}'); project symbols use the "
                f"filesystem form ('src/.../file.py'), external packages "
                f"use a bare module name (no 'src.' prefix)"
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
_COMPONENT_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class InvariantKind(StrEnum):
    """Taxonomy of per-component test invariants.

    Tracks the same observable axes used by CT assertion validation but
    at the component-contract layer rather than the seam layer.
    """

    CALL_BINDING = "call_binding"
    CARDINALITY = "cardinality"
    ERROR_PROPAGATION = "error_propagation"
    STATE_TRANSITION = "state_transition"
    PROPERTY = "property"
    ADVERSARIAL = "adversarial"


class TestInvariant(BaseModel, frozen=True):
    """A single behavioral invariant scoped to a component contract.

    ``method`` is optional and architect-supplied: when an
    ``error_propagation`` invariant covers a specific component-level
    raises entry, the architect may populate ``method`` from impl
    knowledge to anchor the invariant to a method scope. No upstream
    YAML supplies method context, so the field stays None unless the
    architect chooses to populate it.
    """

    __test__: ClassVar[bool] = False

    id: str
    kind: InvariantKind
    description: str
    pass_criteria: str
    method: str | None = None

    @field_validator("id")
    @classmethod
    def validate_inv_id(cls, v: str) -> str:
        """Enforce INV-NNN format."""
        if not _INV_ID_RE.fullmatch(v):
            msg = f"id must match INV-NNN format, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("method")
    @classmethod
    def validate_method_name(cls, v: str | None) -> str | None:
        """Enforce lowercase Python-identifier method name when present."""
        if v is None:
            return v
        if not _PY_IDENT_RE.fullmatch(v):
            msg = (
                f"method must be lowercase identifier-safe when present, "
                f"got '{v}'"
            )
            raise ValueError(msg)
        return v


class TestPlanEntry(BaseModel, frozen=True):
    """Per-component test authoring spec.

    One entry per component contract. The downstream test author reads
    this entry and produces one or more contract tests covering each
    invariant. ``component`` matches the dict key in
    ``TestPlanFile.entries`` (and the component name in
    ``ComponentContractsFile.components``); the redundancy is
    deliberate so a TestPlanEntry remains self-describing when passed
    individually to downstream consumers.
    """

    __test__: ClassVar[bool] = False

    component: str
    invariants: list[TestInvariant]

    @field_validator("component")
    @classmethod
    def validate_component_name(cls, v: str) -> str:
        """Enforce identifier-safe component name."""
        if not _COMPONENT_NAME_RE.fullmatch(v):
            msg = f"component name must be identifier-safe, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("invariants")
    @classmethod
    def validate_non_empty_invariants(
        cls, v: list[TestInvariant]
    ) -> list[TestInvariant]:
        """Reject empty invariants list.

        An entry with zero invariants silently bypasses the
        completeness gate -- the entry exists, so the component counts
        as covered, but no behavioral claim is asserted. The entry
        must be either populated or removed.
        """
        if not v:
            msg = "invariants must contain at least one TestInvariant"
            raise ValueError(msg)
        return v


class TestPlanFile(BaseModel):
    """Top-level container for plans/test-plan.yaml.

    ``entries`` is a component-keyed dict mirroring
    ``ComponentContractsFile.components``: each key is a component name
    and maps to one TestPlanEntry. The dict key is the source of truth
    for naming; the model_validator below verifies the entry's own
    ``component`` field matches its key, catching construction-bypass
    drift.
    """

    __test__: ClassVar[bool] = False

    validated: bool = False
    validated_date: str | None = None
    validated_note: str | None = None
    entries: dict[str, TestPlanEntry] = {}

    @model_validator(mode="after")
    def check_entry_keys_match_components(self) -> "TestPlanFile":
        """Enforce dict key == entry.component for every entry."""
        for key, entry in self.entries.items():
            if entry.component != key:
                msg = (
                    f"entries['{key}'].component is '{entry.component}'; "
                    "dict key must match the entry's component field"
                )
                raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Findings (.iocane/findings/<role>-<timestamp>.yaml)
# ---------------------------------------------------------------------------


class FindingRole(StrEnum):
    """The harness role emitting a finding."""

    TEST_AUTHOR = "test_author"
    GENERATOR = "generator"
    EVALUATOR = "evaluator"
    EVALUATOR_DESIGN = "evaluator_design"


ROLE_TO_DEFECT_KINDS: dict[FindingRole, frozenset[str]] = {
    FindingRole.EVALUATOR_DESIGN: frozenset(
        {
            "design_tautological_invariant",
            "design_vague_raises_trigger",
            "design_symbol_classification_drift",
            "design_missing_adversarial_coverage",
            "design_duplicate_symbols",
            "design_over_abstracted_param_type",
            "design_impl_leaking_docstring",
            "design_responsibility_cohesion_drift",
        }
    ),
}


class RootCauseLayer(StrEnum):
    """The layer whose defect produced the finding and owns the fix.

    Remediation flows downward from the named layer: a yaml_contract
    fix re-drives test authorship and downstream; a test_authorship
    fix re-drives only the test layer; an impl fix is local to the
    affected component.
    """

    YAML_CONTRACT = "yaml_contract"
    TEST_AUTHORSHIP = "test_authorship"
    IMPL = "impl"


class FindingContext(BaseModel, frozen=True):
    """Locator fields pointing to the subject of the finding.

    At least one locator must be populated so the human remediator
    can identify where the defect surfaced. A finding with no
    locators is orphaned and cannot be routed.
    """

    cp_id: str | None = None
    test_file: str | None = None

    @model_validator(mode="after")
    def check_at_least_one_locator(self) -> "FindingContext":
        """Reject a context with no populated locator."""
        if not any((self.cp_id, self.test_file)):
            msg = (
                "FindingContext requires at least one of "
                "cp_id, test_file"
            )
            raise ValueError(msg)
        return self


class FindingDiagnosis(BaseModel, frozen=True):
    """Structured reasoning: what is wrong, where, why."""

    what: str
    where: str
    why: str


class FindingRemediation(BaseModel, frozen=True):
    """Actionable remediation path scoped to a root-cause layer."""

    root_cause_layer: RootCauseLayer
    fix_steps: list[str]
    re_entry_commands: list[str]

    @field_validator("fix_steps", "re_entry_commands")
    @classmethod
    def validate_non_empty(cls, v: list[str]) -> list[str]:
        """Reject empty ordered lists.

        An empty remediation list signals nothing actionable to the
        human, leaving the finding orphaned at the halt point.
        """
        if not v:
            msg = "must contain at least one entry"
            raise ValueError(msg)
        return v


class Finding(BaseModel, frozen=True):
    """A halt-to-human finding emitted by a harness role.

    Replaces the AMEND signal / retry loop: the finding IS the
    remediation workflow. A human reads remediation.fix_steps,
    applies them, then runs remediation.re_entry_commands to
    re-drive the pipeline from the root-cause layer downward.

    defect_kind is a short slug (e.g., ``symbol_gap``,
    ``contract_silent``). Enumeration deferred to Phase 6 when
    emitters are wired up and the taxonomy solidifies.
    """

    role: FindingRole
    context: FindingContext
    defect_kind: str
    affected_artifacts: list[str]
    diagnosis: FindingDiagnosis
    remediation: FindingRemediation

    @model_validator(mode="after")
    def validate_design_role_diagnosis_why(self) -> "Finding":
        """Reject empty diagnosis.why on EVALUATOR_DESIGN findings.

        Semantic findings carry the agent's reasoning in
        diagnosis.why. An empty value strips the human remediator's
        only context for the call. Legacy roles are unconstrained
        until A5/A6 introduce additional semantic roles.
        """
        if (
            self.role is FindingRole.EVALUATOR_DESIGN
            and not self.diagnosis.why.strip()
        ):
            msg = (
                "diagnosis.why must be non-empty for "
                f"role {self.role.value}"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_defect_kind(self) -> "Finding":
        """Reject defect_kind not in the allowed set for the role.

        Strict set-membership at the data-model layer catches typos,
        unauthorized novel slugs, and rubric drift at construction
        time. Roles absent from ROLE_TO_DEFECT_KINDS skip the check
        (legacy free-form behavior; A5/A6 register their own slug
        sets when their roles land).
        """
        allowed = ROLE_TO_DEFECT_KINDS.get(self.role)
        if allowed is not None and self.defect_kind not in allowed:
            msg = (
                f"defect_kind {self.defect_kind!r} not in allowed "
                f"set for role {self.role.value}"
            )
            raise ValueError(msg)
        return self


class FindingFile(BaseModel, frozen=True):
    """Container for .iocane/findings/<role>-<timestamp>.yaml.

    One file per role emission; may carry multiple related findings
    surfaced together.
    """

    findings: list[Finding]

    @field_validator("findings")
    @classmethod
    def validate_non_empty(cls, v: list[Finding]) -> list[Finding]:
        """Reject zero-finding files.

        A file with an empty findings list is indistinguishable from a
        stale sentinel and provides no signal for the human remediator.
        """
        if not v:
            msg = "FindingFile must contain at least one Finding"
            raise ValueError(msg)
        return v
