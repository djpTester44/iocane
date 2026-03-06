---
description: Clarify the PRD before Init to ensure testable, autonomous execution.
---

# Clarify Workflow

**Trigger:** Executed prior to `io-init` or when a new `PRD.md` is provided.
**Purpose:** Prevent architectural hallucination and ensure the PRD contains strictly testable constraints required for the autonomous `io-loop`.

## Execution Rules

1. **Read the PRD:** Parse `plans/PRD.md`.
2. **Analyze Constraints:** Evaluate the PRD against the following strict criteria:
   - Are the success metrics quantifiable and capable of being expressed as strict `pytest` assertions?
   - Are external dependencies (APIs, databases) explicitly named with version targets?
   - Are performance constraints (latency, throughput) defined?
   - Are error-handling states for external integrations specified?
3. **Generate Interrogation:** If any criteria are missing, you must generate a markdown list of highly specific questions.
   - Do not ask open-ended questions (e.g., "How should errors be handled?").
   - Provide binary or categorical options (e.g., "For API timeout errors, should the system implement exponential backoff, or fail immediately and alert?").
4. **Halt Execution:** Do not proceed to architecture or planning. Present the questions to the user and wait for explicit answers. Ensure the `**Clarified:**` field in `plans/PRD.md` remains `False`.
5. **Update PRD:** Once the user answers all questions, update `plans/PRD.md` with the new constraints.
6. **Pass Gate:** When all ambiguities are resolved (or if none were found initially), update the `plans/PRD.md` doc header to set `**Clarified:** True` before exiting.

## Output Format

If ambiguities are found, output strictly in this format:

```markdown
### PRD Ambiguities Detected

The PRD cannot pass to the `io-init` phase until the following constraints are defined:

1. **[Missing Category]**: [Specific question with options]
2. **[Missing Category]**: [Specific question with options]
```

If no ambiguities are found, update the PRD header to `**Clarified:** True` and output:

```markdown
### PRD Clarification Complete

The PRD is strictly constrained and testable. `Clarified` field set to `True`. You may now proceed with `/io-init`.
```