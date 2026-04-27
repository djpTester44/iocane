# Canonical Artifacts

The four YAML files produced by `/io-architect` and consumed by every downstream workflow. These are the source of truth -- sub-agent execution, validators, and remediation flows all bind against them.

| Artifact | Answers |
|---|---|
| `plans/component-contracts.yaml` | What does each component contractually promise to do? |
| `plans/seams.yaml` | How do components fit together, and where does the system meet the outside world? |
| `plans/symbols.yaml` | Which identifiers must be spelled and typed identically across more than one CP? |
| `plans/test-plan.yaml` | What behavioral invariants must each component satisfy under test? |

Schema shape and field-level validators live in `.claude/scripts/schemas.py`. This doc covers purpose and scope -- what belongs in each artifact, what doesn't, and who reads it.

---

## component-contracts.yaml

**Purpose.** Per-component design surface. Each component declares its identity, its dependencies, what it must and must not do, the contract surface it exposes, and which roadmap features it supports.

**Belongs:**

- One entry per component
- Behavioral commitments (`responsibilities`, `must_not`)
- Component-level raises-list (`raises`)
- Roadmap traceability (`features`)
- Composition-root flag for entrypoint-tier components

**Does not belong:**

- Layer assignments (integration-graph facts -> `seams.yaml`)
- DI wiring (-> `seams.yaml` `receives_di`)
- External-system terminals (-> `seams.yaml` `external_terminal`)
- Cross-CP shared identifiers (-> `symbols.yaml`)
- Test invariants (-> `test-plan.yaml`)

**Authored by:** `/io-architect`, `/auto-architect` (under capability grant).
**Read by:** `/io-checkpoint`, `/io-execute`, `/validate-plan`, `/io-review`, `/doc-sync`.

---

## seams.yaml

**Purpose.** Integration map across components. Each entry describes how a component connects to the rest of the system: its layer position, what it receives via DI, what failure modes it can propagate, and whether it touches external terminals.

**Belongs:**

- Layer assignment (1=Foundation, 2=Utility, 3=Domain, 4=Entrypoint)
- DI declarations (`receives_di` for collaborator names; `injected_contracts` additionally for composition roots)
- Failure-mode catalogue per component (`key_failure_modes`)
- External terminals (`external_terminal`) -- network, filesystem, queues, third-party APIs
- CT coverage gaps (`missing_ct_seams`) surfaced by `/io-review`

**Does not belong:**

- Component behavioral surface (-> `component-contracts.yaml`)
- Cross-CP shared identifiers (-> `symbols.yaml`)
- Test invariants (-> `test-plan.yaml`)

**Authored by:** `/io-architect`, `/auto-architect`.
**Read by:** `/io-checkpoint` (CT generation), `/validate-plan` (DI wiring + `HARDCODED_DEPENDENCY` check), `/io-execute`, `/io-review`, `/io-ct-remediate`, `/task-recovery`.

---

## symbols.yaml

**Purpose.** Cross-CP identifier registry. Tracks every identifier that must be spelled and typed identically in more than one CP -- the subset of project vocabulary where divergence between CPs would corrupt downstream consumers.

**Belongs:**

- Settings fields read by more than one component
- Exception classes that cross a contract boundary
- Shared types (dataclass / TypedDict / Pydantic model) consumed by more than one CP
- Pytest fixtures referenced across more than one CP
- Literal exception messages whose wording is asserted by tests

**Does not belong:**

- Internal-to-one-component types or fixtures
- Identifiers not crossing a CP boundary
- Behavioral semantics (-> `component-contracts.yaml`)

**Authored by:** `/io-architect`, `/auto-architect`.
**Read by:** `/io-checkpoint` (`used_by_cps` backfill), `/validate-plan` (conflict detection), any downstream consumer needing to spell an identifier consistently.

Schema-mechanic detail (kind catalogue, `declared_in` zone rules, conflict detection): see `.claude/references/symbols-schema.md`.

---

## test-plan.yaml

**Purpose.** Behavioral-invariant manifest per component. Each component contract has one TestPlanEntry whose invariants describe what a conforming implementation must do. The Test Author writes tests to assert these invariants.

**Belongs:**

- One `TestPlanEntry` per component, keyed by component name in `TestPlanFile.entries` (a dict mirroring `ComponentContractsFile.components`)
- One or more `TestInvariant` items per entry: `id` (INV-NNN format), `kind`, `description`, `pass_criteria`, optional `method`
- Coverage of every component-level raises entry with at least one `error_propagation` invariant
- Coverage of contract postconditions (return shape, observable side effects, state transitions)
- Optional `TestInvariant.method` -- architect-supplied method scope when an invariant covers a specific raises entry

**Does not belong:**

- Implementation detail (the Test Author writes the test; the invariant states the claim)
- Tests for behavior outside the component's contract
- Component structural data (-> `component-contracts.yaml`)

**Authored by:** `/io-architect`, `/auto-architect`.
**Read by:** Test Author (CDT/CT authoring), `/validate-plan` (completeness check), `/io-checkpoint` (test-coverage scoping), `/io-review` (raises-coverage audit).

Schema-mechanic detail (InvariantKind catalogue, INV id format): see `.claude/references/test-plan-schema.md`.

---

## Authoring sequence

The four artifacts are co-authored by `/io-architect` as a single design pass. The artifact-evaluator runs against the complete 4-file set; if it finds violations, the architect revises and re-runs the evaluator. The human approval gate sees only an evaluator-passed design.

Once approved, the canonical set is the binding source of truth. Modifications outside `/io-architect` (or `/auto-architect` under capability grant) trigger reset hooks that flip downstream validation stamps to false, forcing re-architect on any post-blessing mutation. See `.claude/docs/enforcement-mapping.md` for the full reset chain.
