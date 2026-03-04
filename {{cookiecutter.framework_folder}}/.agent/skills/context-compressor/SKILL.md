---
name: context-compressor
description: Summarizes chat context into permanent documentation by extracting architectural decisions, dependency changes, and known issues while filtering out noise. Use at the end of coding sessions to preserve important decisions and changes.
---

# Context Compressor

Summarize chat context into permanent documentation.

## Workflow

1. **Filter** - Ignore chitchat, syntax errors, and failed attempts
2. **Extract** - Focus on:
   - Architectural Decisions (e.g., "Chose Factory Pattern for DB connection")
   - Dependency Changes (e.g., "Added `pydantic` to requirements")
   - Known Issues (e.g., "Tech debt added to `user_model.py`")
3. **Format** - Output a structured log entry using the provided templates

## Templates

For session summaries, see [assets/decisions_entry_template.md](assets/decisions_entry_template.md).

For improvement tracking, see [assets/improvements_entry_template.md](assets/improvements_entry_template.md).

## Required Input

Caller MUST provide (do not fetch):

- `session_context`: Summary of work done this session (paste content directly)

## Output Format

Return ONLY structured log entry:

```json
{
  "decisions": ["<architectural decision>"],
  "dependencies": ["<added/removed package>"],
  "issues": ["<known issue or tech debt>"]
}
```

Do NOT include explanations unless explicitly requested.

## Constraints

- Do NOT include chitchat or casual conversation
- Do NOT document syntax errors
- Do NOT record failed attempts