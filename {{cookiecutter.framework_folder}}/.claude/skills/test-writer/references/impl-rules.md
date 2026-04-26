# Impl-Test Rules (emergent, TDD-style)

Reference loaded by `io-execute.md` Step B. Governs impl tests
authored *during* implementation -- the TDD cycle that develops
internal logic underneath a contract that is already locked.

Substance traces to `.claude/rules/cdd.md` section
"[HARD] CDT vs Implementation TDD".

---

## Scope

Impl tests verify internals invisible to the contract:

- Complex parsing or validation helpers behind a single public method.
- Caching strategies, TTL logic, cache-stampede protection.
- Retry mechanisms, backoff calculations.
- Data transformation pipelines with intermediate state.
- Internal state machines governing private transitions.

The public contract specifies the behavior; impl tests verify how
the private machinery gets there.

---

## Write Location

Under `tests/**` **except** `tests/contracts/` and
`tests/connectivity/`. Suggested conventions:

- `tests/test_<module>_impl.py`
- `tests/<component>/test_<module>_impl.py`

Any write into `tests/contracts/` or `tests/connectivity/` is a scope
violation -- those directories are outside the impl test author's write
scope, and reset hooks are not the intended defense.

---

## Traceability

Impl tests cite **design intent**, not contract clauses. A contract
test cites an invariant ID (`INV-NNN`); an impl test explains *why*
an internal choice is worth verifying in the test docstring.

Good impl-test docstring: "Verify the retry helper backs off
exponentially so a flaky dependency doesn't saturate the pool."

Bad impl-test docstring: "Covers INV-042." (That belongs to a
contract test.)

---

## Separation Rule

Impl tests are **expected to break on refactor**. Contract tests are
**not**. This asymmetry is the whole point of the separation.

If a test would need rewriting when internals change but the public
behavior is unchanged, it is an impl test by definition. If a test
survives an internal rewrite only because the new internals happen
to mirror the old, that test was over-coupled -- split or delete.

---

## Non-Substitution

Impl tests never replace contract tests or CTs. Even if an impl test
happens to exercise the same observable as a contract clause, the
contract test must still exist independently. Contract tests are the
acceptance surface; impl tests are development aids that may be
deleted or rewritten freely during refactor.

---

## TDD Never Reshapes the Contract

If a TDD cycle reveals that the public contract should differ, the
implementation does not silently diverge. The contract stays locked
until the architect amends it.

This is the amendment trigger: emit
`.iocane/amend-signals/<cp-id>.yaml` following the `AmendSignalFile`
schema (see `io-execute.md` Section 9 AMEND-on-impl-gap path). The
architect consumes the signal, amends the contract, and dispatch
re-runs. An impl workaround that ships anyway is a contract
violation regardless of whether the tests pass.

---

## Forbidden

- `assert True` placeholders.
- Writing impl tests into `tests/contracts/` or `tests/connectivity/`.
- Tests that modify `plans/component-contracts.yaml`.
- "Replacing" a contract test with an impl test because the contract
  test is inconvenient -- this silently erases the acceptance surface.
- Citing `INV-NNN` in impl-test docstrings (use design-intent prose).
