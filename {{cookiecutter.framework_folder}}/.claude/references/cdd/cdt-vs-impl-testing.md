# Contract-Derived Testing vs. Implementation TDD

## Purpose of This Document

This document clarifies the relationship between two testing practices
that coexist in a CDD codebase. They look similar -- both involve writing
tests before or alongside code -- but they serve different purposes, operate
at different scopes, and follow different rules. Confusing them leads to
contracts that describe implementations instead of governing them.

---

## The Two Practices at a Glance

| Dimension            | Contract-Derived Testing (CDT)          | Implementation TDD                         |
|----------------------|-----------------------------------------|--------------------------------------------|
| **What drives it**   | The contract file                       | The implementer's design decisions          |
| **Scope**            | Module boundary (public interface)      | Internal logic (private helpers, algorithms)|
| **When written**     | After the contract, before any code     | During implementation, as internals emerge  |
| **What it tests**    | Preconditions, postconditions, errors,  | Internal algorithms, helper functions,      |
|                      | invariants, boundary behaviors          | data transformations, edge cases of private |
|                      |                                         | logic not visible through the contract      |
| **Source of truth**  | The `.pyi` / interface contract file    | The implementer's understanding of "how"    |
| **Traceability**     | Every test cites a contract clause      | Tests cite design intent, not contract      |
| **Survives rewrite** | Yes -- contract unchanged = tests unchanged | No -- new implementation = new internal tests |
| **Who could write it** | Anyone who can read the contract      | Only someone who knows the implementation   |

---

## Contract-Derived Testing (CDT): The "What"

CDT is the testing arm of CDD. It exists to verify that an implementation
honors the contract's behavioral promises. The process is mechanical:

### Input
A contract file and nothing else.

### Process
Read each clause in the contract. Produce one or more test cases that
verify the clause holds.

### Rules

**1. The contract is your only input.**
Do not read the implementation. Do not think about how the module works
internally. You are testing the boundary, not the guts.

**2. Every test traces to a clause.**
Each test function must reference the specific `@pre`, `@post`, `@throws`,
or invariant it verifies. If you cannot point to a clause, the test does
not belong in the contract test suite.

**3. Tests are structured to mirror the contract.**
One test class per contract method. Within each class, tests are grouped
by clause type: precondition violations, postcondition verifications,
error condition triggers, invariant checks.

**4. Contract tests are implementation-agnostic.**
They must pass for any conforming implementation. If you swap the Postgres
implementation for an in-memory implementation, the contract tests must
still pass without modification. If they don't, the tests are testing
implementation details, not contract behavior.

**5. Contract tests are written before any implementation exists.**
They should all fail initially. They define the finish line.

### Example derivation

Given this contract clause:

```python
def create(self, email: str, display_name: str) -> User:
    """
    @pre: email is valid RFC 5322
    @pre: display_name is 1-128 non-blank characters
    @post: returned User.id is a fresh UUIDv4
    @post: returned User.created_at == returned User.updated_at
    @throws: DuplicateEmailError if email already registered
    """
    ...
```

The derived tests are:

```python
class TestCreate:
    # @pre: email is valid RFC 5322
    def test_rejects_invalid_email(self, repo): ...
    def test_rejects_empty_email(self, repo): ...

    # @pre: display_name is 1-128 non-blank characters
    def test_rejects_empty_display_name(self, repo): ...
    def test_rejects_whitespace_only_display_name(self, repo): ...
    def test_rejects_display_name_over_128_chars(self, repo): ...
    def test_accepts_display_name_at_128_chars(self, repo): ...

    # @post: returned User.id is a fresh UUIDv4
    def test_returns_valid_uuid4(self, repo): ...
    def test_returns_unique_ids_for_different_users(self, repo): ...

    # @post: returned User.created_at == returned User.updated_at
    def test_timestamps_equal_on_creation(self, repo): ...

    # @throws: DuplicateEmailError
    def test_duplicate_email_raises(self, repo): ...
```

No knowledge of the implementation was needed. Any developer or agent
reading only the contract would produce substantially the same tests.

---

## Implementation TDD: The "How"

Implementation TDD is the classical red-green-refactor cycle applied to
the internals of a module. It governs how you build the private machinery
that fulfills the contract.

### When it applies

Once you are inside the implementation file, working on logic that does
not surface through the contract boundary:

