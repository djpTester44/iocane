# Canonical Artifacts

The architect-authored YAML triple plus the project-authored catalog. These are the source of truth -- sub-agent execution, validators, and remediation flows all bind against them.

| Artifact | Authored by | Answers |
|---|---|---|
| `plans/component-contracts.yaml` | `/io-architect` | What does each component contractually promise to do? |
| `plans/seams.yaml` | `/io-architect` | How do components fit together, and where does the system meet the outside world? |
| `plans/symbols.yaml` | `/io-architect` | Which identifiers must be spelled and typed identically across more than one CP? |
| `catalog.toml` | `/io-init` (greenfield seeding) + `/io-adopt` (brownfield seeding) + operator review | Which bounded contexts (data_stores, external_systems, user_surfaces, nfr_axes) does the project span? |
| `tests/contracts/test_*.py` | `/io-wire-tests` (CDT Author spawn) | What does each contract surface require from the implementation? |
| `tests/connectivity/test_*.py` | `/io-wire-tests` (CT Author spawn) | Does each seam integration point connect correctly end-to-end? |
| `.iocane/wire-tests/eval_<id>.yaml` | `/io-wire-tests` (Critic spawn) | How well does the test implementation match its contract specification? |

Schema shape and field-level validators live in `.claude/scripts/schemas.py`. This doc covers purpose and scope -- what belongs in each artifact, what doesn't, and who reads it.

---

## component-contracts.yaml

**Purpose.** Per-component design surface. Each component declares its identity, its dependencies, what it must and must not do, the contract surface it exposes, and which roadmap features it supports.

**Belongs:**

- One entry per component
- Behavioral commitments (`responsibilities` -- verb prose; `must_not`)
- Bounded-context citations (`domain_concerns` -- typed `<category>.<entry_name>` references into `catalog.toml`; orthogonal to `responsibilities` per `decisions.md` D-13; consumed by `validate_crc_budget.py` MAX_DOMAIN_CONCERNS cap)
- Component-level raises-list (`raises`)
- Roadmap traceability (`features`)
- Composition-root flag for entrypoint-tier components

**Does not belong:**

- Layer assignments (integration-graph facts -> `seams.yaml`)
- DI wiring (-> `seams.yaml` `injected_contracts`)
- External-system terminals (-> `seams.yaml` `external_terminal`)
- Cross-CP shared identifiers (-> `symbols.yaml`)

**Authored by:** `/io-architect`, `/auto-architect` (under capability grant).
**Read by:** `/io-checkpoint`, `/io-execute`, `/validate-plan`, `/io-review`, `/doc-sync`.

---

## seams.yaml

**Purpose.** Integration map across components. Each entry describes how a component connects to the rest of the system: its layer position, what it receives via DI, what failure modes it can propagate, and whether it touches external terminals.

**Belongs:**

- Layer assignment (1=Foundation, 2=Utility, 3=Domain, 4=Entrypoint)
- DI declarations (`injected_contracts` -- Protocol names injected from a composition root)
- Failure-mode catalogue per component (`key_failure_modes`)
- External terminals (`external_terminal`) -- network, filesystem, queues, third-party APIs
- CT coverage gaps (`missing_ct_seams`) surfaced by `/io-review`

**Does not belong:**

- Component behavioral surface (-> `component-contracts.yaml`)
- Cross-CP shared identifiers (-> `symbols.yaml`)

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

## catalog.toml

**Purpose.** Project-authored enumeration of bounded contexts the project spans. Citation target for `ComponentContract.domain_concerns` typed `<category>.<entry_name>` references; consumed by `validate_crc_budget.py` to enforce the `MAX_DOMAIN_CONCERNS` cap (R3 catalog-citation count per `decisions.md` D-13).

**Belongs:**

