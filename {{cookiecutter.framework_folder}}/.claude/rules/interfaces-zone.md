---
paths:
  - "interfaces/**"
  - "tests/**"
---

# INTERFACES ZONE: Type-Only, Codegen-Only

> `interfaces/` is the codegen output zone for Protocol stubs. Two deterministic hooks (`interfaces-pyi-only.sh`, `interfaces-codegen-only.sh`) refuse writes that violate either invariant. This rule explains why, so reasoning under context pressure does not push toward workarounds that the hooks will reject.

## Cost Model

The repeated C8 drift -- runtime classes injected into `interfaces/`, `.py` files placed alongside `.pyi` stubs, hand-authored edits bypassing the codegen source of truth -- costs more than the writes themselves. Each drift instance propagates: tests import Protocols at runtime, mypy starts treating stubs as implementations, the authoritative contract shifts from `symbols.yaml` to whichever `.py` file sneaked in. Recovery requires tracing every downstream import and restoring the YAML-first authority.

## [HARD] Two invariants

1. **Type-only.** Every file under `interfaces/` ends in `.pyi`. A `.py` in this zone is not a stub; it is a runtime module, and importing one at runtime breaks the type-only promise that downstream tooling (mypy strict, test authors using spec mocks) depends on.

2. **Codegen-only.** Every byte under `interfaces/` is produced by `/io-gen-protocols` from `plans/component-contracts.yaml` + `plans/symbols.yaml` + `plans/test-plan.yaml`. Hand-authored edits diverge the stubs from the YAML source of truth, and the next codegen run overwrites the edit without warning.

## [HARD] How changes land

To change Protocol surface: edit the YAML, re-run `/io-gen-protocols`, commit the regenerated `.pyi`. Never edit the `.pyi` directly -- the edit is silently transient, and drift-time troubleshooting starts at the YAML anyway.

## [HARD] Runtime imports forbidden

Tests, src code, and anything else downstream must not `import` from `interfaces/*` at runtime. The stubs have no runtime identity. Type-annotation usage (string annotations, `TYPE_CHECKING` blocks, pyi-only import chains) is the only admitted reference pattern. If a test needs the impl class at runtime, import it from `src/` -- runtime classes live there per `symbols.yaml.declared_in`.

## Remediation path

Any finding raising `root_cause_layer: interfaces_codegen` (codegen script or template defect) dies in the codegen source, not in `interfaces/`. Any finding raising `root_cause_layer: yaml_contract` dies in YAML. `interfaces/` is never the fix target.
