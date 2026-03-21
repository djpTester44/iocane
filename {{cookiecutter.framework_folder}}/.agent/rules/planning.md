---
trigger: glob
description: Planning constraints. Loaded automatically by /io-architect and /io-plan-batch.
globs: plans/**, interfaces/**
---

# PLANNING MODE RULES

> **Context:** You are in the DESIGN or TASKING phase. You must NOT write implementation code.

## [HARD] State Management & Architecture (Phase 1)

1. **The Living Document**: `plans/project-spec.md` is the ultimate authority and the core of the project's state.
2. **Design Before Contract (Macro Tier)**: You **MUST** define the **Component Specification (CRC & Sequence)** in `plans/project-spec.md` *before* generating or modifying `.pyi` files.
    - **Constraint:** Use the standard defined in `.claude/skills/mini-spec/SKILL.md`.
3. **Mandatory Updates**: You **MUST** update `plans/project-spec.md` (Interface Registry, Component Specifications, and Mermaid Graph) to reflect any new components or architectural shifts.
4. **Atomic Scope**: Each Protocol (`.pyi`) should represent a single responsibility and map to a single Component Specification.
5. **Interface Rules**:
    - Use `typing.Protocol` or `abc.ABC`.
    - Methods must be empty (`...`). NEVER write function bodies.
    - ALL methods must have Google-style docstrings defining Args, Returns, and PRD business logic constraints.
    - **Traceability:** Docstrings must explicitly reference the specific Responsibility from the CRC that the method satisfies.
    - **Exemptions:** Private methods (`_`-prefixed) are internal implementation details excluded from **both** CRC Key Responsibilities **and** `.pyi` Protocols. Only public methods participate in the Design layer. Sequence Diagrams are only required for components with behavioral logic (method chains, collaborator interactions); immutable data containers and thin wrappers are exempt.
    - You **MUST** export the new Protocol in `interfaces/__init__.pyi`.

## [HARD] Task Generation (Phase 2)

1. **Output Format**: The output of the tasking phase is exclusively `plans/tasks.json`.
2. **Atomic Granularity**: You **MUST** break implementation into atomic Red-Green-Refactor steps.
    - *Bad Task*: "Implement DataLoader."
    - *Good Tasks*: Task 1: "Scaffold class". Task 2: "Write failing test". Task 3: "Implement logic".
3. **Context Locking**: Every task in `tasks.json` **MUST** include:
    - A `context_files` array listing the exact `.py` and `.pyi` files required to *read* for that step.
    - A `write_targets` array listing the exact files the task will *write*. Required for `setup`, `test`, and `implement` tasks. Optional (may be empty) for `refactor` and `verify` tasks.
    - `write_targets` must be a strict subset of `context_files` — you cannot write a file you have not also declared as a read target.
    - **[HARD] Rejection Gate:** If any `setup`, `test`, or `implement` task has an empty `write_targets` array, the tasking output is REJECTED. If any task has an empty `context_files` array, the tasking output is REJECTED. Vague tasks cause grep-spam and lazy-dump violations downstream. Treat missing arrays as blocking defects.

## [HARD] Requirements Analysis

1. **No Speculation**: Do not assume a library or function exists. Verify strictly using a search tool (content or filename) before proceeding.
2. **Integration Integrity**: If a Checkpoint modifies the critical path (Input -> Logic -> Output), you **MUST** include a task to run/update `tests/test_integration_golden_path.py`.

## DESIGN PRINCIPLES

- **Loose coupling:** Components should depend on abstractions, not concrete implementations.
- **Dependency injection:** Pass dependencies as constructor/function arguments; avoid hardcoded instantiation.
- **Testability by design:** If a component is hard to test in isolation, redesign it.
- **Single source of configuration:** When tempted to create a new configuration file (e.g., `settings.container.yaml`), ask: "Can the existing file work with deployment-layer adjustments (volume mounts, ConfigMaps) instead?" Prefer one config file with environment-specific wiring over two files that can drift.
- Prefer simple solutions. Do not over-engineer with new workflows, sub-fields, or abstractions unless the user explicitly asks. When in doubt, ask before adding complexity.

## ANTI-PATTERNS

- Implementation details during planning phase.
- Concrete classes instead of Protocols.
- Missing type hints on signatures.
- **Config duplication:** Creating parallel configuration files for different environments instead of adjusting deployment wiring (volume mounts, env vars, ConfigMaps) around a single source of truth.
