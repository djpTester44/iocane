---
paths:
  - "plans/roadmap.md"
  - "plans/component-contracts.yaml"
  - "plans/seams.yaml"
  - "plans/symbols.yaml"
  - "plans/plan.yaml"
---

# PLANNING MODE RULES

## [HARD] State Management & Architecture

1. **Canonical set**: The project's design state is the combined content of `plans/component-contracts.yaml` (CRC behavioral data + component-level raises-list), `plans/symbols.yaml` (cross-CP identifiers: exception classes, shared types, settings fields, fixtures, error messages), and `plans/seams.yaml` (DI graph). No single file is "the" authority -- they are mutually consistent by design.
2. **Atomic Scope**: Each component represents a single responsibility, mapping to one CRC card.

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
