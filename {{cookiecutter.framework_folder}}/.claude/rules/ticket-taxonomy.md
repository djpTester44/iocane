---
paths:
  - "plans/backlog.yaml"
---

# TICKET TAXONOMY

Backlog items in `plans/backlog.yaml` carry one tag that governs routing.

## Valid Tags

| Tag | Definition |
|-----|------------|
| `[DESIGN]` | A change that requires generating or updating a CRC card AND modifying/creating a `.pyi` contract. |
| `[REFACTOR]` | A behavioral change that requires a CRC update, but NO new `.pyi` interface (the contract signature remains exactly the same). |
| `[CLEANUP]` | A pure internal code, style, or logic fix. No design or contract change needed. Includes spec-conformance fixes where the CRC already documents the correct behavior and only the implementation is wrong. |
| `[DEFERRED]` | Known technical debt implicitly accepted for the current phase. Ignored by execution gates. |
| `[TEST]` | Missing test coverage. |
| `[CI-REGRESSION]` | Test passing before dispatch wave, failing after. Identified by ci-sidecar pre/post diff. |
| `[CI-COLLECTION-ERROR]` | Test file fails to collect after dispatch wave. May indicate structural breakage or obsolete test. |
| `[CI-EXTERNAL]` | Test failure caused by external factors. Triage reclassification only -- never produced by the sidecar script. Applied by human when a `[CI-REGRESSION]` item turns out to be a flaky external dependency. |

