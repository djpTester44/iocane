---
paths:
  - "plans/project-spec.md"
  - "plans/roadmap.md"
  - "plans/plan.yaml"
  - "interfaces/**"
---

# PLANNING MODE RULES

## [HARD] State Management & Architecture

1. **The Living Document**: `plans/project-spec.md` is the ultimate authority and the core of the project's state.
2. **Atomic Scope**: Each Protocol represents a single responsibility, mapping to one CRC card.

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
