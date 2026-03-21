---
paths:
  - "plans/project-spec.md"
  - "plans/roadmap.md"
  - "plans/plan.md"
  - "interfaces/**"
---

# PLANNING MODE RULES

> **Context:** You are in the DESIGN phase. You must NOT write implementation code.

## [HARD] State Management & Architecture

1. **The Living Document**: `plans/project-spec.md` is the ultimate authority and the core of the project's state.
2. **Design Before Contract**: You **MUST** define the **Component Specification (CRC & Sequence)** in `plans/project-spec.md` *before* generating or modifying `.pyi` files.
    - **Constraint:** Use the standard defined in `.claude/skills/mini-spec/SKILL.md`.
3. **Mandatory Updates**: You **MUST** update `plans/project-spec.md` (Interface Registry, Component Specifications, and Mermaid Graph) to reflect any new components or architectural shifts.
4. **Atomic Scope**: Each Protocol (`.pyi`) should represent a single responsibility and map to a single Component Specification.
5. **Interface Rules**:
    - Use `typing.Protocol` or `abc.ABC`.
    - Methods must be empty (`...`). NEVER write function bodies.
    - ALL methods must have Google-style docstrings defining Args, Returns, and PRD business logic constraints.
    - **Traceability:** Docstrings must explicitly reference the specific Responsibility from the CRC that the method satisfies.
    - **Exemptions:** Private methods (`_`-prefixed) are excluded from both CRC Key Responsibilities and `.pyi` Protocols. Sequence Diagrams are only required for components with behavioral logic; immutable data containers and thin wrappers are exempt.
    - You **MUST** export the new Protocol in `interfaces/__init__.pyi`.

## [HARD] Orchestration Output Format

`/io-orchestrate` generates per-checkpoint task files at `plans/tasks/[CP-ID].md` and a dispatch script at `plans/tasks/run.sh`. Do not manually create or edit these files — they are orchestrator artifacts.

Each task file contains: objective, write targets, context files, and gate command. Sub-agents read only their assigned task file.

## [HARD] Requirements Analysis

1. **No Speculation**: Do not assume a library or function exists. Verify strictly using a search tool before proceeding.
2. **Integration Integrity**: If a Checkpoint modifies the critical path (Input -> Logic -> Output), you **MUST** include a task to run/update `tests/test_integration_golden_path.py`.

## DESIGN PRINCIPLES

- **Loose coupling:** Components should depend on abstractions, not concrete implementations.
- **Dependency injection:** Pass dependencies as constructor/function arguments; avoid hardcoded instantiation.
- **Testability by design:** If a component is hard to test in isolation, redesign it.
- **Single source of configuration:** Prefer one config file with deployment-layer wiring (volume mounts, env vars, ConfigMaps) over parallel environment-specific files that can drift.
- Prefer simple solutions. Do not over-engineer with new workflows, sub-fields, or abstractions unless explicitly asked.

## ANTI-PATTERNS

- Implementation details during planning phase.
- Concrete classes instead of Protocols.
- Missing type hints on signatures.
- Config duplication: creating parallel configuration files instead of adjusting deployment wiring around a single source of truth.
