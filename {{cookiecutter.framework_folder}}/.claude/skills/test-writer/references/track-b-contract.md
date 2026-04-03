# Track B -- Contract-Driven Test Design

When the subject has no meaningful state machine -- stateless endpoints, pure
functions, validators, data transformers, error contracts -- forcing an FSM model
creates artificial complexity. This track extracts the input/output contract
directly, then uses equivalence partitioning to drive systematic test coverage.

---

## Phase 1 -- Extract the Contract

Analyze the subject and document:

**Inputs** -- Every parameter, field, or external dependency.

- Name, type, valid range or domain.
- Required vs optional. Default values.
- Format constraints (regex, enum, length bounds).

**Outputs** -- Every return value, side effect, or response shape.

- Name, type, shape.
- How output varies by input region (different return types, status codes, etc.).

**Error conditions** -- Every way the subject can reject input or fail.

- What triggers each error (invalid type, out-of-range, missing field, conflict).
- What the error looks like (exception type, status code, error message pattern).

**Invariants** -- Properties that hold across all valid inputs.

- Examples: "output length <= input length", "idempotent on repeated calls",
  "total always non-negative", "response time < 200ms for cached inputs".

**Equivalence partition table** -- Group inputs into classes that should produce
the same category of behavior. This is the key artifact: it replaces the FSM
transition table as the driver for test case design.

```
INPUTS:
  - name: <param>  type: <type>  range: <valid domain>  required: yes/no
OUTPUTS:
  - <description of output shape per input region>
ERROR CONDITIONS:
  - <trigger> -> <error type/code>
INVARIANTS:
  - <property that always holds>
EQUIVALENCE CLASSES:
  EC-01: <description>  inputs: <representative>  expected: <behavior>
  EC-02: <description>  inputs: <representative>  expected: <behavior>
```

If the subject's contract is ambiguous, ask a targeted clarifying question rather
than assuming. One question at a time.

---

## Phase 2 -- Design Test Cases

Map every contract element to test cases:

**Happy path per equivalence class** -- One test per EC with a representative
value from the interior of the class.

**Boundary values** -- For every numeric range or size constraint, test:

- Just inside the boundary (last valid value).
- On the boundary (if the boundary is inclusive).
- Just outside the boundary (first invalid value).

**Error paths** -- One test per error condition. Verify the correct error
type/code and that no partial side effects occur.

**Invariant tests** -- One test per invariant. Property-based tests work well
here: generate arbitrary valid inputs, run the subject, assert the invariant.

**Pairwise combinations** -- When multiple inputs interact (e.g., two optional
fields whose combination matters), cover pairwise combinations rather than full
cartesian product.

Format test cases as a table before writing code:

```
TC-01  EC-01: valid interior   input: <repr>         expect: <output>
TC-02  EC-02: empty input      input: []             expect: <output>
TC-03  boundary: max length    input: 255 chars      expect: accepted
TC-04  boundary: over max      input: 256 chars      expect: rejected
TC-05  error: missing required input: omit <field>   expect: ValidationError
TC-06  invariant: idempotent   input: arbitrary x2   expect: same result
```

---

## Phase 3 -- Generate Executable Tests

Translate the test case table into runnable code. Use the framework and language
already in use in the project (see Shared Conventions in SKILL.md for defaults).

- Group tests by equivalence class using test classes or describe blocks.
- Parametrize tests within the same EC when they share the same assertion shape
  (e.g., multiple valid inputs all expecting success).
- Property-based tests for invariants: generate arbitrary valid inputs, run the
  subject, assert the property.

---

## Example -- Email Validation Endpoint

**Input:** "Write tests for our email validation utility."

**Phase 1 output:**

```
INPUTS:
  - name: email     type: str   range: any string   required: yes
  - name: allow_plus type: bool  range: true/false   required: no (default: true)
OUTPUTS:
  - valid email: returns NormalizedEmail(local, domain, original)
  - invalid email: raises ValidationError with reason code
ERROR CONDITIONS:
  - empty string -> ValidationError("EMPTY")
  - missing @ -> ValidationError("NO_AT_SIGN")
  - domain not resolvable -> ValidationError("BAD_DOMAIN")
  - plus addressing when allow_plus=false -> ValidationError("PLUS_NOT_ALLOWED")
INVARIANTS:
  - normalized.original always equals the input string
  - normalized.local + "@" + normalized.domain is a valid reconstruction
  - idempotent: validate(validate(x).original) produces the same result
EQUIVALENCE CLASSES:
  EC-01: simple valid       "user@example.com"              -> NormalizedEmail
  EC-02: plus addressing    "user+tag@example.com"          -> NormalizedEmail (if allowed)
  EC-03: unicode local      "user@xn--n3h.example.com"     -> NormalizedEmail
  EC-04: empty string       ""                              -> ValidationError
  EC-05: missing @          "userexample.com"               -> ValidationError
  EC-06: bad domain         "user@nonexistent.invalid"      -> ValidationError
  EC-07: plus blocked       "user+tag@ex.com", allow=false  -> ValidationError
```

**Phase 2 output (excerpt):**

```
TC-01  EC-01: simple valid     "user@example.com"           expect: NormalizedEmail
TC-02  EC-02: plus allowed     "u+tag@example.com"          expect: NormalizedEmail
TC-03  EC-04: empty string     ""                           expect: ValidationError(EMPTY)
TC-04  EC-05: no @ sign        "noatsign"                   expect: ValidationError(NO_AT_SIGN)
TC-05  EC-07: plus blocked     "u+t@ex.com", allow=false    expect: ValidationError(PLUS_NOT_ALLOWED)
TC-06  boundary: max length    "a"*64 + "@example.com"      expect: accepted (RFC limit)
TC-07  boundary: over max      "a"*65 + "@example.com"      expect: rejected
TC-08  invariant: idempotent   arbitrary valid emails        expect: same result on re-validate
```

**Phase 3:** pytest test file follows, one function per TC.
