# Rule Conventions

Reference for authoring and reviewing `.claude/rules/*.md` files.

## What Rules Own

Rules own **cost reasoning and value judgments** that shape the agent's behavior before any enforcement point fires. A rule's job is to make Claude understand what goes wrong -- and how expensive it is -- when a constraint is violated.

If a hook already enforces the constraint deterministically, the rule is redundant. If the content is a procedure with steps and gates, it belongs in a command. If it's domain knowledge that reduces output variance, it belongs in a skill.

## Structural Patterns

### Global Rules (no frontmatter)

Apply to every session. Every line costs tokens on every interaction. Use for constraints that genuinely affect all work -- scope discipline, navigation protocol, execution philosophy.

```markdown
# RULE TITLE

> Context-setting blockquote or cost premise.

## Section (with optional [HARD] or [CRITICAL] markers)

Content...
```

No YAML frontmatter. The absence of `paths:` means the rule loads unconditionally.

**Token budget implication**: Because global rules tax every session (including sub-agents), they face the strictest earned-prose bar. A single unnecessary line in a global rule is multiplied across every session and every sub-agent invocation.

### Scoped Rules (YAML frontmatter)

Apply only when matching files are edited. Use for constraints specific to a file type or directory.

```yaml
---
paths:
  - "src/**/*.py"
---
```

```markdown
# RULE TITLE

> Context statement explaining when these rules apply.

## Section
...
```

Scoped rules have a lower token-waste cost because they only load in matching contexts. But the earned-prose filter still applies -- if a linter or hook already enforces the constraint, the prose is redundant regardless of scope.

## The Earned-Prose Filter

The three questions from the framework, applied as an operational checklist:

**1. Can a hook, linter, or script enforce this with an exit code?**
YES -- Delete the prose. The architecture owns it. Check `plans/harness-assessment.md` for the hook inventory; if a hook already covers this, the rule is duplication.
NO -- Continue.

**2. Does Claude's understanding of this constraint change its behavior BEFORE the enforcement point fires?**
YES -- Keep as a rule. Write it as reasoning about cost, not as mechanics.
NO -- Delete. It's either redundant with the enforcement or untriggerable (Claude can't act on it at the moment it loads).

**3. Is this teaching Claude what to DO or WHY to do it?**
WHAT -- Compress to one line or delete. Claude already knows how tools work.
WHY -- Keep. This is the actual rule. Frame it as: "What does it cost when this goes wrong?"

## Cost Reasoning Patterns

Two effective patterns for structuring cost reasoning:

### Front-loaded cost premise (navigation.md pattern)

Open with the cost statement, then list the failure modes it prevents:

```markdown
# NAVIGATION PROTOCOL: Read Surgically, Not Speculatively

Every file read costs context window tokens -- the scarcest resource in a session.

## Failure Modes to Avoid
1. **The "Lazy Dump"**: Reading an entire large file when only one function was needed...
```

Best for: short, focused rules where a single cost premise motivates everything that follows.

### Contextual cost explanations (architecture-gates.md pattern)

Embed cost reasoning alongside each section, explaining why the gate exists:

```markdown
## DI COMPLIANCE

### The AST Limitation
The DI gate hook uses AST analysis, which cannot detect [specific limitation].
This means Claude must understand [the reasoning] to avoid [the cost]...
```

Best for: multi-section rules where different sections have different cost justifications.

## Enforcement Markers

| Marker | Meaning | Use when |
|--------|---------|----------|
| `[HARD]` | Violation causes immediate failure or incorrect output | The cost of violation is high and the constraint is objectively verifiable |
| `[CRITICAL]` | Highest-consequence constraint | Violation is catastrophic or irreversible (e.g., leaked secrets, corrupted state) |
| *(no marker)* | Guidance that improves quality but isn't blocking | The cost is real but the failure mode is recoverable |

Don't overuse markers. If every section is `[HARD]`, none of them stand out. Reserve `[CRITICAL]` for genuinely irreversible failure modes like secret leaks or data corruption.

## Anti-Patterns

1. **Procedural rules**: Step-by-step instructions in a rule file. Procedures belong in commands. Rules should state the cost, not the sequence.

2. **Linter-enforceable rules**: "Always use type hints." If Ruff or mypy enforces this, the prose is redundant. The linter runs deterministically; the rule is noise.

3. **Hook-duplicated rules**: Check the hook inventory in `plans/harness-assessment.md`. If `write-gate.sh` already enforces write boundaries, prose restating that boundary in a rule is duplication.

4. **Untriggerable rules**: Content that can't change Claude's behavior at rule-load time. "After deployment, verify the service is healthy." Claude isn't deploying anything when this rule loads.

5. **Scope-cost mismatch**: A global rule (no `paths:`) that only applies to Python files. Use YAML `paths:` to scope it -- otherwise it taxes every session including ones that never touch Python.

## Canonical Exemplars

- **navigation.md** -- Gold standard for cost-first reasoning. 12 lines, global scope, every line earns its place. Front-loaded cost premise, numbered failure modes.
- **scope-discipline.md** -- Enforcement markers used well. `[HARD]` on three genuinely blocking constraints. Opening blockquote sets the stakes.
- **architecture-gates.md** -- Scoped rule (`src/**/*.py`). Contextual cost reasoning per section. 3-level heading depth for complex multi-topic rules.
