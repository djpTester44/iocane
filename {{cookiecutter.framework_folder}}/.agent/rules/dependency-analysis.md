---
trigger: glob
description: Architectural dependency analysis constraints. Loaded by /dep-check and /io-loop verify.
globs: **/*.py
---

# DEPENDENCY ANALYSIS RULES

> **Context:** These rules govern when and how to use `import-linter` during development and verification.

## [HARD] When to Run

1. **After any `import` change** in source packages (as defined in `pyproject.toml`): You **MUST** run a dependency check before marking a task complete.
2. **During `/io-loop` verify steps**: Run `uv run rtk lint-imports`.
3. **During `/io-review` pre-scan**: Run `uv run rtk lint-imports` to surface coupling and contract compliance.

## [HARD] Contract Enforcement

1. **Contracts are workspace-specific**: Read `pyproject.toml` [tool.importlinter] for the current workspace's root packages and contracts.
2. **Self-layer imports are allowed**: Only **cross-layer** or **independence** boundaries are governed as defined in the contracts.

## Commands

### Full Check (CI, used during verify steps)

```bash
uv run rtk lint-imports
```

### Visual Exploration

```bash
uv run rtk import-linter explore <package>
```

e.g. `uv run rtk import-linter explore lib` OR `uv run rtk import-linter explore jobs`
(Note: with `src` layout, you may need to use `src.lib` if top-level imports are not preserved in the tool, but `pyproject.toml` config usually handles the root)

## Interpreting Violations

1. **Circular dependency**: Extract shared types into a common module, or inject the dependency via constructor parameter.
2. **Independence violation**: Peer packages are importing each other. Refactor to a shared interface in `interfaces/` and inject via DI.
3. **Layer violation**: A lower layer is importing from a higher layer. Refactor to receive the dependency via injection.

## [CRITICAL] Technical Debt

1. **NEVER suppress a violation** by removing a contract.
2. If a violation exists but cannot be fixed (e.g., structural coupling to DTOs), it **MUST** be added to `ignore_imports` with a comment tracking it for a future DTO-separation phase.
3. Always check the `ignore_imports` list to understand current known architectural debt.
