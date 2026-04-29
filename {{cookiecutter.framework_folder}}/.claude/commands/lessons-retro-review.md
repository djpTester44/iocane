---
name: lessons-retro-review
description: Review and apply lessons from the most recent /lessons-retro proposal.
---

Review the most recent `/lessons-retro` proposal and apply approved items to their destinations. The user marks decisions in the proposal file BEFORE running this; you read those decisions and apply them.

## Step 1 -- Find the latest proposal AND surface any prior deferred items

Use Bash: `ls -t .lessons/retro-review/*.md 2>/dev/null | head -1` (excluding `archive/`).

If no proposal exists, halt and tell the user "No proposal found in .lessons/retro-review/. Run /lessons-retro first."

If `.lessons/deferred.yaml` exists, read it and surface a heads-up to the user BEFORE proceeding to parse the new proposal. Show one bullet per deferred entry:

```
Deferred items pending (N entries):
  - <id> -- <name truncated to ~80 chars>
    proposal: <path>
  - <id> -- <name>
    proposal: <path>

(Open the referenced archived proposals to act on these. Edit .lessons/deferred.yaml to prune.)
```

If `.lessons/deferred.yaml` does not exist or has no entries, skip this surfacing.

## Step 2 -- Parse and classify

Use the Read tool on the proposal. For each `## Item N` section, extract:

- **Lesson:** the text after `**Lesson:**`
- **Tier:** `GLOBAL` or `WORKSPACE`
- **Destination:** the path after `**Destination:**`
- **Decision:** find which of the three checkboxes in `**Decision:** [ ] PROMOTE  [ ] DEFER  [ ] DISCARD` is marked `[X]` (case-insensitive).

Classify each item into one of four buckets:
- **PROMOTE** -- exactly `[X] PROMOTE  [ ] DEFER  [ ] DISCARD`
- **DEFER** -- exactly `[ ] PROMOTE  [X] DEFER  [ ] DISCARD`
- **DISCARD** -- exactly `[ ] PROMOTE  [ ] DEFER  [X] DISCARD`
- **UNMARKED** -- no `[X]` in any of the three boxes (treated as DISCARD by default; user is flagged in the summary)

Hard error: if an item has **more than one** `[X]` (e.g., `[X] PROMOTE [X] DEFER`), halt before showing the summary. Tell the user: "Item N has ambiguous decision (multiple marks). Edit the proposal and re-run."

Ignore the legend block at the top of the proposal (the example `[X] PROMOTE -- ...` lines). Only count `**Decision:**` lines as actual decisions.

## Step 3 -- Show summary, ask for confirmation

Print:

```
<proposal_path>: N items

  PROMOTE (P):
    - Item 1: <one-line lesson summary> [GLOBAL -> learned-rules.md]
    - Item 4: <one-line lesson summary> [WORKSPACE -> lessons-retro-learned.md]
  DEFER (D):
    - Item 2: <one-line lesson summary>
    - Item 3: <one-line lesson summary>
  DISCARD (X):
    - Item 5: <one-line lesson summary>
  UNMARKED (U) -- will be treated as DISCARD by default:
    - Item 6: <one-line lesson summary>
```

(Omit empty buckets.)

Ask: "Apply all decisions as shown? [y/N]"

If the user replies anything other than `y` (case-insensitive), halt cleanly. Proposal stays in place; no changes. User edits and re-runs.

## Step 4 -- Apply PROMOTE items

Today's date in `YYYY-MM-DD` format: get via Bash `date +%Y-%m-%d`.

For each PROMOTE item, in proposal order:

### GLOBAL items

Use the Edit tool on `.claude/rules/learned-rules.md`. Locate the `## Global (cross-workspace)` section. If the section currently contains only `<!-- Global lessons appended here by promote.sh on /lessons-retro-review approval. -->`, replace that comment with the first bullet. Otherwise append a new bullet at the end of the section (before the next `##` heading).

Bullet format:
```
- <Lesson text> _(YYYY-MM-DD)_
```

### WORKSPACE items

Derive the topic from the destination filename: `lessons-retro-learned.md` -> topic `lessons-retro`. The destination path is what Pass 2 specified.

If the file does NOT exist, use the Write tool to create it with this template:
```
# Workspace Rules: <Topic-Title>

Local-only learnings for this workspace, scoped to `<topic>`.

- <Lesson text> _(YYYY-MM-DD)_
```

Then update `.claude/rules/learned-rules.md` -- the `## Workspace-Specific Index` section's `Active files:` list. Add a new bullet:
```
- `.lessons/workspace-rules/<topic>-learned.md`
```

If the file already exists, use the Edit tool to append a new bullet at the end. Do NOT touch the index for files that already exist.

## Step 5 -- Handle scan failures

If any Edit/Write call returns an error from `secret-scan.sh` or `emoji-scan.sh` (PreToolUse Edit hook), STOP immediately. Do NOT continue applying remaining items. Do NOT finalize. Do NOT register deferred items.

Surface the failure to the user:
```
Scan blocked promotion of Item N: <one-line lesson summary>
Reason: <hook error message>
Edit the proposal (or the rule file directly) to remove the offending content, then re-run /lessons-retro-review.
```

The proposal stays in place. Items already promoted before the block stay promoted (each Edit is atomic).

## Step 6 -- Finalize (always, after a confirmed apply)

If Step 3 was confirmed and Step 5 did not fire, finalize via:

```
bash .claude/hooks/retro/promote.sh finalize <proposal_path>
```

This archives the proposal to `.lessons/retro-review/archive/`, deletes `.lessons/.pending-review`, and removes the matching Pass 1 JSONL from `.lessons/tmp/`. Always runs, regardless of P/D/X/U counts.

Capture the archived path from the script's output (or compute as `.lessons/retro-review/archive/<basename>`) -- you'll need it for Step 7.

## Step 7 -- Register DEFERred items

For each DEFER item, derive:
- **id**: `<stamp>#item-<N>` where `<stamp>` is the proposal's timestamp prefix (e.g., `20260427-0549`) and `<N>` is the item number from the proposal.
- **name**: first sentence of the Lesson text, truncated to ~120 chars (drop trailing punctuation if mid-sentence).

Then call:
```
bash .claude/hooks/retro/promote.sh defer <archived_proposal_path> <id> "<name>"
```

The script appends an entry to `.lessons/deferred.yaml` (creating the file with header if missing).

DISCARD and UNMARKED items get no follow-up -- they're dropped on archive.

## Step 8 -- Report

```
Applied P items (G GLOBAL / W WORKSPACE).
Deferred D items (registered in .lessons/deferred.yaml).
Discarded X items.
[Unmarked U items treated as discarded.]   <-- only if U > 0
Proposal archived: .lessons/retro-review/archive/<filename>
Pending-review flag cleared.
```
