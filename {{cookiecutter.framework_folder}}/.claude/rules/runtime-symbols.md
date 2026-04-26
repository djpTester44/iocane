---
paths:
  - "plans/symbols.yaml"
  - "src/**"
---

# RUNTIME SYMBOLS: Exception Classes and Shared Types Live Somewhere Importable

> Runtime-bearing symbols (`kind: exception_class`, `kind: shared_type`) declare their home via `symbols.yaml.declared_in`, which must point at a legitimate import zone -- either the project's `src/` tree (project-defined symbols) or a bare Python module path (third-party packages like `pydantic`, `sqlalchemy.orm`). The schema validator (`Symbol.check_declared_in_zone`) rejects dotted-src Pythonic form (`src.foo.bar`); this rule explains why so test authors and impl writers declare runtime identity where runtime code actually lives.

## Cost Model

A shared type like `RoutePayload` is a Python class with an `__init__`, fields, and (often) methods. When a test asserts `isinstance(result, RoutePayload)`, it needs the runtime class body. Placing it in `src/` (for project-defined symbols) or declaring the external package (`pydantic`, `httpx`, ...) keeps the runtime identity where runtime code actually lives.

Exception classes are the same case: `raise RouteNotFound(...)` instantiates a class. That class body is either `src/` code or a third-party package.

## [HARD] Authoring rule

- **Exception class (project-defined)**: add to `symbols.yaml` with `kind: exception_class`, `declared_in: src/...`, `parent: <BaseExceptionName>`. The impl body lives at the declared path.
- **Exception class (third-party)**: add with `kind: exception_class`, `declared_in: <module>` (e.g., `pydantic`), `parent: <BaseClassName>`. The package owns the runtime class; the consumer's `pyproject.toml` must install it.
- **Shared type (project-defined)**: add with `kind: shared_type`, `declared_in: src/...`, `type_expr: <one-line shape summary>`. The impl body lives at the declared path.
- **Shared type (third-party)**: add with `kind: shared_type`, `declared_in: <module>` (e.g., `pydantic`, `sqlalchemy.orm`), `type_expr: <one-line shape summary>`. The package owns the runtime class.
- The schema validator rejects dotted-src Pythonic form (`src.foo.bar`) as an authoring mistake. If the validator fires, fix the `declared_in`; do not remove the symbol.

## [HARD] Test author implication

When a test needs to import a runtime-bearing symbol (to instantiate, to `isinstance` check, to raise), import from the `declared_in` module -- that is `src/domain/exceptions.py`, `src/domain/types.py`, `pydantic`, `sqlalchemy.orm`, whatever `symbols.yaml` declares.

## Remediation path

Any finding naming a runtime symbol in the wrong zone carries `root_cause_layer: yaml_contract` -- fix `plans/symbols.yaml.<name>.declared_in`, then re-run any downstream validators.
