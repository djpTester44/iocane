# Command Conventions

Reference for authoring and reviewing `.claude/commands/*.md` files.

## What Commands Own

Commands own **sequenced workflows with approval gates**. Every command is a procedure that routes the user (or sub-agent) through a series of steps where ordering matters and at least some steps require verification before proceeding.

If there are no gates and no ordering constraints, it's not a command -- it's a skill or a rule.

## Structural Template

Every command follows this skeleton:

```yaml
---
name: <command-name>
description: <one-line purpose>. <Tier level>. <Key constraint>.
---
```

```markdown
# WORKFLOW: <COMMAND-NAME>

<!-- Chain positioning (where does this command sit in the pipeline?) -->
`<predecessor> -> [<this-command>] -> <successor>`

## 1. STATE INITIALIZATION

<!-- What context must be loaded and what metadata must be validated before proceeding -->

## 2. PROCEDURE

### Step A: <STEP NAME>
<!-- Each step: action, verification, gate if applicable -->

### Step B: [HARD GATE] <GATE NAME>
<!-- Gates block progression until satisfied -->

...

## 3. CONSTRAINTS
<!-- Invariants that apply across all steps -->
```

### Required Elements

- **YAML frontmatter**: `name` and `description`. Description should state the tier level and the command's position in the workflow chain.
- **Chain positioning**: ASCII diagram showing predecessor/successor commands. If the command is invoked standalone, say so.
- **State initialization**: What files to load, what metadata to check. Some commands load heavily (io-architect loads 5 files); others deliberately constrain context (io-execute loads only its task file).
- **Numbered procedure**: Steps in execution order. Each step should have a clear action and a way to verify it succeeded.
- **Constraints section**: Invariants that hold across all steps.

### Gate Types

| Marker | Meaning | When to use |
|--------|---------|-------------|
| `[HARD GATE]` | Blocks progression; must pass before continuing | Preconditions that are objectively verifiable (file exists, stamp present) |
| `[HUMAN GATE]` | Requires human approval before continuing | Design decisions, tier boundaries, approval checkpoints |
| `[CRITICAL]` | Marks high-consequence context or actions | Context loading that must happen first, actions with irreversible side effects |

A command without at least one gate is suspicious -- if nothing blocks progression, why is ordering enforced?

## Earned-Prose Filter for Commands

Run each step through these three questions:

**1. Does this step require human approval before continuing?**
YES -- Keep as a gate. Gates are the command's core value.
NO -- Continue.

**2. Does step ordering matter? Would skipping or reordering cause a wrong outcome?**
YES -- Keep. Sequence is what commands own.
NO -- Delete. If it's reasoning, move to a rule. If it's domain knowledge, move to a skill.

**3. Is this step verifiable? Can you tell whether it succeeded?**
YES -- Keep. Name the verification (file exists, test passes, stamp present).
NO -- Delete. Unverifiable steps are waste -- they look rigorous but don't constrain execution.

## Context Loading Patterns

Commands vary in how much context they load, and the choice is deliberate:

- **Heavy load** (io-architect, io-review): Tier 1 commands that need cross-artifact awareness. Load planning rules, specs, CRC cards, protocols.
- **Minimal isolation** (io-execute): Tier 3 sub-agent commands that must NOT have cross-checkpoint awareness. Explicitly constrain to task file only.
- **Selective** (io-orchestrate): Load only dispatch-relevant state, not implementation details.

State how much context to load and why. "Load everything" and "load nothing" are both valid strategies -- the mistake is not explaining which one you chose.

## Anti-Patterns

1. **Advisory prose with no gate**: "Consider the impact of this change." There is no gate, no verification, no ordering constraint. This is a thought, not a step. Move to a rule if it's cost reasoning; otherwise delete.

2. **Steps that can't be verified**: "Ensure the design is high quality." What does verification look like? If you can't name a check (file exists, test passes, human approves), the step is unenforceable.

3. **Chain positioning that doesn't match actual invocation**: The diagram says `io-specify -> [io-architect]` but nothing actually prevents running io-architect without io-specify. If the chain is advisory, say so. If it's enforced (by a gate checking for predecessor artifacts), name the gate.

4. **Escalation without conditions**: "Escalate if something goes wrong." Name the specific triggers. io-execute does this well: table of 5 failure triggers, each with a named condition and action.

5. **Context loading without justification**: Loading 5 files without saying why leads to copy-paste across commands. Some commands deliberately avoid loading context (io-execute). The choice is the design; document it.

## Canonical Exemplars

When in doubt, model after these:

- **io-architect.md** -- Tier 1 approval flow: heavy context load, human gate at design boundary, explicit artifact writes
- **io-execute.md** -- Tier 3 autonomous execution: minimal context isolation, step checkboxes for resumption, escalation table with named triggers
- **io-review.md** -- Verification pipeline: 10-step linear review, findings taxonomy (HIGH/MEDIUM/LOW/INFO), human gate at approval decision
