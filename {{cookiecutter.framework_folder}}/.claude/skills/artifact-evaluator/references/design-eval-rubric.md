# Design Evaluator Rubric

Eight reasoning categories applied semantically against
io-architect's canonical three-artifact set:

- `plans/component-contracts.yaml` -- `ComponentContractsFile` /
  `ComponentContract` (component-level `raises: list[str]`,
  `responsibilities`, `key_features`)
- `plans/seams.yaml` -- `SeamsFile` / `SeamComponent`
  (`injected_contracts`, layer assignment, external-terminal status)
- `plans/symbols.yaml` -- `SymbolsFile` / per-symbol metadata
  (`declared_in`, `kind`, exception classes)

Each category below names a `defect_kind` slug. The slugs are
schema-validated against `ROLE_TO_DEFECT_KINDS[EVALUATOR_DESIGN]`
in `.claude/scripts/schemas.py`. **A slug here that is missing from
the schema map breaks Finding construction at runtime** -- the rubric
prose and the schema map must be co-authored.

The categories are advisory: emit a finding when reasoning surfaces a
defect. Never halt; never modify artifacts. The architect reads
findings, revises, and re-runs.

---

## R6-Narrow Residue Scope (Phase 1)

These eight categories are the R6-narrow residue: defect classes the
A5 (CDT) and A6 (CT) meso-tier evaluators provably cannot reach.
A5/A6 validate implementation-to-contract conformance via axes:
payload-shape coverage, per-contract-field invariant assertions,
mock-factory completeness, raises-coverage parity. None of those axes
reach specification-quality defects (tautological invariant CONTENT,
trigger SPECIFICITY, symbol CLASSIFICATION correctness, adversarial
DECLARATION, symbol-name drift, TYPE ABSTRACTION level, docstring
COUPLING, or cohesion GRAPH SHAPE). All eight categories remain as
the narrowed design-tier critic's responsibility under R6-narrow.

**Category 4 (`design_missing_adversarial_coverage`) is INVARIANT
(non-trimmable in Phase 1).** Per decisions.md D-03 alpha: trim
flexibility applies to all other categories; this axis is pinned
because the security-class defect (F3: missing adversarial coverage
on trust-boundary surfaces) must retain a semantic backstop alongside
the deterministic cross-artifact validator
(`validate_trust_edge_chain.py`). Do not remove this category in
Phase 1 breakout trim passes or future substage reviews without an
explicit D-NN supersession of D-03 alpha.

---

## 1. Tautological Invariants -- `design_tautological_invariant`

**What to look for.** A `ComponentContract.responsibilities` item
or `raises` trigger that restates a type signature, method name, or
framework-provided guarantee without asserting actual behavior. The
entry gives no behavioral constraint -- the implementation can satisfy
it without doing anything meaningful.

**Why it matters.** Tautological entries are silent contract holes.
They pass schema validation and look complete, but give the test
author nothing concrete to assert. The defect surfaces when
implementation diverges silently.

**Bad example** (in `plans/component-contracts.yaml`):

```yaml
components:
  router:
    responsibilities:
      - "router has a route() method"
      # The class already declares route -- restating it as a
      # responsibility gives the test nothing to assert.
```

**Good example.**

```yaml
components:
  router:
    responsibilities:
      - >-
        route() with an unknown destination raises UnknownRouteError;
        known destinations resolve to the registered handler before
        the handler is invoked.
```

---

## 2. Vague Raises Triggers -- `design_vague_raises_trigger`

**What to look for.** A `ComponentContract.raises[]` entry whose
trigger phrasing does not name a concrete precondition. Test authors
cannot bind a specific input to a specific exception -- they end up
asserting "raises X under some condition," which is unverifiable.

**Why it matters.** Component-level raises are the authoritative
input to the raises-coverage rubric (Plan B §-1.3). Vague triggers
let the test author write any test that produces the exception type
-- losing the documentation surface and the architect's intent.

**Bad example.**

```yaml
components:
  router:
    raises:
      - "ValidationError when input is bad"
```

**Good example.**

```yaml
components:
  router:
    raises:
      - "ValidationError when destination is empty string or None"
      - "ValidationError when destination contains path-traversal segments"
```

---

## 3. Suspicious Symbol Classifications -- `design_symbol_classification_drift`

