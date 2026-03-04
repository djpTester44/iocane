---
description: Collaboratively expand project scope with structured additions to PLAN.md.
---

# WORKFLOW: BRAINSTORM (Scope Expansion)

**Objective:** Collaboratively expand project scope with structured additions to `plans/PLAN.md`.

**Context:**
* Scope: Strategic planning - requirements, milestones, scope changes
* Output: Approved changes to `plans/PLAN.md`.

**Procedure:**
1. **GATHER INPUT:** Collect proposed scope change. Ask: What capability is being added? Priority level (Must/Should/Could)? New milestone or addition to existing? Constraints/dependencies?
2. **ASSESS IMPACT:** Analyze conflicts with existing requirements, effects on milestones, and architectural implications for `plans/project-spec.md`.
3. **DRAFT ADDITIONS:** Prepare changes to `plans/PLAN.md` sections - Requirements Table (FR-XXX/NFR-XXX with priority), Scope Changes (in/out items), Milestones (new or additions), Open Questions.
4. **PRESENT FOR APPROVAL:** Display proposed changes clearly with "Approve these changes? (yes/no/modify)" prompt.
5. **APPLY CHANGES:** Only after explicit approval - update `plans/PLAN.md`, add entry to Revision History.
6. **NEXT STEPS:** Instruct user to run `/io-init` (if fresh) or `/io-architect` to design the new capability.

**Rules:**
* No automatic implementation - only updates strategic docs.
* No task creation - use `/io-tasking` only after Design and Contract are anchored.
* No unilateral edits - `PLAN.md` changes require explicit approval.