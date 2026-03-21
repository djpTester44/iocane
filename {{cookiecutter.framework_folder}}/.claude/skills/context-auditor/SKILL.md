---
name: context-auditor
description: Analyzes the codebase to identify architectural risks and dependencies before implementation. Use when planning new features, assessing impact of changes, or reviewing architecture for potential issues like circular dependencies or SOLID violations.
---

# Context Auditor

Analyze codebase for architectural risks and dependencies before implementation.

## Trigger Examples

- "What would this change affect?"
- "Analyze dependencies before I refactor"
- "Check for circular dependencies"
- "Review architecture for SOLID violations"
- "What would break if I change this Protocol?"

## Workflow

1. **Scan Context** - Examine file structure, `PLAN.md`, and `interfaces/*.pyi`
2. **Analyze Impact** - For a given `feature_request`, determine:
   - Which modules will need to change
   - Which Protocols (from interfaces/) are affected
   - Existing patterns (Factories, Adapters) that must be used
   - Potential circular dependencies
   - Use the symbol-tracer skill (`uv run symbol_tracer.py --symbol "<Symbol1>,<Symbol2>" --root src/ --summary`) to trace cross-file references instead of reading implementation files directly
3. **Output** - Produce an "Impact Report" containing:
   - Affected Modules
   - Affected Protocols
   - New Dependencies
   - Potential SRP/LSP Violations
   - Risk Score (Low/Medium/High)

## Output Format

```markdown
## Impact Report: [Feature Name]

### Affected Modules
- [module_a.py]: [reason]
- [module_b.py]: [reason]

### Affected Protocols
- [interfaces/component.pyi]: [reason]

### New Dependencies
- [module] -> [new_dependency]

### Potential Violations
- **SRP**: [description]
- **LSP**: [description]

### Risk Score: [Low/Medium/High]
[Justification]
```