- A complex parsing algorithm inside a validation helper
- A caching strategy with eviction logic
- A retry mechanism with backoff calculations
- A data transformation pipeline with intermediate steps
- A state machine governing internal transitions

These are all invisible to the contract. The contract says "create returns
a User with a valid UUID." It does not care whether UUIDs come from
`uuid4()`, a Snowflake ID generator, or a custom scheme. But if you choose
to build a custom UUID scheme, TDD is a fine way to develop it.

### Rules

**1. Implementation TDD never shapes the contract.**
If a TDD cycle reveals that you want a different public interface, that is
a signal to propose a contract amendment -- not to change the contract
silently or let the test drive the boundary.

**2. Implementation tests live separately from contract tests.**
Contract tests go in `tests/contracts/test_<module>.py`.
Implementation tests go elsewhere under `tests/` (for example
`tests/test_<module>_impl.py` or alongside the internal module they test).
The separation is enforced by `write-gate.sh` via role-scoped write
targets -- it is physical, not just conceptual.

**3. Implementation tests are expected to break on refactor.**
If you rewrite the internals, implementation tests may need rewriting.
Contract tests must not need rewriting. This asymmetry is the whole point --
contract tests verify stability; implementation tests verify current
internal design.

**4. Implementation tests do not substitute for contract tests.**
Even if your TDD tests happen to cover the same behavior as a contract
clause, the contract test must still exist independently. Contract tests
are the acceptance criteria; implementation tests are development aids.

---

## The Directional Distinction

This is the most critical conceptual point:

```
CDD Flow (prescriptive):
  Contract -> Tests -> Implementation
  "The contract says X must hold. Write a test that checks X.
   Write code until the test passes."

TDD Flow (exploratory):
  Test -> Code -> Refactor -> (interface emerges)
  "I want behavior X. Write a test for X. Write code to pass it.
   Clean up. The interface is whatever the tests ended up needing."
```

In CDD, the contract is **designed** as an architectural decision. It
reflects how modules relate, what responsibilities they carry, and what
guarantees they make. It is a product of system design thinking.

In TDD, the interface **emerges** from iterative test-code cycles. It is
a product of implementation discovery.

Both are valid. But in a CDD codebase, TDD operates *inside* the
implementation, underneath the contract. TDD does not get to redefine the
module boundary. The hierarchy is:

```
Contract (architectural authority)
  |__ Contract-Derived Tests (boundary verification)
       |__ Implementation (fulfills the contract)
            |__ Implementation TDD (develops internal logic)
                 |__ Implementation Tests (verifies internals)
```

---

## The Trap: Retroactive Contracts

The failure mode this document exists to prevent:

1. Developer/agent writes tests in TDD style
2. Tests organically define the interface
3. A `.pyi` file is written after the fact to "document" the interface
4. The contract is now descriptive -- it describes what was built
5. The contract has no independent authority -- changing the implementation
   changes what the contract "should" say

This produces a codebase that looks like CDD (it has contract files, it
has tests) but behaves like ad-hoc development with retroactive
documentation. The contract is a rubber stamp, not a governing artifact.

**How to detect this has happened:**
- Contract clauses map 1:1 to implementation branches (the contract was
  reverse-engineered from the code)
- Contract tests import or reference implementation-specific types,
  helpers, or configuration
- Changing the implementation requires changing the contract tests
- The contract contains no preconditions or postconditions -- only type
  signatures

**How to prevent it:**
- Enforce the workflow order: contract -> tests -> implementation
- Require contract review/approval before implementation begins
- Contract tests must pass against a mock/stub implementation, proving
  they are implementation-agnostic

---

## Summary for the Agent

When you are asked to work in this codebase:

1. **Building a new module?**
   Write the contract first. Derive tests from it. Implement last.

2. **Writing tests for an existing contract?**
   Read only the contract. Structure tests by clause. Do not open the
   implementation file.

3. **Implementing complex internal logic?**
   Use TDD freely inside the implementation. Put those tests in a
   separate file from the contract tests.

4. **Tempted to change the contract because your implementation wants
   a different interface?**
   Stop. Propose the contract change as a separate step with rationale.
   Do not bundle it with implementation changes.

5. **Unsure whether a test belongs in contract tests or impl tests?**
   Ask: "Would this test need to change if I rewrote the internals but
   kept the same public behavior?" If yes -> implementation test.
   If no -> contract test.
