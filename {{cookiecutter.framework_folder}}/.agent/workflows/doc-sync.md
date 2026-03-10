---
description: Reconcile documentation and design artifacts with current codebase state. No PLAN.md — syncs roadmap.md and project-spec.md.
---

> **[NO PLAN MODE]**
> Reconciliation workflow. Proposes changes to roadmap.md checkpoint statuses and project-spec.md.
> Changes to roadmap.md require human approval. project-spec.md structural updates are auto-applied.

> **[CRITICAL] CONTEXT LOADING**
> 1. Load the Architecture Template: `view_file .agent/templates/project-spec.md`
> 2. Load the Architecture Spec: `view_file plans/project-spec.md`
> 3. Load the Roadmap: `view_file plans/roadmap.md`

# WORKFLOW: DOC-SYNC

**Objective:** After a feature's checkpoints are complete and gap analysis has run, reconcile `plans/project-spec.md` and `plans/roadmap.md` with actual codebase state. Update README. Verify no documentation drift.

**Position in chain:**
```
/gap-analysis -> [/doc-sync]
```

---

## 1. STATE INITIALIZATION

Before proceeding, output:

- **Checkpoints complete in current batch:** [list with PASS status]
- **project-spec.md last updated:** [infer from content or git log]
- **roadmap.md feature statuses:** [list current status per feature]

---

## 2. PROCEDURE

### Step A: GATHER STATE

Read the following without loading full file contents into context where possible — use `extract_structure.py` for `.py` files:

* `tasks/[CP-ID].status` — for all checkpoints to confirm PASS
* `interfaces/*.pyi` — all current contracts
* `plans/project-spec.md` — current Interface Registry and CRC cards
* `plans/roadmap.md` — current feature list and acceptance criteria
* `plans/backlog.md` — open items (to avoid marking a feature complete if blockers exist)

---

### Step B: UPDATE README.MD

Sync the root README using `.agent/templates/README.md` as the master structure.

**Constraints:**
- Project description only — extract high-level summary from PRD
- Quick start: ensure `uv sync` and test commands are current
- Architecture summary: ensure link to `plans/project-spec.md` is visible
- No granular task lists, checkpoint statuses, or recent completions here

---

### Step C: RECONCILE PROJECT-SPEC.MD

Verify `plans/project-spec.md` reflects current codebase state:

* **Interface Registry:** Does every entry point to a file that actually exists? Remove entries for deleted files. Add entries for new Protocol implementations not yet registered.
* **CRC Cards:** Do responsibilities match what the implementation actually does? If implementation added behavior not in the CRC, flag as a MEDIUM finding (unanchored behavior — should go to backlog).
* **Mermaid dependency graph:** Does it reflect the actual import structure? Re-generate if components were added or removed.

**Rule:** `project-spec.md` reflects current codebase state only. Do not add future-state items, debt tracking, or state management artifacts.

Apply reconciliation updates directly — no human approval needed for factual corrections (e.g., wrong file path, missing registry entry). Propose-only for any change that modifies the meaning of a CRC responsibility.

When writing factual corrections to `plans/project-spec.md`, bracket all writes with the sentinel to prevent `reset-on-project-spec-write.sh` from resetting the Approved stamp mid-sync:

- **Step C-pre:** `bash: mkdir -p .iocane && touch .iocane/validating`
- **Step C:** [All Edit/Write operations for factual corrections — strictly sequential, never parallel]
- **Step C-post:** `bash: rm -f .iocane/validating`

---

### Step D: UPDATE ROADMAP.MD CHECKPOINT STATUSES

For each feature in `plans/roadmap.md`:

* Check: Are all checkpoints for this feature showing `PASS` in `tasks/[CP-ID].status`?
* Check: Are all acceptance criteria in `roadmap.md` for this feature verifiably satisfied?
* Check: Are there any open `[DESIGN]` or `[REFACTOR]` items in `plans/backlog.md` for this feature's components?

**Propose** status updates to `roadmap.md`:
- All checkpoints PASS + no blocking backlog items → propose marking feature `[COMPLETE]`
- Checkpoints PASS but blocking backlog items open → propose marking feature `[COMPLETE - PENDING REMEDIATION]`
- Checkpoints not all PASS → do not update status

**Rule:** Roadmap status updates require human approval before write.

Present proposed changes. Wait for approval.

---

### Step E: VERIFY FILE LINKS

* Scan all markdown docs for broken file links.
* Flag broken links as LOW findings.
* Auto-fix links where the target file exists at a different path (rename/move) — flag what was changed.

---

### Step F: OUTPUT

```
DOC-SYNC COMPLETE.

README.md: updated
project-spec.md: [N] reconciliation updates applied
roadmap.md: [N] status updates [pending approval / applied]
Broken links fixed: [N]

[If any CRC drift found:]
Unanchored behavior flagged: [N items] — run /review-capture to add to backlog.md
```

---

## 3. CONSTRAINTS

- Does not touch `plans/plan.md` — plan.md is owned by `/io-checkpoint`
- Does not touch `interfaces/*.pyi` — contracts are owned by `/io-architect`
- Does not touch `plans/backlog.md` directly — findings go via `/review-capture`
- `project-spec.md` changes that alter CRC meaning require human approval
- `roadmap.md` status updates require human approval
- No implementation code written in this workflow
