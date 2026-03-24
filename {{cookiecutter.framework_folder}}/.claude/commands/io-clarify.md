---
name: io-clarify
description: Clarify the PRD before Init to ensure testable, autonomous execution.
---

# Clarify Workflow

**Trigger:** Executed prior to `io-init` or when a new `PRD.md` is provided.
**Purpose:** Prevent architectural hallucination and ensure the PRD contains strictly testable constraints required for autonomous sub-agent execution.

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
6. **Critique PRD:** After all ambiguities are resolved, critique the full `plans/PRD.md` against the following rubric. Score each criterion and produce an overall PASS/FAIL:

   | Criterion | Description |
   |-----------|-------------|
   | Testability | All success metrics are expressible as concrete `pytest` assertions |
   | External dependency completeness | All APIs, databases, and services are named with version targets |
   | Performance constraints | Latency and throughput requirements are defined where relevant |
   | Error handling coverage | Failure states for all external integrations are specified |
   | Constraint specificity | No vague requirements (e.g. "fast", "reliable", "scalable") without measurable definition |

   Present findings in this format:

   ```markdown
   ### PRD Critique

   | Criterion | Result | Notes |
   |-----------|--------|-------|
   | Testability | PASS/FAIL | ... |
   | External dependency completeness | PASS/FAIL | ... |
   | Performance constraints | PASS/FAIL | ... |
   | Error handling coverage | PASS/FAIL | ... |
   | Constraint specificity | PASS/FAIL | ... |

   **Overall: PASS / FAIL**

   [If FAIL: list specific gaps with actionable questions to resolve them]
   ```

   If FAIL: present gaps to the user, wait for responses, update `plans/PRD.md`, and re-run the critique. Iterate until all criteria PASS.

7. **Pass Gate:** When the critique returns an overall PASS, write the `**Clarified:** True` stamp to `plans/PRD.md` using the following strictly sequential steps:
   - **Step 7-pre:** `bash: mkdir -p .iocane && touch .iocane/validating`
   - **Step 7:** Edit `plans/PRD.md` to set `**Clarified:** True` in the doc header.

   The sentinel prevents `reset-on-prd-write.sh` from immediately resetting the stamp. The hook auto-deletes the sentinel when it detects the `**Clarified:** True` stamp write — no explicit cleanup step required. Steps must NOT be parallelized — create sentinel first, then write.

## Output Format

If ambiguities are found, output strictly in this format:

```markdown
### PRD Ambiguities Detected

The PRD cannot pass to the `io-init` phase until the following constraints are defined:

1. **[Missing Category]**: [Specific question with options]
2. **[Missing Category]**: [Specific question with options]
```

If no ambiguities are found and the critique returns an overall PASS, update the PRD header to `**Clarified:** True` and output:

```markdown
### PRD Clarification Complete

The PRD is strictly constrained and testable. `Clarified` field set to `True`. You may now proceed with `/io-init`.
```