- Four categories: `data_stores`, `external_systems`, `user_surfaces`, `nfr_axes`
- One entry per concrete bounded context the project spans
- `external_systems` entries carry an optional `trust_boundary: bool` flag. The flag is a forward-looking structured-index mirror of the `roadmap.md` Trust Edges section, agent-set during catalog population to mirror `TE-NN` entries authored in the same workflow run (true when the entry's name resolves to the owning component or backing service of a roadmap TE; false otherwise). The flag is a structured-index optimization for the Phase 1 roadmap-tier trust-edge gate; it is NOT authority -- the `roadmap.md` Trust Edges section remains source of truth, and `validate_trust_edge_chain.py` does not read the flag.

**Does not belong:**

- Behavioral prose (-> `component-contracts.yaml` `responsibilities`)
- Trust-edge declarations as first-class authority (-> `roadmap.md` Trust Edges)

**Authored by:** `/io-adopt` Step 4 (brownfield seeding from `current-state.md` + PRD NFRs) or `/io-init` Step C via `scaffold-greenfield.sh` (greenfield template copy); operator review before `/io-clarify` is mandatory in both paths.

**Read by:** `validate_crc_budget.py` (distinct-citation count for `MAX_DOMAIN_CONCERNS`); future `/io-architect` integration may consume the typed citations directly.

**Kind enums:** allowed `kind` values are unioned from `.claude/catalog-kinds.toml` (harness defaults) + optional `./catalog-kinds.local.toml` (project additive extension; gitignored).

---

## tests/contracts/test_*.py

**Purpose.** Contract-Driven Tests (CDTs). Each test file validates that a component's implementation conforms to the contract surface declared in `component-contracts.yaml` -- method signatures, parameter types, exception raises, and behavioral invariants.

**Belongs:**

- One test file per component under test
- Parametrized test cases covering all declared `raises` exception paths
- Inline collaborator mocking via `unittest.mock.Mock(spec=[...method names...])` per `component-contracts.yaml` collaborator declarations (no shared module imports; CT Author reads CDT files to mirror mock construction shape).
- Assertions on return type, parameter name, and exception wording
- Four evaluation axes (`payload_shape_covered`, `invariants_asserted`, `collaborator_mocks_speced`, `raises_coverage_complete`)

**Does not belong:**

- Integration-point testing (-> `tests/connectivity/test_*.py`)
- Cross-component seam validation (-> CT)
- Cross-test shared fixture modules (rev 5 dropped S1 fixture-builders; mocks are inline per spec(method-name) at the test-file tier)

**Authority:** `io-wire-tests.cdt` capability template (write scope: `tests/contracts/test_*.py`).
**Authored by:** CDT Author spawn (`spawn-test-author.sh --target-type cdt`).
**Read by:** CDT Critic, CT Author (mock-factory pattern reuse), `/io-checkpoint` (slicing for CT generation).
**Spec:** `plans/v5-meso-pivot/wire-tests-payload-contracts.md` Author contract (D-09).

---

## tests/connectivity/test_*.py

**Purpose.** Connectivity Tests (CTs). Each test file validates that seam integration points described in `seams.yaml` connect correctly end-to-end: dependency injection wiring, external-terminal mocking, failure-mode propagation, and cross-component data flow.

**Belongs:**

- One test file per integration point / seam
- Parametrized test cases covering each declared `key_failure_modes` per component
- DI wiring validation (collaborators injected correctly, no missing dependencies)
- External-terminal mocking via inline `Mock(spec=[...])` constructions consistent with the matching CDT files (`cdt_ct_mock_spec_consistent` axis; pattern-consistency at the spec(method-name) tier, not shared-module-import).
- Three evaluation axes (`seam_fan_coverage`, `cdt_ct_mock_spec_consistent`, `integration_path_asserted`)

**Does not belong:**

- Single-component contract validation (-> `tests/contracts/test_*.py`)
- Component behavioral semantics (belongs in CDT)

**Precondition:** Matching CDT eval YAMLs must have STATUS=PASS (D-20).

**Authority:** `io-wire-tests.ct` capability template (write scope: `tests/connectivity/test_*.py`).
**Authored by:** CT Author spawn (`spawn-test-author.sh --target-type ct`).
**Read by:** CT Critic, `/io-checkpoint` (slicing for further wave generation).
**Spec:** `plans/v5-meso-pivot/wire-tests-payload-contracts.md` Author contract (D-09).

---

## .iocane/wire-tests/eval_<id>.yaml

**Purpose.** Critic EvalReport. Each report evaluates how well a test file (CDT or CT) matches its contract specification. Structured evaluation across multiple axes with a three-state verdict (PASS / FAIL / AMBIGUOUS).

**Belongs:**

- STATUS field (one of PASS, FAIL, AMBIGUOUS)
- Axis-level evaluations (4 axes for CDT: signature, behavior, exception-path coverage, mocking-harness; 3 axes for CT: DI correctness, seam resilience, terminal-isolation)
- `critique_notes` (cross-field validator enforces coupling with STATUS and axis verdicts)
- Evidence citations tying findings back to specific test assertions or mock-factory patterns
- Author retry context (findings surface in `/io-wire-tests` step for Author decision)

**Does not belong:**

- Patch recommendations (Critic surfaces findings; Author decides revision shape)
- Test execution results (test runs produce pytest output, separate channel)

**Schema:** `EvalReport` (Pydantic, `frozen=True`, `extra="forbid"`; defined in `.claude/scripts/schemas.py`).

**Authority:** `io-wire-tests.critic` capability template (write scope: `.iocane/wire-tests/eval_*.yaml`).
**Produced by:** Critic spawn (`spawn-test-critic.sh`).
**Read by:** Orchestrator (`run_actor_critic_loop.sh`), Author retry path, `run_critic_audit.py`.
**Spec:** `plans/v5-meso-pivot/wire-tests-payload-contracts.md` Critic contract.

---

## Authoring sequence

The three architect-authored artifacts are co-authored by `/io-architect` as a single design pass. Step G runs five deterministic gates (CRC budget, symbols coverage, symbol-conflict detection, path-references, trust-edge chain). Step H runs the design-evaluator subprocess single-pass per architect attempt (R2-narrow); the evaluator emits findings or PASS and exits, then the architect halts at Step I with findings + canonical artifacts surfaced. The human approval gate at Step I triages findings and decides next action (approve / in-place correction / upstream revision request); each re-attempt is a fresh /io-architect invocation, not an auto-loop (D-04 clause-5 option a).

Once approved, the canonical set is the binding source of truth. Modifications outside `/io-architect` (or `/auto-architect` under capability grant) trigger reset hooks that flip downstream validation stamps to false, forcing re-architect on any post-blessing mutation. See `.claude/docs/enforcement-mapping.md` for the full reset chain.
