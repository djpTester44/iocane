---
paths:
  - "src/**/*.py"
---

# ARCHITECTURE GATES

> **Context:** These rules govern structural compliance checks during implementation.

## DI COMPLIANCE

### The AST Limitation

`.claude/scripts/check_di_compliance.py` uses static AST parsing. It will flag a `[CRITICAL]` violation if it cannot statically verify that a collaborator is injected via `__init__`. It cannot parse dynamic unpacking (`**kwargs`), factory patterns, or delayed initialization.

### [HARD] The Escape Hatch

If your implementation requires dynamic injection or a factory pattern that legitimately bypasses the AST parser, use `# noqa: DI`. Using `# noqa: DI` is an admission of tech debt. Using it to bypass a failing test is forbidden.

For module-level instantiation violations, use `# noqa: DI-MODULE`. Same rules apply.

### [HARD] Layout Boundaries

Components outside `src/` break import-linter contracts and the DI compliance check -- a single misplaced file fails the entire architecture gate.

**Cross-reference:** The `interfaces/` directory invariant (`.pyi` stubs only, no runtime `.py` files) is enforced at the planning layer by `/io-checkpoint` Section 3, `/validate-plan` Step 7, and `/io-review` Step D.

---

## DEPENDENCY ANALYSIS

### [HARD] Contract Enforcement

Self-layer imports are allowed -- only cross-layer or independence boundaries are governed.

### [CRITICAL] Technical Debt

NEVER suppress a violation by removing a contract. If a violation cannot be fixed, document it in `ignore_imports` with a comment tracking it for a future phase.
