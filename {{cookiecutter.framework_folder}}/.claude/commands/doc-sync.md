---
name: doc-sync
description: Reconcile documentation and design artifacts with current codebase state. No plan.yaml -- syncs roadmap.md, project-spec.md, and seams.yaml.
---

> **[NO PLAN MODE]**
> Reconciliation workflow. Proposes changes to roadmap.md checkpoint statuses.
> Changes to roadmap.md require human approval.
> seams.yaml is updated in place from source code via seam_parser.

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load the component registry: `view_file plans/component-contracts.toml`
> 2. Load the Architecture Spec: `view_file plans/project-spec.md` (read-only — reference only for planned CRC/Protocol-backed components)
> 3. Load the Roadmap: `view_file plans/roadmap.md`
> 4. Load the Integration Seams reference (if exists) via `seam_parser.load_seams('plans/seams.yaml')`

# WORKFLOW: DOC-SYNC

**Objective:** After a feature's checkpoints are complete and gap analysis has run, reconcile `README.md`, `plans/roadmap.md`, and `plans/seams.yaml` with actual codebase state. Verify no documentation drift.

**Position in chain:**

```
/gap-analysis -> [/doc-sync]
```

---

## 1. STATE INITIALIZATION

Before proceeding, output:

- **Checkpoints complete in current batch:** [list with PASS status]
- **roadmap.md feature statuses:** [list current status per feature]

---

## 2. PROCEDURE

### Step A: GATHER STATE

Read the following without loading full file contents into context where possible — use `extract_structure.py` for `.py` files:

- `tasks/[CP-ID].status` — for all checkpoints to confirm PASS
- `interfaces/*.pyi` — all current contracts
- `plans/project-spec.md` — current Interface Registry and CRC cards (read-only reference only)
- `plans/roadmap.md` — current feature list and acceptance criteria
- `plans/backlog.yaml` — open items (to avoid marking a feature complete if blockers exist)

---

### Step B: UPDATE README.MD

Sync the root README using `.claude/templates/README.md` as the master structure.

**Constraints:**

- Project description only — extract high-level summary from PRD
- Quick start: ensure `uv sync` and test commands are current
- Architecture summary: ensure link to `plans/project-spec.md` is visible
- No granular task lists, checkpoint statuses, or recent completions here

---

### Step C: UPDATE ROADMAP.MD CHECKPOINT STATUSES

For each feature in `plans/roadmap.md`:

- Check: Are all checkpoints for this feature showing `PASS` in `tasks/[CP-ID].status`?
- Check: Are all acceptance criteria in `roadmap.md` for this feature verifiably satisfied?
- Check: Are there any open `[DESIGN]` or `[REFACTOR]` items in `plans/backlog.yaml` for this feature's components?

**Propose** status updates to `roadmap.md`:

- All checkpoints PASS + no blocking backlog items → propose marking feature `[COMPLETE]`
- Checkpoints PASS but blocking backlog items open → propose marking feature `[COMPLETE - PENDING REMEDIATION]`
- Checkpoints not all PASS → do not update status

**Rule:** Roadmap status updates require human approval before write.

Present proposed changes. Wait for approval.

---

### Step D: RECONCILE BACKLOG

For each `[ ]` item in `plans/backlog.yaml`:

- Read the named component's current implementation.
- Determine whether the fix described in the `Detail` field has been applied.
- If resolved: mark the item `[x]` in-place (checkbox state change only — do not alter any other text).
- If still open: leave `[ ]` and include the item in the Step G output as still-active.

**Rule:** Only checkbox state changes are permitted. Do not edit descriptions, severity, or source fields.

---

### Step E: RECONCILE SEAMS

Full-project reconciliation of `plans/seams.yaml` against actual source code using `seam_parser`. This catches drift that `/io-review` Step F missed (skipped reviews, brownfield onboarding, accumulated changes).

**If `plans/seams.yaml` does not exist:** Create it from `.claude/templates/seams.yaml`, then populate every implemented component that is also registered in the Interface Registry.

**Load seams:** `seam_parser.load_seams('plans/seams.yaml')`. Use `find_by_component()` for lookups.

**For every component in `plans/component-contracts.toml` (iterate `[components]` keys; use `file` field for the implementation path):**

1. Read the component's `__init__` signature from its implementation file in `src/`.
2. Use `find_by_component()` to locate the component's seam entry (or note the entry is missing).
3. Check each field for drift:
   - **receives_di:** Do `__init__` parameters match? Flag any added, removed, renamed, or re-typed.
   - **external_terminal:** Scan for direct client instantiation (`httpx.AsyncClient()`, `boto3.client()`, `create_async_engine()`, etc.) not reflected in the field.
   - **key_failure_modes:** Compare raised exception types against listed failure modes.
4. If the component has no implementation file yet (planned but unbuilt): skip it.

**Preservation rule:** Treat `plans/component-contracts.toml` as the authoritative component list. If a seam entry corresponds to a component still registered there, do **not** auto-remove that seam entry just because the implementation file does not exist yet. Cross-check `plans/project-spec.md` CRC cards when the TOML entry is ambiguous.

**Actions:**

- Use `seam_parser.update_component()` for drifted fields, `add_component()` for missing entries, `remove_component()` for orphaned entries. Call `save_seams()` after all mutations.
- Remove entries only when the component is absent from both the current implementation and `plans/project-spec.md` (true orphaned seam entries).
- Do **not** modify the `backlog_refs` field -- that is populated by `/io-backlog-triage` during drain.
- Do **not** auto-remove planned CRC/Protocol-backed components.
- Report a summary of changes in Step G output.

---

### Step F: VERIFY FILE LINKS

- Scan all markdown docs for broken file links.
- Flag broken links as LOW findings.
- Auto-fix links where the target file exists at a different path (rename/move) — flag what was changed.

---

### Step G: OUTPUT

```
DOC-SYNC COMPLETE.

README.md: updated
roadmap.md: [N] status updates [pending approval / applied]
seams.yaml: [N] entries updated, [N] entries created, [N] entries removed
backlog.yaml: [N] items closed [x], [N] still open
Broken links fixed: [N]
```

---

## 3. CONSTRAINTS

- Does not touch `plans/plan.yaml` — plan.yaml is owned by `/io-checkpoint`
- Does not touch `interfaces/*.pyi` — contracts are owned by `/io-architect`
- Does not edit `plans/project-spec.md` — it may be read as reference, but ownership remains outside `/doc-sync`
- Does not **add new findings** to `plans/backlog.yaml` — new findings go via `stage_review_findings.py`. Closing resolved items (`[ ]` → `[x]`) is permitted in Step D.
- `roadmap.md` status updates require human approval
- Do not auto-remove planned CRC/Protocol-backed components from `plans/seams.yaml`
- No implementation code written in this workflow
