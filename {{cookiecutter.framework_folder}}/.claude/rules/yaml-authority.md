---
paths:
  - "plans/**"
  - "src/**"
  - "tests/**"
---

# YAML AUTHORITY: Fix Upstream, Re-derive Downstream

> `plans/*.yaml` is the source of truth for the component contract surface, runtime symbol registry, and test invariants. Everything under `src/` and `tests/` is derived from or validated against that source. When reasoning surfaces a wrongness downstream, the drift is almost always a YAML defect, and fixing the derived artifact leaves the YAML defect in place for the next validation run to re-flag.

## Cost Model

The derived-vs-source inversion is the expensive failure. A symptomatic fix in a failing test looks green until the next `validate_symbols_coverage.py` invocation re-flags the underlying drift; debugging the re-emergence pays the full trace cost twice (once to locate the downstream symptom, again to realize the YAML was always the cause). The compounding case is worse: a test weakened to silence a drift warning permanently hides the YAML defect until a downstream component mis-integrates on the un-declared contract.

## [HARD] Fix-upstream invariant

When a component's responsibilities, raises-list, exception name, shared-type shape, or test invariant is wrong, the fix lands in the owning YAML -- not in the runtime class and not in the assertion that caught it. Edit the YAML, re-run the validation chain, commit. The only legitimate reason to touch a derived file is when the validator itself is wrong; that is a separate defect class, not a YAML-authority violation.

## Remediation path routing

| Symptom surface | Authoritative YAML |
|---|---|
| Component responsibilities, must_not, features, or raises-list wrong | `plans/component-contracts.yaml` |
| Exception class, shared type, Settings field, or error-message symbol wrong | `plans/symbols.yaml` |
| Seam / layer assignment / external-terminal drift | `plans/seams.yaml` |

After the YAML edit: `validate_symbols_coverage.py` re-verifies the cross-YAML reference loop; the re-run is the evidence the fix landed.

Note: `seams.yaml.allowed_layers` and `seams.yaml.external_terminals` are written by `/io-plan-batch` Step X (Phase 5+) and consumed by the scope-cap cache materializer at State 5. Treat as authority within the `seams.yaml` owning surface -- no duplication into derived files.
