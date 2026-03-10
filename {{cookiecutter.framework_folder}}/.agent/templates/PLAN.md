# Plan

**Generated from:** plans/roadmap.md + plans/project-spec.md
**Plan Validated:** FAIL

---

## Checkpoints

### CP-01: [Checkpoint Name]
**Feature:** F-[NN] — [Feature name from roadmap.md]
**Description:** [One sentence — what is built and testable when this checkpoint is complete]
**Status:** [ ] pending

**Scope:**
- Component: [ComponentName] (`src/[path]/[module].py`)
- Protocol: `interfaces/[protocol].pyi`
- Methods implemented: `[method_name]`, `[method_name]`

**Write targets:**
- `src/[path]/[module].py`
- `tests/[path]/test_[module].py`

**Context files (read-only):**
- `interfaces/[protocol].pyi`
- `plans/project-spec.md` (CRC card for [ComponentName] only)

**Gate command:** `pytest tests/[path]/test_[module].py`

**Depends on:** none
**Parallelizable with:** none

---

### CP-02: [Checkpoint Name]
**Feature:** F-[NN] — [Feature name from roadmap.md]
**Description:** [One sentence — what is built and testable when this checkpoint is complete]
**Status:** [ ] pending

**Scope:**
- Component: [ComponentName] (`src/[path]/[module].py`)
- Protocol: `interfaces/[protocol].pyi`
- Methods implemented: `[method_name]`, `[method_name]`

**Write targets:**
- `src/[path]/[module].py`
- `tests/[path]/test_[module].py`

**Context files (read-only):**
- `interfaces/[protocol].pyi`
- `plans/project-spec.md` (CRC card for [ComponentName] only)

**Gate command:** `pytest tests/[path]/test_[module].py`

**Depends on:** CP-01
**Parallelizable with:** none

---

## Connectivity Tests

### CT-001: CP-01 → CP-02

```
test_id: CT-001
function: test_[descriptive_name]
file: tests/connectivity/test_cp01_cp02.py
fixture_deps: [[fixture_name]]
contract_under_test: interfaces/[protocol].pyi :: [ProtocolName].[method_name]
assertion: [What must be true about the return value — type, shape, invariants]
gate: pytest tests/connectivity/test_cp01_cp02.py::test_[descriptive_name]
```

---

## Feature Completion Map

| Feature | Checkpoints | Status |
|---------|-------------|--------|
| F-01: [name] | CP-01, CP-02 | [ ] |

---

## Self-Healing Log

[Populated by /validate-plan during auto-remediation passes]
