# Test Plan Schema

Every Protocol method has a per-method invariant spec in
`plans/test-plan.yaml`. The Test Author (Tier 1, Opus) reads each entry
and produces contract tests in `tests/contracts/` or emits an
`AmendSignal` when the Protocol is silent on an invariant.

## Cost Model

Tests written against a Protocol stub without a behavioral spec tend to
drift toward whatever the generator produced -- the contract becomes
descriptive instead of governing. Declaring invariants up front forces
the architect to reason about observable behavior before any code is
written, and makes "the Protocol is silent on this" a first-class
signal instead of an inference.

## Schema (authoritative: `scripts/schemas.py`)

```yaml
entries:
  - protocol: interfaces/<name>.pyi
    method: <method name>
    invariants:
      - id: INV-NNN
        kind: <InvariantKind>
        description: <one-line behavioral claim>
        pass_criteria: |
          <how a conforming implementation is verified>
```

## InvariantKinds

### `call_binding`
How a method delegates work to collaborators.

Pass criteria typically name: which collaborator is invoked, which
argument is bound to which parameter, and under which input.

```yaml
- id: INV-002
  kind: call_binding
  description: Delegates geocoding to the injected Geocoder
  pass_criteria: |
    Geocoder.lookup is called exactly once with the destination from the
    route request. No other collaborator is touched on the happy path.
```

### `cardinality`
How many times a method or side effect fires per invocation.

Pass criteria typically name: exact count, per-iteration constraints,
idempotency on retry.

```yaml
- id: INV-003
  kind: cardinality
  description: Persists one route row per successful resolution
  pass_criteria: |
    For a successful route(), RouteRepository.save is called exactly once.
    No duplicate writes on retries.
```

### `error_propagation`
Which exception types propagate, under which trigger, with what message.

Pass criteria typically name: the raised type, the input that triggers
it, and (when declared) the message substring.

```yaml
- id: INV-001
  kind: error_propagation
  description: Raises RouteNotFound when the destination is absent
  pass_criteria: |
    Given a destination not present in the routing table, route() raises
    RouteNotFound with the destination in the message.
```

### `state_transition`
Explicit state machine transitions a method drives.

Pass criteria typically name: the before/after states, the triggering
input, and the forbidden intermediate or terminal states.

```yaml
- id: INV-004
  kind: state_transition
  description: RouteStatus transitions PENDING -> RESOLVED on success
  pass_criteria: |
    Before route() runs, status is PENDING; after a successful return,
    status is RESOLVED. FAILED is only set on error paths, never skipped.
```

### `property`
A universal property that must hold for an arbitrary input in the
declared domain. Typically expressed as a property-based test.

Pass criteria typically name: the domain generator, the property, and
any observability constraints.

```yaml
- id: INV-005
  kind: property
  description: Route resolution is deterministic for the same inputs
  pass_criteria: |
    Property test: for any (src, dst) present in the table, two successive
    route() calls with the same args return structurally equal RoutePayload
    values.
```

### `adversarial`
A deliberately hostile input that must be rejected in the declared way.

Pass criteria typically name: the adversarial input, the rejection
mechanism (exception type, validation return), and what must NOT happen.

```yaml
- id: INV-006
  kind: adversarial
  description: Rejects coordinate payloads outside the declared bbox
  pass_criteria: |
    Given coords outside the configured geofence, route() raises ValueError
    rather than returning a partial RoutePayload.
```

## Authoring guidance

- One invariant per observable behavior -- do not combine multiple
  claims in one entry. Test-quality heuristics penalize entries that
  bundle unrelated axes.
- Every `@throws` / `Raises:` on the Protocol **must** have an
  `error_propagation` invariant. The Test Author emits an AmendSignal
  if the Protocol declares a raised type but no invariant covers it.
- Every `@post` on the Protocol **should** have at least one invariant
  (call_binding, cardinality, state_transition, or property depending
  on the postcondition's shape).
- `adversarial` invariants are optional but strongly recommended for
  any Protocol method that accepts user-shaped input.
- `pass_criteria` is the contract the Test Author translates into
  assertions. Write it so a reader who has never seen the implementation
  can produce a test from it.

## AmendSignal

When the Test Author finds an invariant that cannot be enforced because
the Protocol is silent on it, it writes an `AmendSignalFile` to
`.iocane/amend-signals/<protocol>.yaml` and does NOT write the test
file for that Protocol.

```yaml
protocol: interfaces/router.pyi
attempt: 1
signals:
  - method: route
    invariant_id: INV-001
    kind: missing_raises
    description: |
      INV-001 states "Raises RouteNotFound" but the Protocol declares no
      Raises: clause on route(). The test cannot pin which exception type
      without inferring.
    suggested_amendment: |
      Add `Raises: RouteNotFound when destination is absent from the
      table.` to the route() docstring.
```

`handle_amend_signal.py` routes the file back to the architect amend
sub-loop, bounded by `architect.amend_retries` in `iocane.config.yaml`.
