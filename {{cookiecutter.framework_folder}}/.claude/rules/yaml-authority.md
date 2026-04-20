---
paths:
  - "plans/**"
  - "interfaces/**"
  - "src/**"
  - "tests/**"
---

# YAML AUTHORITY: Fix Upstream, Re-derive Downstream

> `plans/*.yaml` is the source of truth for Protocol surface, runtime symbol registry, and test invariants. Everything under `interfaces/`, `src/`, and `tests/` is derived or validated against that source. When reasoning surfaces a wrongness downstream, the drift is almost always a YAML defect, and fixing the derived artifact leaves the YAML defect in place for the next codegen run to re-introduce.

## Cost Model

The derived-vs-source inversion is the expensive failure. A symptomatic fix at `interfaces/router.pyi` or in a failing test looks green until the next `/io-gen-protocols` run or the next `validate_symbols_coverage.py` invocation overwrites or re-flags it; debugging the re-emergence pays the full trace cost twice (once to locate the downstream symptom, again to realize the YAML was always the cause). The compounding case is worse: a test weakened to silence a drift warning permanently hides the YAML defect until a downstream component mis-integrates on the un-declared contract.

## [HARD] Fix-upstream invariant

When a Protocol method signature, exception name, shared-type shape, or test invariant is wrong, the fix lands in the owning YAML -- not in the `.pyi` stub, not in the runtime class, not in the assertion that caught it. Edit the YAML, re-run the codegen / validation chain, commit the regenerated output. The only legitimate reason to touch a derived file is when the codegen template or the validator itself is wrong; that is a separate defect class (`root_cause_layer: interfaces_codegen` or `test_harness`), not a YAML-authority violation.

## Remediation path routing

| Symptom surface | Authoritative YAML |
|---|---|
| Protocol method name/args/return_type/raises wrong | `plans/component-contracts.yaml` (edit `ComponentContract.methods`) |
| Exception class, shared type, Settings field, or error-message symbol wrong | `plans/symbols.yaml` |
| Test invariant wrong or missing | `plans/test-plan.yaml` |
| Seam / layer assignment / external-terminal drift | `plans/seams.yaml` |

After the YAML edit: `/io-gen-protocols` regenerates `interfaces/*.pyi`; `validate_symbols_coverage.py` + `validate_test_plan_completeness.py` re-verify the cross-YAML reference loop; the re-run is the evidence the fix landed.
