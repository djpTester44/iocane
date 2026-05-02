# LEARNED RULES

> Lessons promoted from `/lessons-retro-review`. Global section applies across any repo; workspace-scoped lessons live local-only under `.lessons/workspace-rules/`.

## Global (cross-workspace)

- When handing multi-item work off to follow-up sessions, write a per-session opening prompt that names the specific items in scope and lists pre-session decisions to confirm -- do not hand a fresh agent the full doc without framing context. _(2026-04-27)_
- When sequencing follow-up sessions across multi-item work, scope each session to a bounded set of items rather than combining items to reduce session count -- correctness and elegance win over fewer sessions. _(2026-04-27)_
- When using AskUserQuestion in plan mode for multi-part architectural questions, state the domain distinction and your current understanding in the question body up front so the operator can correct the framing in one round instead of three. _(2026-05-01)_
- When applying a stated in-place correction, do not ask the operator whether to bundle unrelated findings (e.g., open semantic findings from a prior evaluator step) into the same cycle -- execute only the stated correction scope and surface other findings separately. _(2026-05-01)_

## Workspace-Specific Index

Workspace-scoped lessons live in `.lessons/workspace-rules/{topic}-learned.md` (gitignored, local-only by design). Two developers in the same repo will have divergent workspace rule sets.

Active files:

<!-- File list maintained by promote.sh. -->
