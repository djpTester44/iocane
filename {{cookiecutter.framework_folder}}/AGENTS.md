## Session Lessons

### 2026-03-30

**Pattern:** `/io-checkpoint` generated write targets for runtime `.py` files in
`interfaces/` (a contract-only `.pyi` directory). The violation survived `/validate-plan`
(INFO-only exemption for non-`src/` files), `/io-execute` (no location awareness), and
`/io-review` (`src/`-scoped registry check only). Caught by manual inspection.
**Rule:** All runtime `.py` write targets must resolve to `src/` or `tests/`.
`interfaces/` is `.pyi`-only. When reviewing checkpoint write targets, verify `.py`
files are in architecturally valid directories, not just registered in
`component-contracts.toml`.

### 2026-03-16

**Pattern:** Agent used raw `ls`, `find`, and `cat` Bash commands throughout a session despite the global CLAUDE.md rule requiring `rtk ls`, `rtk find`, and the Read/Glob tools respectively. The user had to manually correct the agent mid-session.
**Rule:** Before issuing any `ls`, `find`, `cat`, `head`, `tail`, or `grep` Bash command, substitute: `ls` → `rtk ls`, `find` → Glob tool, `cat`/`head`/`tail` → Read tool, `grep` → Grep tool. The `rtk` prefix and dedicated tools are non-negotiable regardless of context or urgency.
**VIOLATION**: BAD: `uv run rtk python...` or `rtk uv run python`; GOOD: `uv run python...` Approved usage only mentioned above.
