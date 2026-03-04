---
description: Synchronize documentation, design anchors, and contracts with codebase state.
---

**Objective:** Update documentation to reflect current codebase state, ensuring the Macro/Meso/Micro Hierarchy (Design > Contracts > Code) is synchronized against strict templates.

**When to Use:** After completing a Iocane Loop phase, adding new Protocols, or making significant architectural changes.

---

> **[CRITICAL] CONTEXT LOADING**
> 1. Load the Architecture Template: `view_file .agent/templates/project-spec.md`

## Procedure

### 1. GATHER CONTEXT
Read the following to understand current state and enforce structure:
- `plans/progress.md` - Recent completions
- `plans/tasks.json` - Current task status
- `interfaces/*.pyi` - All Protocol definitions
- `plans/project-spec.md` - Current Design Anchors
- `.agent/templates/README.md` - Structure Template (Identity only, no status)
- `.agent/templates/project-spec.md` - Structure Template (CRC Layout)

> **[TIP] Token Efficiency:**
> Use `uv run python .agent/scripts/extract_structure.py <file>` to scan `.py` files for Registry mapping instead of reading full source code.

### 2. UPDATE README.md
Sync the root README using `.agent/templates/README.md` as the master structure.
**CONSTRAINT:** Do NOT include granular task lists, checkpoints, or recent "done" items here.
- **Project description** - Extract high-level summary from PRD.
- **Quick start** - Ensure installation (uv sync) and test commands are current.
- **Architecture summary** - Ensure the link to `plans/project-spec.md` is visible.
- **Current Version** - Update version string only (e.g., v0.1.0) if applicable.

### 3. UPDATE project-spec.md (The Anchor Check)
Sync Protocol references using the table format defined in `.agent/templates/project-spec.md`:
- **Registry Check:** Ensure every `.pyi` file is listed in the Interface Registry table.
- **Design Check:** Ensure every Component in the Registry has a corresponding **CRC Card** in the "Component Specifications" section.
- **CRC Hygiene:** Scan each CRC card's Key Responsibilities for `_`-prefixed methods. If found, remove them -- private methods are implementation details excluded from the Design layer.
- **Action:** If a CRC is missing, flag it as "Unanchored Component" and suggest running `/io-architect` to fix it.

**Automated Anchor Verification:**
```bash
# Verify behavioral anchors (CRC cards) match structural contracts (Protocols)
uv run python .agent/scripts/check_design_anchors.py
```

### 4. UPDATE PLAN.md
**Backlog Reconciliation (auto, no approval needed):**
- **[HARD] Full Scan:** Identify ALL `[ ]` items across ALL historical review blocks in `plans/PLAN.md` -- not just the most recent one. Cross-reference every individual pending item against the extracted implementation structural data to detect silently completed work.
- Read `plans/PLAN.md Remediation Backlog` for any `[ ]` items.
- For each pending item, verify whether the fix is now present in the codebase (use `extract_structure.py` or targeted `view_code_item` — do not read full files).
- If the fix is confirmed: mark the item `[x]` in-place. Do **not** move or delete it — the backlog is its own audit record.
- If all items in a `#### From <CP> /review` group are `[x]`, the group is considered resolved. Leave it in place (history).

**Checkpoint & Roadmap updates (user approval required):**
- Marking checkpoints/tasks as complete
- Adding new items to roadmap sections
- Updating revision history

**Present diff to user before applying any checkpoint/roadmap changes.**


### 5. VERIFY LINKS
Run a quick check that all file links in markdown docs are valid using the mandatory search tool:

```bash
# Manual check: list linked files using smart_search pattern
.agent/scripts/smart_search.sh "file:///" plans/
.agent/scripts/smart_search.sh "file:///" README.md
```

---

## Document Permissions

| Document | Permission | Notes |
|----------|------------|-------|
| `README.md` | Auto-update | Identity Only (Follow Template) |
| `plans/project-spec.md` | Auto-update | Protocol registry & CRC Cards (Follow Template) |
| `plans/PLAN.md` | **User approval** | Strategic doc |
| `plans/PRD.md` | **User approval** | Requirements doc |

---

## Output
After completing doc-sync, report:
1. Files updated.
2. **Gap Report:** List of "Unanchored Components" (Missing CRC) or "Orphan Contracts" (Missing Registry Entry).
3. Changes made (brief summary).
4. Any items requiring user approval.