**What to look for.** A `symbols.yaml` entry whose `kind` (function,
class, exception, etc.) or `declared_in` field disagrees with the
component-contracts.yaml usage of the same name. Drift between the
two files surfaces here because both are architect-authored at Step
F-pre / Step H-2c.

**Why it matters.** Symbol classification drives the test-author's
import paths and assertion targets. A symbol declared as a function
in symbols.yaml but used as a class constructor in
component-contracts.yaml will compile under static analysis and fail
at runtime against the actual implementation.

**Bad example.** `symbols.yaml` lists `RouteHandler` as
`kind: function` but `component-contracts.yaml` `router.collaborators`
uses it as a Protocol class.

**Good example.** Both files agree on the kind and the declaring
module path; cross-referencing the two yields no contradictions.

---

## 4. Missing Adversarial Coverage -- `design_missing_adversarial_coverage` [INVARIANT: non-trimmable in Phase 1]

**What to look for.** A `ComponentContract` whose
`responsibilities` describe a security-sensitive or
input-validation surface (auth checks, path resolution, deserialization,
url construction, sql, shell), but whose `raises` list contains zero
adversarial-input triggers.

**Why it matters.** The test surface ends up only covering happy
path. Adversarial inputs (malformed payloads, traversal sequences,
oversized strings, type confusion) don't have a corresponding raises
trigger, so the CDT critic can't request coverage. The defect ships.

**Bad example.** `component-contracts.yaml` `path_resolver`
component has responsibilities mentioning "resolve user-provided path
to absolute filesystem location" but no raises entry for traversal
inputs.

**Good example.** Same component lists raises like
`"PathTraversalError when resolved path escapes the configured root"`
with a trigger specific enough that a test author can construct an
adversarial input to exercise it.

### 4a. Trust-Edge Cross-Artifact Sub-Clause

**Additional axis: PRD Trust Edges -> contract raises -> symbols
Settings parameterization chain.** When a component is named in the
roadmap's Trust Edges section (structured sub-fields: `component`,
`attack_vectors`, `thresholds_settings`), verify the following chain
holds across the four-artifact set:

1. **Declaration present.** The Trust Edge declaration names this
   component explicitly with at least one `attack_vectors` entry and
   at least one `thresholds_settings` symbol.
2. **Raises chain complete.** The component's `raises` list in
   `component-contracts.yaml` includes at least one entry whose
   trigger text names an adversarial-rejection condition matching the
   declared `attack_vectors` (regex match on: `invalid`, `malformed`,
   `oversize`, `traversal`, `forbidden`, `unauthorized`, `tamper`,
   `replay`).
3. **Parameterization discipline.** The component's `responsibilities`
   and `raises` bodies do NOT contain bare numeric literals
   (threshold values, sizes, timeouts, counts) without an adjacent
   `Settings.<symbol>` reference, where the symbol name matches a
   `thresholds_settings` entry from the Trust Edge declaration.

**Why this sub-clause exists.** The deterministic validator
`validate_trust_edge_chain.py` (invoked at io-architect Step G)
mechanically checks chain presence and parameterization. This rubric
axis is the semantic backstop: it catches QUALITY gaps the
deterministic check cannot reach (a raises trigger that technically
names a condition but is so vague that no adversarial test can be
derived from it; a `thresholds_settings` symbol that exists but is
never used in the corresponding raises description). Emit a finding
when the chain is formally present but semantically inadequate.

---

## 5. Near-Duplicate Symbols -- `design_duplicate_symbols`

**What to look for.** Two `symbols.yaml` entries whose names differ
only in case, pluralization, underscore placement, or one-character
typo, and which both appear in the same component's contract surface.
The architect likely intended one symbol; the duplicate is
copy/paste drift.

**Why it matters.** Test authors will import one of the two; the
other appears unused at static-analysis time but is referenced in
prose. Drift compounds: every downstream rubric reads the wrong
symbol.

**Bad example.** `RouteRegistry` and `RouteRegistery` both declared
in symbols.yaml; `component-contracts.yaml` references the misspelled
form in one collaborator and the correct form in another.

**Good example.** One canonical symbol; all references aligned.

---

## 6. Over-Abstracted Parameter Types -- `design_over_abstracted_param_type`

