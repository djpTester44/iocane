---
name: end-sesh
description: End a session and write a handoff summary to LEFTOFF.md at the project root. Records the last work item, workflow run, files updated, and recommended next action.
---

> **[NO PLAN MODE]**
> Write LEFTOFF.md only. No other files are modified.

# COMMAND: /end-sesh

**Objective:** Produce a concise handoff document at `LEFTOFF.md` in the project root so the next session can resume without re-reading the full conversation.

---

## PROCEDURE

### Step 1: GATHER CONTEXT

Inspect the current session to determine:

1. **Last work item** — the most recent task, checkpoint, or user request that was actively being worked on. Check `plans/plan.yaml` for the current checkpoint and `plans/backlog.yaml` for any in-progress items.
2. **Workflow / command run** — the last `/io-*` command or named workflow that was invoked (e.g., `/io-execute CP-09`, `/io-review CP-08`).
3. **Files updated** — list every source file, test file, interface, or plan document that was written or modified during this session. Use the conversation history and any terminal output to compile this list. Be specific (file paths relative to repo root).
4. **Recommended next action** — based on the project state, plan status, and any pending backlog items, determine the single most logical next command or action the human should run when resuming.

---

### Step 2: WRITE LEFTOFF.md

Write the file `LEFTOFF.md` at the project root with the structure below. Replace all bracketed placeholders with real content. Do NOT include sections with no data — omit them cleanly.

```markdown
# LEFTOFF

> Generated: {ISO-8601 datetime}

## Last Work Item

{One or two sentences describing the task or request that was being worked on. Include the checkpoint ID or task name if applicable.}

## Last Workflow Run

{Command name and arguments, e.g. `/io-execute CP-09` or `/io-review CP-08R2`. If no formal workflow was run, describe the ad-hoc action taken.}

## Files Updated This Session

| File | Change summary |
|------|----------------|
| {relative/path/to/file.py} | {brief description of what changed} |

## What to Run Next

```{bash}
{exact command or sequence to execute on resume}
```

{One or two sentences explaining why this is the recommended next step.}

```

---

### Step 3: CONFIRM

After writing the file, output:

```

LEFTOFF.md written.
Resume point: {one-line summary of what to run next}

```

Do not output the full file contents — the confirmation line is sufficient.
