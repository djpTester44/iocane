# Symbols Registry Schema

Every cross-CP identifier is declared once in `plans/symbols.yaml`.
Downstream generators read the registry instead of inferring. Architect
authors the registry at Tier 1; CPs reference symbols by name only.

## Cost Model

An inferred Settings field name, exception class, or fixture name creates
silent drift between sibling CPs in a parallel wave. By the time it
surfaces (usually as an import error or a runtime lookup miss), the
offending CP has already been committed. Declaring the symbol once makes
the convention enforceable by `validate_symbols_coverage.py`.

## Schema (authoritative: `scripts/schemas.py`)

```yaml
symbols:
  <symbol_name>:
    kind: <SymbolKind>
    declared_in: <file path of the authoritative definition>
    used_by: [<component name>, ...]      # architect-authored at H-6
    used_by_cps: [<CP-ID>, ...]           # checkpoint-backfilled
    # kind-specific fields below
```

## `used_by` vs `used_by_cps`

Two reference axes, populated by different stages:

- **`used_by`** -- component names that reference the symbol. The
  architect populates this at `/io-architect` Step F by walking the
  CRC collaboration graph. This list is stable across the architect
  lifetime; it changes only when the architect re-runs.
- **`used_by_cps`** -- CP-IDs that touch the symbol. Backfilled at
  `/io-checkpoint` after `plan.yaml` is authored, by matching each CP's
  `scope[].component` against the architect-authored `used_by`. This
  list is stable across the checkpoint lifetime; it is regenerated when
  `/io-checkpoint` re-runs.

Tier-3 generators query `used_by_cps` to scope the symbol slice they
receive in their task pack. Tier-1 architect amend cycles query
`used_by` to find every component impacted by a contract change.

The validator `check_kind_required_fields` enforces which fields must
be populated per kind.

## SymbolKinds

### `settings_field`
Configuration attribute on a Pydantic `Settings` model or equivalent.

Required: `type_expr`, `env_var`
Optional: `default`

```yaml
DatabaseUrl:
  kind: settings_field
  declared_in: src/core/config.py
  type_expr: str
  env_var: APP_DB_URL
  default: null
  used_by: [CP-02, CP-05]
```

### `exception_class`
A custom exception that crosses a component-contract boundary.

Required: `parent` (base class name)

```yaml
RouteNotFound:
  kind: exception_class
  declared_in: src/domain/exceptions.py
  parent: LookupError
  used_by: [CP-03, CP-04]
```

### `shared_type`
A dataclass, TypedDict, or Pydantic model consumed by more than one CP.

Required: `type_expr` (shape summary sufficient for a downstream CP to
consume without reading the source)

```yaml
RoutePayload:
  kind: shared_type
  declared_in: src/domain/types.py
  type_expr: "@dataclass(frozen=True) with fields: src:str, dst:str, hops:int"
  used_by: [CP-03, CP-05]
```

### `fixture`
A pytest fixture shared across `tests/contracts/` or `tests/`.

Required: `fixture_scope` (`function`, `module`, `session`)

```yaml
fake_router:
  kind: fixture
  declared_in: tests/conftest.py
  fixture_scope: function
  used_by: [CP-03, CP-04]
```

### `error_message`
A literal string passed to an exception constructor. Registered when the
exact wording is verified by a test assertion or log-triage tool.

Required: `message_pattern`

```yaml
RouteNotFoundMessage:
  kind: error_message
  declared_in: src/domain/router.py
  message_pattern: "route not found for destination={destination}"
  used_by: [CP-03]
```

## External-package declarations

For `exception_class` and `shared_type` symbols that live in a
third-party installed package (pydantic, sqlalchemy, httpx, ...) rather
than in the project's `src/` tree, set `declared_in` to the **bare
Python module path** (no slashes, no `.py` suffix):

```yaml
BaseModel:
  kind: shared_type
  declared_in: pydantic
  type_expr: "class pydantic.BaseModel"
  used_by: [ConnectorRegistry]

ValidationError:
  kind: exception_class
  declared_in: pydantic
  parent: ValueError
  used_by: [ConfigLoader]

Session:
  kind: shared_type
  declared_in: sqlalchemy.orm
  type_expr: "class sqlalchemy.orm.Session"
  used_by: [PipelineRepository]
```

Downstream test and impl authoring imports `from <module> import <Name>`
for these -- the consumer's `pyproject.toml` is responsible for
ensuring the package is installable.

### `declared_in` shape rules (zone check)

| Input | Interpreted as | Emitted import |
|---|---|---|
| `src/foo/bar.py` | Project filesystem path | `from src.foo.bar import X` |
| `tests/conftest.py` | Tests zone (fixtures only) | `from tests.conftest import X` |
| `pydantic` | External bare module | `from pydantic import X` |
| `sqlalchemy.orm` | External dotted module | `from sqlalchemy.orm import X` |
| `src.domain.types` | **Rejected** -- dotted-src is a Pythonic mistake; use filesystem form | -- |
| `sorce/foo.py` | **Rejected** -- path-shaped values must start with `src/` | -- |

The validator rejects the common authoring mistakes (dotted-src
Pythonic form, wrong prefix) at schema load so typos surface near
the authoring site rather than downstream at type-check time.

### Residual authoring risks

- **Typo in a bare-module name** (`declared_in: pydantik`) cannot be
  caught at schema-load time without importing the package. Surfaces
  at pyright/mypy when the module is imported from `src/`.
- **Single-segment name collision** (`declared_in: core` where both a
  project `src/core/__init__.py` and an installed `core` package
  exist) resolves to whichever Python finds first on `sys.path`.
  Choose names that don't collide; when ambiguous, use the
  `src/core/__init__.py` filesystem form to anchor.

## Conflict detection

`symbols_parser.py` surfaces two hard conflicts:

- **`detect_env_var_conflicts`** -- two Settings fields claiming the
  same env var. Silent drift: the last loader wins.
- **`detect_message_pattern_conflicts`** -- two error_message symbols
  with the same literal. Breaks log-based triage.

Both are consulted by `validate_symbols_coverage.py`.

## Authoring guidance

- If you are tempted to let a generator infer a symbol's name or type,
  declare it here instead.
- Do not register symbols that are local to a single CP -- the registry
  is explicitly for cross-CP identifiers.
- `used_by` is the primary query key. Tier-3 generators filter the
  registry by their own CP-ID to scope the slice they receive.
