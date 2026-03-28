---
paths:
  - "plans/backlog.md"
---

# TICKET TAXONOMY

Backlog items in `plans/backlog.md` carry one tag that governs routing.

## Valid Tags

| Tag | Definition |
|-----|------------|
| `[DESIGN]` | A change that requires generating or updating a CRC card AND modifying/creating a `.pyi` contract. |
| `[REFACTOR]` | A behavioral change that requires a CRC update, but NO new `.pyi` interface (the contract signature remains exactly the same). |
| `[CLEANUP]` | A pure internal code, style, or logic fix. No design or contract change needed. |
| `[DEFERRED]` | Known technical debt implicitly accepted for the current phase. Ignored by execution gates. |
| `[TEST]` | Missing test coverage. |

