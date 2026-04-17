---
paths:
  - "plans/roadmap.md"
  - "plans/component-contracts.yaml"
  - "plans/seams.yaml"
  - "plans/symbols.yaml"
  - "plans/test-plan.yaml"
  - "plans/plan.yaml"
  - "interfaces/**"
---

# PLANNING MODE RULES

## [HARD] State Management & Architecture

1. **Canonical set**: The project's design state is the combined content of `plans/component-contracts.yaml` (CRC), `interfaces/*.pyi` (Protocols + shared types + exceptions), `plans/symbols.yaml` (cross-CP identifiers), `plans/test-plan.yaml` (per-method invariants), and `plans/seams.yaml` (DI graph). No single file is "the" authority -- they are mutually consistent by design, with the architect stamping `test-plan.yaml.validated: true` after the H-post-validate gates pass.
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
