---
name: context-sync
description: Synchronizes documentation (Tasks, Plans, PRDs) with the actual codebase state to ensure tracking documents accurately reflect the code that exists. Use when documentation may be out of sync with implementation, or to verify task completion status.
---

# Context Sync

Synchronize documentation with codebase reality.

## Trigger Examples

- "Sync docs with code"
- "Check if tasks are actually complete"
- "Update documentation to match reality"
- "Verify task completion status"

## Workflow

1. **Context Acquisition**
   - Read all files listed in `target_files`
   - Parse documents for task lists (`- [ ]`), feature announcements, and architecture definitions

2. **Reality Check (The Scan)**
   - For each claim found, verify it exists in the codebase
   - Use search/navigation tools to confirm existence of referenced code artifacts
   - Verify implementations match Protocols in `interfaces/*.pyi` (single source of truth)

3. **Synchronization (The Fix)**
   - Update documents to match reality:
     - Mark tasks `[x]` if code exists but docs show incomplete
     - Mark tasks `[ ]` (or add note) if docs say done but code is missing
   - Add file links to make documentation more precise
   - Ensure `tasks.json` components have correct `interface_file` paths

## Constraints

- **Conservative**: Only mark items if 90%+ certain; otherwise leave a comment requesting verification
- **No Hallucinations**: Never mark things as done unless the code is visually confirmed
- **Atomic Updates**: Use precise, targeted edits (not wholesale rewrites)

## Required Input

Caller MUST provide:

- `target_files`: List of doc files to sync (paths only - skill will read)

## Output Format

Return sync report:

```json
{
  "synced": [{"file": "path", "changes": ["marked X complete"]}],
  "unverified": [{"file": "path", "item": "description", "reason": "code not found"}]
}
```

## Tool Strategy

- `grep_search`: Verify code artifacts exist (class names, function names)
- `file_search`: Locate files referenced in docs
- `read_file`: Only when grep confirms existence and line context needed
- Do NOT read entire files to check if something exists