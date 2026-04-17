# CT-Author Rules (Primary Flow)

Reference loaded by `io-ct-author.md` Step 4. Governs CT body generation
at the ct-writer stage, *before* target impl exists. Remediation flow
(`io-ct-remediate.md`) uses a different contract -- see that command
file; this reference does not govern it.

---

## Flow Context

The target checkpoint's impl does not exist yet. The CT file will fail
collection (import error) or fail assertion once written. That is the
expected pre-generator state. The generator stage takes the CT RED to
GREEN -- not this session.

Running the CT gate during ct-writer is not authorized. Creating
skeleton impl in `src/` to silence an import error is forbidden.

---

## Source of Truth

The authoritative CT spec is `plans/plan.yaml`. Each CT entry carries
the fields below; they are already projected onto the task file's
`connectivity_tests` list for the target CP.

| Field | Role |
|-------|------|
| `test_id` | CT-NNN identifier; cite in the test docstring |
| `function` | Test function name (exact match, no renaming) |
| `file` | Write path (must match `task.connectivity_tests[].file`) |
| `fixture_deps` | Fixture names the test body uses |
| `contract_under_test` | `interfaces/<protocol>.pyi :: <Protocol>.<method>` |
| `assertion` | Three-observable body; see below |
| `gate` | Never run here; recorded for generator/evaluator |

---

## Assertion Structure (three-observable rule)

Per `io-checkpoint.md` Appendix A.4a, every CT assertion names three
observables. The test body must map each to at least one assertion:

1. **Call binding** -- which upstream method is invoked and with which
   argument(s). Use `.call_args` / `assert_called_with(...)`.
2. **Call cardinality** -- how many invocations per downstream
   operation. Use `.call_count` / `assert_called_once()`.
3. **Error propagation** -- downstream behavior when the upstream
   raises each of its declared exceptions. Use `pytest.raises(...)`.

Every Protocol `Raises:` on the source side named in the CT spec's
`assertion:` field must be exercised by at least one branch in the
test body. Entries annotated `[DEFERRED: <reason>]` in the spec are
skipped with an explicit comment; do not invent assertions for them.

---

## Source Mocking Rule (primary-flow divergence from remediate)

Every source-side Protocol listed in `fixture_deps:` must be
**spy-capable**. Accepted forms:

- `unittest.mock.MagicMock(spec=<ProtocolName>)`
- `pytest-mock`'s `mocker.Mock(spec=<ProtocolName>)` or `mocker.spy(...)`
- Hand-rolled stub class that records `.call_args`, `.call_count`,
  `.called`

The source Protocol type is imported from `interfaces.<stem>` solely
for the `spec=` argument. Source impl MUST NOT be imported -- it may
not exist yet, and even when it does, importing it would couple the
CT to internals the seam does not expose.

The target component is imported real, from `src.<path>`. The CT
exercises the target against the spy-mocked source collaborator.

---

## Fixture Discipline

- Fixture names in the test body match `fixture_deps:` exactly.
- Identity-only fixtures (a plain factory returning a fixed value, a
  dataclass with no call-recording surface) are rejected per
  `io-checkpoint.md` Appendix A.4b. If the spec lists
  `stub_<name>_returning_x`, that is an architect-level defect --
  HALT (see failure mode below) rather than author against it.
- DI composition-root seams (A.3c) override via the framework surface
  (`app.dependency_overrides[...]` for FastAPI, provider factory
  swap for Typer). The override target is the Protocol, not the
  concrete impl.

---

## Write Location

- Target: `tests/connectivity/*.py`, per each CT's `file:` field in
  `task.connectivity_tests`.
- Never `tests/contracts/` -- Tier-1-owned by the Test Author.
- Never `src/`, never `plans/*`, never `interfaces/*` (architect-owned).
  Any such write triggers reset hooks and invalidates downstream
  validation stamps during parallel dispatch.

One test function per CT. One CT per file is the default shape (CT
file naming already reflects one-seam-per-file); multiple functions
per file only when `task.connectivity_tests` lists multiple CTs for
the same `file:` path.

---

## Imports

```python
from interfaces.<source_stem> import <SourceProtocol>  # for spec=
from src.<target_path> import <TargetClass>             # real target
```

The `interfaces/exceptions.pyi` and `interfaces/models.pyi` sibling
stubs may be imported for exception classes and shared types.

---

## Forbidden

- `assert True` placeholders.
- Mocks without cardinality or call-binding assertions.
- Imports from `src/<source_path>` (the source impl).
- Skeleton impl creation in `src/` to silence import errors.
- Running `pytest` / the CT gate.
- Writing anything outside `tests/connectivity/<your CT file>`.
- Emitting `.iocane/amend-signals/*.yaml` -- no AMEND channel at this
  tier.

---

## Failure Mode (HALT, no AMEND)

If any CT spec field is ambiguous, contradictory, or references an
unresolvable fixture or non-existent Protocol method, HALT with a
structured error naming the defective CT-IDs. Do NOT emit an AMEND
signal. Do NOT author an approximate test.

CT-signature defects are architect-level issues that the architect's
`H-post-validate` gates should have caught upstream. Surfacing them
here routes the defect back for re-architect; the AMEND loop is
Protocol-scoped (tester domain), not CT-scoped.
