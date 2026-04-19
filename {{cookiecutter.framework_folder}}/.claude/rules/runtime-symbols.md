---
paths:
  - "plans/symbols.yaml"
  - "src/**"
  - "tests/**"
---

# RUNTIME SYMBOLS: Exception Classes and Shared Types Live in src/

> Runtime-bearing symbols (`kind: exception_class`, `kind: shared_type`) declare their home via `symbols.yaml.declared_in`, which must point into `src/`. The schema validator (`Symbol.check_declared_in_zone`) rejects `interfaces/` paths; this rule explains why so test authors and impl writers do not reach for the interfaces stub when they need the concrete class.

## Cost Model

A shared type like `RoutePayload` is a Python class with a `__init__`, fields, and (often) methods. When a test asserts `isinstance(result, RoutePayload)`, it needs the runtime class, not a type-only Protocol stub. Placing the class body under `interfaces/` forces tests to import from a zone that is supposed to be type-only, corrupting both invariants. Placing it in `src/` keeps the runtime identity where runtime code lives.

Exception classes are the same case: `raise RouteNotFound(...)` instantiates a class. That class body is `src/` code; the `interfaces/` Protocol stub merely declares (in its `Raises:` docstring) that methods of that Protocol can raise it.

## [HARD] Authoring rule

- **Exception class**: add to `symbols.yaml` with `kind: exception_class`, `declared_in: src/...`, `parent: <BaseExceptionName>`. The impl body lives at the declared path.
- **Shared type**: add to `symbols.yaml` with `kind: shared_type`, `declared_in: src/...`, `type_expr: <one-line shape summary>`. The impl body lives at the declared path.
- The schema validator refuses `declared_in: interfaces/...` for both kinds. If the validator fires, fix the `declared_in`; do not remove the symbol.

## [HARD] Test author implication

When a test needs to import a runtime-bearing symbol (to instantiate, to `isinstance` check, to raise), import from the `declared_in` module -- that is `src/domain/exceptions.py`, `src/domain/types.py`, whatever `symbols.yaml` declares. Never import from `interfaces/`.

`gen_protocols.py` already emits `from <module> import <Name>` inside generated `.pyi` stubs for every referenced shared-type and exception-class symbol; the stubs reference `src/` under the hood. Tests that need the runtime class should reach the same `src/` module directly, not route through the stub.

## Remediation path

Any finding naming a runtime symbol in the wrong zone carries `root_cause_layer: yaml_contract` -- fix `plans/symbols.yaml.<name>.declared_in`, then re-run `/io-gen-protocols` and any downstream consumers. `interfaces/` is not the fix target.
