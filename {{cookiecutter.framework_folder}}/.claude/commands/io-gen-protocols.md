---
name: io-gen-protocols
description: Emit interfaces/*.pyi Protocol stubs from YAML sources via jinja2 codegen. Invoked after /io-architect (post-H, post-validators) and before any test authoring. Re-runnable whenever YAML changes.
---

# /io-gen-protocols

## Purpose

Mechanically generate `interfaces/*.pyi` from the YAML-authored contract surface. `interfaces/` is codegen output -- type-only, not runtime-importable. The authorial inputs are `plans/component-contracts.yaml`, `plans/symbols.yaml`, and `plans/test-plan.yaml`; every byte in `interfaces/` derives from those.

```
/io-architect -> /io-gen-protocols -> spawn-test-author.sh -> ...
```

Owns: rendering one `.pyi` per Protocol-bearing component; idempotent output given the same YAML input.

Does **not** own: YAML authoring (that is `/io-architect`); test authoring (that is `spawn-test-author.sh` / `io-test-author`); impl writing (that is `io-execute`).

---

## Preconditions

Before invoking this command:

1. `plans/component-contracts.yaml` exists and parses. Every component that declares a `protocol:` path also declares a non-empty `methods:` list (each with `name`, `args`, `return_type`, optional `raises`, optional `docstring`).
2. `plans/symbols.yaml` exists and parses. Every exception name appearing in any `MethodSpec.raises` is declared as `kind: exception_class` with a valid `declared_in`. Every **project-defined OR external** custom type appearing in any `ArgSpec.type_expr` or `MethodSpec.return_type` is declared as `kind: shared_type` with a valid `declared_in`. `declared_in` accepts two shapes: a project filesystem path (`src/domain/types.py`) for project-defined symbols, or a bare Python module path (`pydantic`, `sqlalchemy.orm`) for third-party packages. The validator rejects dotted-src Pythonic form (`src.domain.types`), wrong-zone paths, and `interfaces/...` placements at schema load. Names resolvable to Python builtins (`list`, `int`, `str`, ...) or known stdlib modules (`datetime`, `typing.Optional`, `collections.abc.Callable`, `pathlib.Path`, `uuid.UUID`, `decimal.Decimal`, `enum.*`, `fractions.Fraction`) do NOT require a `symbols.yaml` entry -- `gen_protocols.py` emits their imports from an internal table. Unknown names (neither builtin, nor declared in `symbols.yaml`, nor in the stdlib table) are skipped with a stderr `WARN:`; either declare the name (project path or bare module) or extend `_STDLIB_IMPORTS` in `harness/scripts/gen_protocols.py`.
3. `plans/test-plan.yaml` is optional at first-run. When present, `error_propagation` invariants whose `description` mentions a method's raised exception provide the trigger text in the generated docstring; absent invariants yield a placeholder.

`validate_symbols_coverage.py` enforces precondition 2 mechanically and will FAIL if any `MethodSpec.raises` name does not resolve to a declared `exception_class`.

---

## Steps

### Step 0 -- [HARD GATE] Symbol coverage

Run:

```bash
uv run python .claude/scripts/validate_symbols_coverage.py
```

If exit non-zero, HALT. The emitted error names the missing symbol and the `component.method` that referenced it. Fix `plans/symbols.yaml` (add the missing `exception_class` or `shared_type` entry with the correct `declared_in: src/...` path) before re-invoking.

### Step 1 -- Codegen

Invoke the codegen script with `IOCANE_ROLE=gen_protocols` so the `interfaces-codegen-only.sh` hook admits the writes:

```bash
IOCANE_ROLE=gen_protocols uv run python .claude/scripts/gen_protocols.py
```

The script reads the three YAML files and emits one `interfaces/<stem>.pyi` per component whose `protocol:` field is non-empty. Components without a `protocol:` (e.g., `Settings`, value types) are skipped.

Flags (rarely needed -- defaults match harness convention):

- `--contracts PATH` (default `plans/component-contracts.yaml`)
- `--symbols PATH` (default `plans/symbols.yaml`)
- `--test-plan PATH` (default `plans/test-plan.yaml`)
- `--out-dir PATH` (default `interfaces`)
- `--template PATH` (default `harness/templates/interface.pyi.template`)

### Step 2 -- Verify

Confirm each emitted `.pyi` parses as Python:

```bash
for f in interfaces/*.pyi; do
  uv run python -c "import ast; ast.parse(open('$f').read())"
done
```

Optional strict check -- mypy-validate the stubs against a trivial impl scaffold (useful when debugging codegen drift):

```bash
uv run mypy --strict interfaces/*.pyi
```

---

## Idempotence

The codegen is deterministic: same YAML input produces byte-identical `.pyi` output. Re-invoking after no YAML change produces no diff. Re-invoking after a YAML edit produces exactly the diff implied by that edit -- no spurious whitespace or ordering churn.

## Re-run discipline

Re-run `/io-gen-protocols` whenever `plans/component-contracts.yaml`, `plans/symbols.yaml`, or `plans/test-plan.yaml` changes in a way that affects the Protocol surface (methods added / removed / renamed; args or return types changed; raises set changed; responsibilities edited; exception or shared-type `declared_in` moved).

The architect is responsible for signalling when to re-run; there is no automatic invalidation hook because the decision "is this YAML change contract-affecting?" requires judgement. When in doubt, re-run -- idempotence guarantees a no-op when nothing changed.

## Failure handling

If codegen fails:

- **YAML not well-formed** -- the loading step fails with a `ValidationError`; the error names the offending field. Fix the YAML and re-run. (Root-cause layer: `yaml_contract`.)
- **Template syntax error** -- `jinja2.TemplateSyntaxError` with line/column. This is a harness-side defect; emit a finding with `root_cause_layer: interfaces_codegen` so the codegen script or template is fixed before downstream consumers are re-run.
- **mypy fails on emitted stub** -- typically a symptom of missing symbol declarations (shared type referenced in a method signature without a corresponding `symbols.yaml` entry). Fix the YAML source and re-run (`yaml_contract` layer). Only treat as `interfaces_codegen` when the YAML is complete and correct but the template still emits ill-typed output.

See `harness/rules/remediation-discipline.md` for the full remediation protocol.
