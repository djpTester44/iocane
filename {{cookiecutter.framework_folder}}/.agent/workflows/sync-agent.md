# Sync GitHub Directory to Agent Directory

**Objective:** One-command sync from `.github/` to `.agent/` (additive only -- never deletes targets).

**Script:** `.agent/scripts/github_to_agent_sync.py`
**Reverse:** Use the `sync-agent` prompt (`.github/prompts/sync-agent.prompt.md`) for `.agent/` -> `.github/`.

---

## Procedure

### 1. Preview changes (dry run)

```bash
python .agent/scripts/github_to_agent_sync.py --dry-run
```

Review the output table. Confirm the listed files are expected.

### 2. Execute sync

```bash
python .agent/scripts/github_to_agent_sync.py
```

### 3. Review created files

For each file listed under **Created Files** in the script output:

- Open the file and verify frontmatter was converted correctly.
- For rules: confirm `trigger:`/`globs:` (not `applyTo:`), `> Inherits:` line removed.
- For workflows: confirm `description:` present, no `name:` field.
- For skills/scripts/templates/loose files: confirm content matches source.

Report any errors or unexpected results to the user.

---

## Exempt Files

The following files are **never overwritten** by this sync and must be maintained independently:

| File | Exclusion Mechanism |
|------|--------------------|
| `github_to_agent_sync.py` | `EXCLUDED_SCRIPTS` in both sync scripts |
| `agent_to_github_sync.py` | `EXCLUDED_SCRIPTS` in both sync scripts |
| `sync-agent.md` / `sync-agent.prompt.md` | `EXCLUDED_PROMPTS` in the sync script |

---

## Conversion Reference

The script handles all format conversions automatically. For details on what it does, see the docstrings and comments in `.agent/scripts/github_to_agent_sync.py`.

Key transformations:

- **Rules:** `applyTo:` -> `trigger:`/`globs:`, removes `> Inherits:` line, renames `*.instructions.md` -> `*.md`
- **Workflows:** Removes `name:` field, renames `*.prompt.md` -> `*.md`
- **Skills/Scripts/Templates/Loose files:** Copied as-is
