# Skill Conventions

Reference for authoring and reviewing `.claude/skills/*/SKILL.md` files within this harness. This covers harness-specific conventions -- for generic skill creation mechanics (evals, description optimization, progressive disclosure), defer to `skill-creator`.

## What Skills Own

Skills own **reusable domain knowledge that reduces output variance**. A skill's job is to carry the patterns, templates, and constraints that Claude can't reliably infer from caller context alone. Without the skill, Claude would produce inconsistent or incorrect results across invocations.

If the content is cost reasoning about when things go wrong, it belongs in a rule. If it's a sequenced workflow with approval gates, it belongs in a command. If it's something a hook can enforce, it belongs in a hook.

## Structural Template

```yaml
---
name: <skill-name>
description: <what it does>. <when to use -- be pushy>. <when NOT to use if ambiguous>.
---
```

```markdown
# <Skill Name>

<One-line goal statement.>

## Trigger Examples (optional)
- "Natural language prompt that should invoke this skill"

## Workflow
1. Step one
2. Step two

## Required Input (when skill expects caller-provided context)
Caller MUST provide (do not fetch):
- `input_name`: description

## Output Format
<template or JSON structure>

## Constraints / When to Use
<Situational guidance, domain-specific limitations>
```

### Section Guidance

Not every section is required. Use what the skill needs:

- **Trigger Examples**: Useful when the skill's scope is non-obvious. Skip for skills with self-explanatory names.
- **Required Input**: Use when the skill depends on context the caller must paste (not fetch). Prevents the skill from doing redundant reads. See minimal-coder as exemplar.
- **Output Format**: Use when output structure matters for downstream consumption. Can be JSON, markdown template, or prose description.
- **Constraints / When to Use**: Domain-specific boundaries. "Use during TDD red-to-green phase" (minimal-coder). "NO implementation logic allowed" (spec-writer).

## Earned-Prose Filter for Skills

**1. Does this knowledge reduce output variance?** Would Claude produce inconsistent results across invocations without it?
YES -- Keep. Variance reduction is the skill's core value.
NO -- Continue.

**2. Is this a pattern or template Claude can't infer from the caller's context alone?**
YES -- Keep. This is domain knowledge the model lacks.
NO -- Delete. You're restating what the model already knows.

**3. Is this constraint or trigger guidance?**
CONSTRAINT ("never do X in this domain") -- Keep in the skill body.
TRIGGER ("when to invoke me") -- Keep only in the YAML description. Don't duplicate inside.
NEITHER -- Delete.

## Description Writing

The YAML `description` is the primary trigger mechanism. It determines whether Claude consults the skill at all. Key principles:

- **Be pushy**: Claude undertriggers skills. Include synonyms and adjacent concepts. "Use when creating commands, writing workflows, authoring command files, defining workflow steps, or reviewing command structure" is better than "Use when creating commands."
- **Name the boundary**: If this skill is close to another skill's domain, state what this one does NOT cover. "Do NOT use for generic skill creation mechanics -- that belongs to skill-creator."
- **Trigger info lives here only**: Don't duplicate "when to use" guidance inside the skill body. The body earns its prose through domain knowledge, not trigger logic.

## Relationship to skill-creator

| Concern | Owner |
|---------|-------|
| How to structure a SKILL.md (progressive disclosure, <500 lines) | `skill-creator` |
| How to run evals and optimize descriptions | `skill-creator` |
| What content belongs in *this harness's* skills | `harness-author` (this skill) |
| Whether prose earns its place in a skill | `harness-author` (this skill) |

When creating a new skill for this harness, use both: `skill-creator` for the mechanics, `harness-author` for the convention compliance.

## Anti-Patterns

1. **General knowledge restated**: "Use type hints on all function signatures." Claude does this by default; the linter enforces it. The skill adds zero variance reduction.

2. **Trigger guidance in the body**: "Use this skill when you need to..." This belongs in the YAML description. Inside the body, it wastes tokens on every invocation -- the skill already triggered.

3. **Overly prescriptive MUSTs**: "You MUST ALWAYS format output EXACTLY as shown." Explain why the format matters instead. Heavy-handed imperatives are a yellow flag that the reasoning isn't earning its keep. If Claude understands why the format matters (downstream parser expects it, human reviewer scans for specific headings), the correct behavior follows.

4. **Monolithic skills without progressive disclosure**: A 600-line SKILL.md that covers 4 domains inline. Use `references/` to organize by variant -- Claude loads only the relevant reference file.

5. **Competing with existing skills**: Before creating a skill, check whether an existing skill already covers the domain. Enhance the existing skill rather than creating a competitor with overlapping triggers.

## Canonical Exemplars

- **context-auditor** -- Analysis skill: trigger examples, 3-step workflow, markdown output template. Clean and focused.
- **minimal-coder** -- Execution skill: explicit Required Input block, permissions section, JSON output format. Shows how to constrain caller responsibility.
- **refactor-guru** -- Diagnostic skill: checklist format with checkbox sub-sections, violations catalog output. Shows the checklist pattern for quality gates.
