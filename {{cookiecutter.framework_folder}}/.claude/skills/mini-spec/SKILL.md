---
name: mini-spec
description: Generates CRC cards and Sequence Diagrams to anchor behavioral logic before coding.
---

# MINI-SPEC: Behavioral Anchoring

> **Purpose:** To prevent "Unanchored Code" by defining the internal behavior (Design) of a component before the Type Signature (Contract) is written.

## 1. Position in the Workflow

```
PRD -> /io-clarify -> /io-specify -> [/io-architect uses mini-spec] -> /io-checkpoint -> /io-orchestrate
```

This skill is invoked by `/io-architect` during the CRC card and Protocol design steps. It defines what a component does (Design) before the `.pyi` contract is written (Contract).

## 2. CRC Card Standard

Class-Responsibility-Collaboration (CRC) cards map the observable behavior of a component.

**Format:**

```markdown
### [ComponentName]
**Layer:** [1-Foundation | 2-Utility | 3-Domain | 4-Entrypoint]
**File:** `src/[path]/[module].py`
**Protocol:** `interfaces/[protocol].pyi`

**Responsibilities:**
- `[CURRENT]` [Responsibility verified in existing code — cite file:line]
- `[TARGET]` [Responsibility not yet implemented — design intent]
- [Each responsibility is testable in isolation]
- [If a CURRENT responsibility diverges from TARGET design, add a prose note beneath]

**Collaborators:**
- [ComponentName] via [ProtocolName] — [why needed]

**Must NOT:**
- [Explicit negative constraint — what this component must never do]
```

**Heuristics:**

- **Observable behaviors only:** Responsibilities describe outcomes, not implementation steps. "Validates payload against domain model" not "calls `.model_validate()` on input dict".
- **One card, one concept:** If a card has more than 7 responsibilities, break it into two components.
- **Traceability:** Every responsibility must map to at least one public method in the Protocol. Private helpers (`_`-prefixed) do not appear in CRC cards.
- **Must NOT is mandatory:** At least one negative constraint per card. Derive from the layer rules in `pyproject.toml` import-linter config (e.g., "Must NOT import from `src/domain/`").
- **Current/Target tagging is mandatory:** Every responsibility line carries exactly one tag: `[CURRENT]` (verified, with `file:line` citation) or `[TARGET]` (design intent). In greenfield projects, all responsibilities are `[TARGET]`.

## 3. Sequence Diagram Standard

Use Mermaid to lock down the critical execution path — side effects, external calls, and error branches.

**Format:**

```mermaid
sequenceDiagram
    participant Caller
    participant Component
    participant Collaborator

    Caller->>Component: method_name(params)
    Component->>Collaborator: collaborator_method(args)
    Collaborator-->>Component: result
    Component-->>Caller: ReturnType
```

**Heuristics:**

- **Happy path + primary failure mode:** Always diagram the success flow. Add a failure branch if the error responsibility is non-obvious (e.g., who raises `UserNotFoundError` when the repo returns `None`).
- **Show data at boundaries:** Label arrows with the type or shape of data crossing each seam — not variable names.
- **Non-trivial flows only:** Simple pass-through components do not need a sequence diagram.

## 4. Gap Analysis Rules

When auditing code against design:

1. **Unanchored Code:** Implementation contains logic NOT in the CRC.
   - Action: Add the behavior to the CRC, or remove it from the code.
   - Exemption: `_`-prefixed methods are internal implementation details. Do not flag them.

2. **Missing Implementation:** CRC lists a responsibility NOT in the implementation.
   - Action: Implement it.