**What to look for.** A `ComponentContract.responsibilities` or
`raises` description references a parameter type (or argument shape)
that is so abstract -- `Any`, `object`, `dict`, `Mapping[str, Any]` --
that the test author cannot construct a meaningful adversarial or
boundary case. The contract surface accepts everything; the test
surface checks nothing.

**Why it matters.** Over-abstracted types defeat both the type
checker and the test-design phase. The implementation can drift
arbitrarily within the abstract type's bounds without any test
catching the change.

**Bad example.** "router.route accepts a `dict` payload and dispatches
to the registered handler." The contract carries no schema; tests
can pass with `{}` or `{anything: anything}`.

**Good example.** The contract names a concrete `RoutePayload`
Protocol or a frozen dataclass with named fields; tests can construct
boundary values for each field.

---

## 7. Implementation-Leaking Docstrings -- `design_impl_leaking_docstring`

**What to look for.** A `ComponentContract.responsibilities` field
that describes HOW the component works (the algorithm, internal data
structure, library used) instead of WHAT it guarantees. The contract
surface should read like a user-facing API doc, not like a code
comment.

**Why it matters.** Implementation leakage couples the contract to
one implementation. A future refactor that preserves behavior but
changes the algorithm forces a contract rewrite -- which forces a
test rewrite -- which forces a regression hunt because the contract
"changed."

**Bad example.** "router.route uses a hash table to look up the
handler and falls back to a regex scan if the hash misses."

**Good example.** "router.route returns the handler registered for
the destination; lookup is O(1) amortized and deterministic across
identical inputs."

---

## 8. Responsibility Cohesion Drift -- `design_responsibility_cohesion_drift`

**What to look for.** A `ComponentContract.responsibilities` list
that bundles two or more unrelated concerns into one component --
e.g., "validate input, route the request, log the request, and
update the metric counter." The component spans multiple cohesion
boundaries; the test surface for any one concern is polluted by the
others.

**Why it matters.** Wide-cohesion components are integration tests
masquerading as unit tests. CDT becomes hard to author (every test
needs every collaborator); CT becomes redundant (the component is
already an integration). Composition-root components are an
exception (they wire collaborators by definition); flag for
non-composition-root components.

**Bad example.** Single component `request_handler` lists
responsibilities "parse JSON, validate against schema, dispatch to
handler, persist audit row, emit metric." Five cohesion boundaries;
only one component.

**Good example.** Five components, each with one responsibility;
the composition root wires them in sequence. The architect's CRC
budget calls this out (composition_root <=2 Layer-2/3 collaborators
per `validate_crc_budget.py`).

---

## Slug Catalog (schema-co-authored)

The eight `defect_kind` slugs below MUST match the frozenset at
`.claude/scripts/schemas.py` `ROLE_TO_DEFECT_KINDS[FindingRole.EVALUATOR_DESIGN]`.
All eight slugs are retained under the Phase 1 R6-narrow trim pass
(no retirements). The schema map is unchanged.

| Slug | Phase 1 disposition |
|---|---|
| `design_tautological_invariant` | KEEP -- A5 invariant-assertions axis does not reach spec-content quality |
| `design_vague_raises_trigger` | KEEP -- A5 raises-coverage parity does not reach trigger specificity |
| `design_symbol_classification_drift` | KEEP -- no A5/A6 cross-file symbol-classification axis |
| `design_missing_adversarial_coverage` | INVARIANT-PINNED (D-03 alpha; non-trimmable in Phase 1) |
| `design_duplicate_symbols` | KEEP -- no A5/A6 cross-artifact symbol-name drift axis |
| `design_over_abstracted_param_type` | KEEP -- A5 payload-shape axis works within a type's bounds, not against abstraction level |
| `design_impl_leaking_docstring` | KEEP -- A5/A6 cannot reach spec-prose coupling quality |
| `design_responsibility_cohesion_drift` | KEEP -- cohesion graph shape is unreachable by meso-tier conformance checks |

A new category requires a same-changeset addition to the schema map.
The Finding model_validator rejects unknown slugs at construction
time -- catching rubric drift before the file hits disk.

Retiring a slug requires: (1) a same-changeset edit removing it from
`ROLE_TO_DEFECT_KINDS[FindingRole.EVALUATOR_DESIGN]` in
`.claude/scripts/schemas.py`; (2) a D-NN decisions-log entry
documenting the retirement rationale and citing the A5/A6 axis that
supersedes it.
