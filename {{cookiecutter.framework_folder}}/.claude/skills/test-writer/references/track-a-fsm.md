# Track A -- FSM-Driven Test Design

Enterprise business logic is often a disguised Finite State Machine. This track
extracts that FSM explicitly, then drives systematic test case design from it --
covering every transition, guard, and invariant before writing a single line of
executable code.

---

## Phase 1 -- Extract the FSM

Before writing any test cases, model the subject system as an FSM. Ask for or
infer the following from the code, spec, or user description:

**States** -- Every distinct status/stage an entity can occupy.

- Name each state clearly (e.g. `PENDING`, `ACTIVE`, `SUSPENDED`, `CLOSED`).
- Flag terminal states (no outbound transitions).
- Flag unreachable states if any are apparent.

**Transitions** -- Every edge between states.

- Format: `SOURCE --[event/action]--> TARGET`
- Every transition must be named. If the user has not named it, infer from the code.

**Guards** -- Conditions that must hold for a transition to fire.

- Format: `transition: guard expression` (e.g. `APPROVE: balance > 0 AND kyc_verified`)
- Note negative guards (conditions that block a transition).

**Invariants** -- Properties that must hold in ALL states or across ALL transitions.

- These are the highest-yield input for property-based tests.
- Examples: "total items never negative", "created_at never changes after set",
  "sum of line items always equals order total".

Produce the FSM as a structured block before moving to Phase 2. Format:

```
STATES: [list]
TRANSITIONS:
  - SOURCE --[event]--> TARGET  (guard: <condition>)
INVARIANTS:
  - <property that always holds>
```

If the system is ambiguous, ask a targeted clarifying question rather than
assuming. One question at a time.

---

## Phase 2 -- Design Test Cases

Map every FSM element to one or more test cases. Cover all of the following:

**Transition coverage** -- At minimum one happy-path test per transition.

- "Can I reach TARGET from SOURCE by firing EVENT with valid inputs?"

**Guard coverage** -- For every guarded transition:

- One test where the guard passes (transition fires).
- One test where the guard fails (transition is rejected).

**Negative transition coverage** -- Illegal moves must be rejected.

- For every state, attempt at least one transition that should NOT be allowed.
- Verify the system rejects it and stays in the current state.

**State reachability** -- Every state must be reachable from a valid start state
via some sequence of transitions. Flag any state that cannot be reached.

**Terminal state finality** -- No transition should escape a terminal state.

**Invariant tests** -- One test per invariant. These are often best expressed as
property-based tests: generate arbitrary valid inputs, apply arbitrary valid
transitions, assert the invariant holds throughout.

Format test cases as a table or numbered list before writing code:

```
TC-01  PENDING -> APPROVED   guard passes         expect: state = APPROVED
TC-02  PENDING -> APPROVED   guard fails (no KYC) expect: rejected, state = PENDING
TC-03  APPROVED -> CLOSED    valid close event    expect: state = CLOSED
TC-04  CLOSED -> APPROVED    illegal transition   expect: error/exception
TC-05  invariant: balance    arbitrary ops        expect: balance >= 0 always
```

---

## Phase 3 -- Generate Executable Tests

Translate the test case table into runnable code. Use the framework and language
already in use in the project (see Shared Conventions in SKILL.md for defaults).

- One test function per test case.
- Group by state or transition using classes/describe blocks.
- Property-based tests for invariants: generate input with the framework's
  arbitrary data primitives, apply a sequence of valid transitions, assert the
  invariant after each step.

---

## Example -- Order Approval Workflow

**Input:** "Write tests for our order approval workflow."

**Phase 1 output:**

```
STATES: DRAFT, PENDING_APPROVAL, APPROVED, REJECTED, CANCELLED
TRANSITIONS:
  - DRAFT --[submit]--> PENDING_APPROVAL  (guard: items.count > 0 AND total > 0)
  - PENDING_APPROVAL --[approve]--> APPROVED  (guard: approver.role == MANAGER)
  - PENDING_APPROVAL --[reject]--> REJECTED
  - PENDING_APPROVAL --[cancel]--> CANCELLED
  - APPROVED --[cancel]--> CANCELLED
  - DRAFT --[cancel]--> CANCELLED
TERMINAL STATES: REJECTED, CANCELLED (APPROVED per spec has no further transitions)
INVARIANTS:
  - total == sum(item.price * item.qty for item in items)  [always]
  - created_at is immutable after creation
  - REJECTED and CANCELLED are terminal -- no outbound transitions
```

**Phase 2 output (excerpt):**

```
TC-01  DRAFT -> PENDING      guard passes (items present)      expect: PENDING_APPROVAL
TC-02  DRAFT -> PENDING      guard fails (empty cart)          expect: error, stays DRAFT
TC-03  PENDING -> APPROVED   approver is MANAGER               expect: APPROVED
TC-04  PENDING -> APPROVED   approver is not MANAGER           expect: error, stays PENDING
TC-05  REJECTED -> APPROVED  illegal escape from terminal      expect: error
TC-06  invariant: total      add/remove items, arbitrary qty   expect: total == sum always
```

**Phase 3:** pytest test file follows, one function per TC.
