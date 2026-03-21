## Session Lessons

### 2026-03-16

**Pattern:** Agent used raw `ls`, `find`, and `cat` Bash commands throughout a session despite the global CLAUDE.md rule requiring `rtk ls`, `rtk find`, and the Read/Glob tools respectively. The user had to manually correct the agent mid-session.
**Rule:** Before issuing any `ls`, `find`, `cat`, `head`, `tail`, or `grep` Bash command, substitute: `ls` → `rtk ls`, `find` → Glob tool, `cat`/`head`/`tail` → Read tool, `grep` → Grep tool. The `rtk` prefix and dedicated tools are non-negotiable regardless of context or urgency.
