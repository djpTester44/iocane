---
name: harness-author
description: Author, review, and refine Iocane harness artifacts -- rules, commands, and skills. Determines which artifact type a constraint belongs in, applies the earned-prose filter for that type, and enforces structural conventions. Use this skill whenever creating a new command, writing or reviewing a rule file, reviewing a skill for convention compliance, deciding whether something should be a rule vs a hook vs a command vs a skill, trimming prose from harness files, or assessing whether a harness artifact earns its place. Do NOT use for generic skill creation mechanics (evals, description optimization) -- that belongs to skill-creator.
---

# Harness Author

Author, review, and refine harness artifacts with the right prose in the right layer.

## The Problem This Solves

Every line in a harness artifact has a runtime cost. Rules consume context tokens on every matching file edit. Commands consume tokens on every invocation. Skills consume tokens whenever triggered. Prose that doesn't change behavior at the moment it loads is pure waste -- and worse, it dilutes the prose that does matter.

This skill ensures each artifact type contains only the prose that earns its place, in the layer where it has impact.

## Artifact Taxonomy

Before writing anything, determine which layer owns the constraint:

```
Can a hook or script enforce this with an exit code?
  YES --> Write the hook. Delete the prose entirely.
  NO  --> Continue.

Is this reasoning about cost, value, or judgment tradeoffs?
  YES --> Rule. (auto-loads when matching files are edited)
  NO  --> Continue.

Is this a multi-step workflow with sequenced gates and human approval points?
  YES --> Command. (invoked explicitly by the user)
  NO  --> Continue.

Is this reusable domain knowledge that reduces output variance across invocations?
  YES --> Skill. (triggered by task context)
  NO  --> It probably doesn't need to exist.
```

When something spans two layers, split it: the gate/sequence lives in the command, the domain knowledge lives in the skill, the cost reasoning lives in the rule. Never merge them.

## Earned-Prose Filters

Each artifact type has its own test for whether a line of prose earns its place. The tests are different because the failure modes are different.

### Rules -- "What does it cost when this goes wrong?"

Rules shape judgment before enforcement fires. Their failure mode is **wasted tokens on content that doesn't change behavior**.

Read `references/rules.md` before authoring or reviewing a rule file.

### Commands -- "Can this step be skipped, reordered, or verified?"

Commands own sequenced workflows with approval gates. Their failure mode is **steps that can't be verified**, producing workflows that look rigorous but don't actually constrain execution.

Read `references/commands.md` before authoring or reviewing a command file.

### Skills -- "Would Claude produce inconsistent results without this?"

Skills carry domain knowledge the model can't infer from context alone. Their failure mode is **restating what the model already knows**, wasting tokens on zero-variance content.

Read `references/skills.md` before authoring or reviewing a skill.

## Cross-Cutting Anti-Patterns

These appear across all artifact types:

1. **Hook duplication** -- Prose that restates what a hook already enforces. The hook runs deterministically; the prose is redundant. Delete it.

2. **Layer bleeding** -- A rule that contains procedural steps (belongs in a command), or a command that contains cost reasoning with no gate attached (belongs in a rule). Each layer has a job; don't mix them.

3. **Phantom constraints** -- Prose that sounds authoritative but can't be verified at any point in the workflow. "Always ensure high quality" teaches nothing. Either name the verification or delete the line.

4. **Cross-layer duplication** -- The same constraint stated in both a rule and a command. Pick the layer where it has impact and delete the other copy.

5. **General knowledge restated** -- "Use type hints on function signatures" in a project where the linter enforces it and the model does it by default. Two enforcement points already exist; the prose adds nothing.

6. **Over-trimming well-constructed files** -- Not every file needs trimming. If every line passes the earned-prose filter and no anti-patterns (1-5) actually apply, the verdict is CLEAN. The anti-pattern checklist is a diagnostic tool, not a mandate to find problems. Forcing a TRIM verdict on a clean file wastes review effort and risks removing prose that earns its place.

## Workflow

1. **Classify** -- Determine which artifact type(s) the task involves. Load the relevant reference file(s).
2. **Apply filter** -- Run each line of prose through the earned-prose test for that artifact type.
3. **Check structure** -- Verify the artifact matches the structural template for its type (frontmatter, sections, conventions).
4. **Check boundaries** -- Confirm no layer bleeding or cross-layer duplication with existing artifacts. Use `plans/harness-assessment.md` as the inventory reference if available.
5. **Output** -- Produce the artifact or the review findings.

## Review Output Format

When reviewing an existing artifact, produce findings in this format:

```markdown
## Review: [filename]

### Verdict: [TRIM | RESTRUCTURE | RELOCATE | CLEAN]

### Findings
| Line(s) | Issue | Action |
|---------|-------|--------|
| 5-8 | Restates hook enforcement (write-gate.sh) | Delete |
| 12 | Procedural step with no gate | Move to command or delete |
| 20-25 | Cost reasoning (belongs here) | Keep |

### Token Impact
- Current: ~[N] tokens
- After changes: ~[N] tokens
- Reduction: [N]% 
```

## Authoring Output Format

When creating a new artifact, produce the complete file content following the structural template from the relevant reference doc. Include a brief rationale section at the end explaining which earned-prose test each major section passes.
