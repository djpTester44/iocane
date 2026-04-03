---
name: test-writer
description: >
  Systematic test generation for business logic, stateless endpoints, pure
  functions, validators, data transformations, and error contracts. Use this
  skill whenever the user wants to write tests for application behavior --
  whether it involves state machines (order pipelines, approval flows, user
  lifecycle, payment processing) or stateless subjects (REST endpoints,
  validation functions, data converters, configuration parsers, error handling).
  Trigger even if the user just says "write tests for X", "help me test this",
  or "what should I test here". This two-track approach (FSM or Contract-Driven)
  produces more thorough coverage than ad-hoc test writing for any subject type.
---

# Systematic Test Writer

This skill uses two tracks to generate tests. Both tracks follow the same
three-phase discipline (Extract -> Design -> Generate) but apply it to different
kinds of subjects. The triage gate below determines which track to use.

---

## Triage Gate

For each test class (not per file -- a single module may contain both types):

> **Does the subject have 2+ distinct named states with explicit transitions
> between them?**

- **Yes** -> **Track A: FSM-Driven** -- read `references/track-a-fsm.md`
- **No** -> **Track B: Contract-Driven** -- read `references/track-b-contract.md`

Examples of Track A subjects: order approval workflows, user account lifecycle,
payment authorization flows, document review pipelines -- anything where an
entity moves through named stages.

Examples of Track B subjects: email validation, price calculators, REST endpoint
handlers, configuration parsers, data format converters, permission checkers --
anything with inputs, outputs, and rules but no state progression.

If the classification is ambiguous, ask the user one clarifying question:
"Does [subject] move through named stages, or does it take input and produce
output without remembering previous calls?" The answer determines the track.

**Mixed modules:** When a file contains both stateful and stateless logic,
suggest organizing tests into separate test classes -- one per track. Do not
force one track onto the entire file.

---

## Why Equivalence Partitioning Bridges Both Tracks

Both tracks are grounded in equivalence partitioning -- the idea that inputs can
be grouped into classes where all members produce the same category of behavior,
so one representative per class gives systematic coverage without exhaustive
enumeration.

- **Track A** partitions the *state space*: each (state, event, guard-condition)
  triple defines an equivalence class of inputs that should trigger the same
  transition.
- **Track B** partitions the *input space* directly: each combination of input
  ranges, types, and constraints defines an equivalence class that should produce
  the same output shape.

The three-phase discipline (Extract the model -> Design TCs from partitions ->
Generate code) is identical. The difference is what gets partitioned.

---

## Shared Conventions

Both tracks follow these conventions. Track-specific phases are in the reference
files; these rules apply to all generated tests.

### Phase Discipline

Never skip Phase 1 (Extract) or Phase 2 (Design) even if the user asks to "just
write the tests." Present abbreviated versions if speed matters, but the
extraction and TC design must happen -- they are what make the output
systematically complete rather than ad hoc.

### Interaction Pattern

1. User provides code, spec, or description of the system under test.
2. Produce the Phase 1 extraction and confirm with the user before proceeding.
   ("Does this look right? Anything missing?")
3. Produce the Phase 2 TC table and confirm before writing code. This is the
   cheapest place to catch gaps.
4. Generate Phase 3 executable tests.
5. If the user iterates ("add a test for X" / "I missed a condition"), update
   the Phase 1 model and TC table first, then update the code. Keep all three
   in sync.

### Naming

- One test function per test case. Name after the TC identifier and scenario:
  `test_tc01_pending_to_approved_guard_passes` (Track A) or
  `test_tc01_valid_email_simple_address` (Track B).
- For hybrid modules with multiple test classes, prefix TC IDs with a component
  abbreviation to avoid collisions: `TC-R01` for Router, `TC-D01` for Delivery.
  Test functions follow the same prefix: `test_tc_r01_low_priority_email`.

### Structure

- Group by state/transition (Track A) or equivalence class (Track B) using test
  classes or describe blocks.
- Shared setup (constructing the entity or subject in a known state) goes in
  fixtures or setUp -- never duplicated inline.
- No logic in test bodies beyond arrange / act / assert. Helpers go in helpers.
- Tests must not depend on external I/O unless integration tests are explicitly
  requested. Mock or stub at the boundary.

### Framework Defaults

Match the framework and language already in use. If unknown:

- Python: `pytest` (property-based: `hypothesis`)
- JavaScript/TypeScript: `jest` or `vitest` (property-based: `fast-check`)
- Other: ask before assuming.

If the codebase uses a specific test runner or project convention, follow it.
Ask the user if unsure.

---

## Scope Guard

**Do not rewrite existing tests.** When asked to improve test coverage for a
module that already has tests:

- Identify which existing tests are FSM-style and which are contract-style.
- If a single test file mixes both, suggest splitting into separate test classes
  by type rather than rewriting.
- Add new tests to fill gaps identified by the relevant track's Phase 2 analysis.
- Leave existing passing tests untouched.

---

## Track References

- **Track A (FSM-Driven):** `references/track-a-fsm.md` -- for subjects with
  states, transitions, guards, and invariants.
- **Track B (Contract-Driven):** `references/track-b-contract.md` -- for
  stateless subjects with input/output contracts and equivalence partitions.

Read the appropriate reference file after the triage gate routes you.
