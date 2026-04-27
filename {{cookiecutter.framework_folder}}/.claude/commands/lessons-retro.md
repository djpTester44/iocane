---
name: lessons-retro
description: Manually run the /lessons-retro extraction pipeline against the current session.
---

Trigger the two-pass lesson-extraction pipeline (Sonnet -> Opus xhigh) against THIS session's transcript without waiting for `/clear`.

## Step 1 -- Resolve current transcript path

`.iocane/session-start-payload.json` is NOT a reliable source: any `claude -p` subprocess in this repo can overwrite it with its own session metadata, so the file may point at a sub-agent SID instead of yours. Resolve via filesystem instead.

Use the Bash tool to:

1. `pwd` -- get current working directory.
2. `ls -1 ~/.claude/projects/` -- list project directories. Each is a Claude Code project store, named by Claude Code's munging convention (path separators and drive letters replaced with `-`, e.g. `C--Users-danny-projects-agent-frameworks-iocane-build`).
3. Identify the directory matching the current cwd. Use judgment -- if cwd basename is `iocane_build`, look for a directory containing `iocane-build`. If multiple plausible matches exist, list each with the most recently modified `*.jsonl` inside, and pick the directory whose latest JSONL has been modified most recently (that's the active session).
4. Within the matched directory: `ls -t <dir>/*.jsonl | head -1` -- the JSONL with the most recent modification time IS the current session's transcript.
5. Strip the `.jsonl` extension from the basename to get `session_id`.

If no plausible directory matches, halt and ask the user to paste the transcript path directly.

## Step 2 -- Confirm and invoke

Report the resolved `session_id` and `transcript_path` to the user in one short line, then immediately invoke:

```
bash .claude/hooks/retro/invoke-retro.sh --manual <session_id> <transcript_path>
```

The pipeline runs synchronously (~1-3 minutes).

## Step 3 -- Report

When the script returns:
- Read `.lessons/debug/pipeline.log` (last ~20 lines).
- If both passes logged successful completion (`pipeline complete proposal=...`), report the proposal path to the user and tell them to run `/lessons-retro-review` when ready.
- If either pass logged `produced no output -- abort`, surface the failure with the relevant log tail. Do NOT retry automatically.

## Caveats

- The current session's JSONL is being actively written. The transcript may not include the last 1-2 exchanges at the moment Pass 1 reads it. Acceptable tradeoff for ad-hoc capture.
- Manual invocation bypasses the cooldown gate but still updates `.lessons/.cooldown` -- a subsequent `/clear` within the cooldown window will be skipped (logged to `.lessons/.skip-log`).
- Resolution heuristic assumes you are running this slash command IN the session you want to extract from. If you have multiple concurrent sessions in the same repo, the most-recently-modified JSONL may not be yours; verify the resolved path before proceeding.
