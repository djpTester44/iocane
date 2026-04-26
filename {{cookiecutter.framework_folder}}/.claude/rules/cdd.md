---
paths:
  - "plans/**"
  - "src/**"
  - "tests/**"
---

# CDD: Contract-Driven Development Governance

> The contract is the architectural authority. Implementation and tests
> are derived from it, not the other way around. A codebase that looks
> like CDD but is actually "tests emerged, contract was backfilled" pays
> the full CDD cost with none of the stability benefit.

## Cost Model

Retroactive contracts collapse the boundary between design and
implementation. When the contract is reverse-engineered from the code,
changing the implementation changes what the contract "should" say --
the contract has no independent authority, and no single artifact
governs behavior. Tests written in this regime are implementation-shaped,
not behavior-shaped, so they cannot catch semantic regressions; they
only catch byte-for-byte edits to the code they were extracted from.

## [HARD] Seven Principles

1. **Contract first, always.** No impl, no test, before the contract.
2. **Contracts define behavior, not just shape.** Types, signatures,
   `@throws`, invariants -- all four are required.
3. **Tests are derived from contracts.** Read the contract; each clause
   produces one or more tests. Never read the impl to decide what to test.
4. **Independent implementability.** A contract that cannot be implemented
   without reading another module's internals is underspecified -- fix the
   contract.
5. **Substitutability.** Any conforming impl replaces any other. Behavior
   not declared in the contract is incidental and must not be relied upon.
6. **Explicit error contracts.** Every raised exception type and its
   trigger is declared. Raising an undeclared type is a contract
   violation, same as returning the wrong type.
7. **Contracts are immutable once active.** Changes require a separate
   diff with rationale, not bundled into an impl PR.

## [HARD] CDT vs Implementation TDD

Contract-Derived Tests (CDT) live in `tests/contracts/`. Implementation
tests live elsewhere under `tests/`. The separation is enforced by
`write-gate.sh` role-scoped write targets -- generators cannot write
contract tests, testers cannot write impl tests.

- CDT: derived from contract clauses; survives any impl rewrite that
  preserves contract behavior; every test cites a specific clause.
- Impl TDD: classical red-green-refactor on internal logic (parsers,
  caches, retry backoffs); may break on refactor; never redefines the
  contract boundary.

If a TDD cycle reveals you want a different public interface, that is a
contract amendment proposal, not a silent contract edit.
