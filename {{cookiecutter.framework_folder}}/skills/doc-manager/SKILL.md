---
name: doc-manager
description: Manage project documentation files (PLAN.md, README.md, DECISIONS.md, IMPROVEMENTS.md, project-spec.md, interfaces/*.pyi) with appropriate tool selection for appending, editing, or syncing docs. Use when updating project documentation with minimal diffs.
---

# Doc Manager

Manage project documentation with appropriate tool selection.

## Trigger Examples

- "Update PLAN.md with this decision"
- "Add this to progress.md"
- "Append a new section to README"
- "Edit project-spec.md"

## Managed Files

| File/Directory | Purpose |
|----------------|--------|
| `plans/PLAN.md` | Strategic requirements |
| `plans/project-spec.md` | Protocol overview and module map |
| `plans/tasks.json` | Current phase tasks |
| `plans/progress.md` | Completed work archive |
| `interfaces/*.pyi` | Protocol definitions (single source of truth) |
| `README.md` | Project documentation |

## Workflow

1. **Read** the target file to understand current structure
2. **Identify** the operation type:
   - Append/Add new content
   - Specific edit/modification
   - Multiple non-contiguous edits
   - New file/full regeneration
3. **Select** the appropriate tool based on operation:

| Operation | Tool |
|-----------|------|
| Append new content (log entries, decisions, sections) | `smart_append` script |
| Specific edit (checkbox toggle, typo fix, mark resolved) | `replace_file_content` |
| Multiple scattered edits | `multi_replace_file_content` |
| New file or complete restructure | `write_to_file` |

1. **Execute** with minimal diff (avoid full overwrites)
2. **Verify** the file remains clean Markdown

## Scripts

### smart_append.py

Appends content to a file, optionally under a targeted Markdown header:

```bash
python scripts/smart_append.py <file_path> "<content>" --target_header "## Section"
```

### update_catalog.py

Sweeps directory to generate a central CATALOG.md of all Skills, Workflows, and Rules:

```bash
python scripts/update_catalog.py
```

## Required Input

Caller MUST provide:

- `target_file`: Path to document to update
- `operation`: "append" | "edit" | "multi_edit" | "create"
- `content`: Content to add/modify (paste directly)

## Output Format

Return operation result:

```json
{
  "file": "path",
  "operation": "append",
  "success": true,
  "lines_changed": 5
}
```

## Constraints

- Do NOT overwrite entire files when a targeted append/edit suffices
- Do NOT use full regeneration except for new files or rare complete restructures
- Do NOT break existing Markdown structure