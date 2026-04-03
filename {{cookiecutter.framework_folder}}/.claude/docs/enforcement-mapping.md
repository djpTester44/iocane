# Enforcement Mapping

Maps every harness constraint to its enforcement mechanism.

---

## Hook-Enforced (gate via exit code 2)

| Constraint | Hook | Event | Async |
|------------|------|-------|-------|
| No pip/pip3 invocations | `forbidden-tools.sh` | PreToolUse Bash | |
| No bare python/python3 invocations | `forbidden-tools.sh` | PreToolUse Bash | |
| No cd .. traversal in sub-agent context | `forbidden-tools.sh` | PreToolUse Bash | |
| RTK prefix required for CLI tools | `rtk-enforce.sh` | PreToolUse Bash | |
| No .py writes during /io-architect phase | `architect-boundary.sh` | PreToolUse Edit/Write | |
| Write targets scoped to checkpoint | `write-gate.sh` | PreToolUse Edit/Write | |
| No secrets in written files | `secret-scan.sh` | PreToolUse Edit/Write | |
| No backslash paths in written files | `backslash-path.sh` | PreToolUse Edit/Write | |
| No emoji in written files | `emoji-scan.sh` | PreToolUse Edit/Write | |
| Design file required before .pyi contract | `design-before-contract.sh` | PreToolUse Edit/Write | |
| Env vars filtered by phase (Phase A/B/C) | `environ-gate.sh` | PreToolUse Edit/Write | |
| Plan mode required when flag set | `environ-gate.sh` | PreToolUse Edit/Write | |
| .py file creation context injection | `py-create-context.sh` | PreToolUse Edit/Write | yes |
| Validation stamp reset on PRD write | `reset-on-prd-write.sh` | PostToolUse Edit/Write | |
| Validation stamp reset on project-spec write | `reset-on-project-spec-write.sh` | PostToolUse Edit/Write | |
| Validation stamp reset on plan.md write | `reset-on-plan-write.sh` | PostToolUse Edit/Write | |
| Validation stamp reset on .pyi write | `reset-on-pyi-write.sh` | PostToolUse Edit/Write | |
| BL-NNN assignment on backlog write | `backlog-id-assign.sh` | PostToolUse Edit/Write | |
| Backlog tag validation | `backlog-tag-validate.sh` | PostToolUse Edit/Write | yes |
| Archive sync on checkpoint approval | `archive-sync.sh` | PostToolUse Edit/Write | yes |
| Escalation capture on command failure | `escalation-gate.sh` | PostToolUse Bash | |
| Tool failure logging and corrective feedback | `tool-failure.sh` | PostToolUseFailure | |
| Block turn when escalation flag present | `stop-gate.sh` | Stop | |
| Per-turn dynamic state injection | `prompt-submit.sh` | UserPromptSubmit | |
| Sentinel cleanup on session exit | `session-end.sh` | SessionEnd | |
| Sub-agent harness context injection | `subagent-start.sh` | SubagentStart | |
| Sub-agent exit logging and loop guard | `subagent-stop.sh` | SubagentStop | |
| Workflow state snapshot before compaction | `pre-compact.sh` | PreCompact | |
| Harness re-orientation after compaction | `post-compact.sh` | PostCompact | |
| No credential exfiltration via subprocess | `subprocess-credential-scope.md` (rule, no hook) | -- | |

---

## Gate-Enforced (compliance commands and workflow gates)

| Constraint | Command | When |
|------------|---------|------|
| Write-target collision detection | `check_write_target_overlap.py` | io-plan-batch Step C [HARD GATE] |
| Batch confidence threshold (85%) | inline scoring rubric | io-plan-batch Step E [HARD GATE] |
| Batch human approval | user accept/modify/reject | io-plan-batch Step F [HUMAN GATE] |
| Ruff lint compliance | `run-compliance.sh` → `uv run rtk ruff check` | io-review Step D, gap-analysis Step C |
| Mypy type correctness | `run-compliance.sh` → `uv run mypy` | io-review Step D, gap-analysis Step C |
| Import-linter layer contracts | `run-compliance.sh` → `uv run rtk lint-imports` | io-review Step D, gap-analysis Step C |
| Bandit security scan | `run-compliance.sh` → `bandit -q -ll` | io-review Step D, gap-analysis Step C |
| DI compliance (full run) | `run-compliance.sh` → `check_di_compliance.py` | io-review Step D, gap-analysis Step C |

---

## Rule-Enforced (agent reasoning, no mechanical enforcement)

| Constraint | Rule |
|------------|------|
| Read surgically — no full-file dumps | `navigation.md` |
| Never exceed prompt scope | `scope-discipline.md` |
| No hardcoded secrets | `scope-discipline.md` |
| Agent Tool for sub-agents, not inline | `scope-discipline.md` |
| Sub-agent context hygiene | task template preamble |
| TDD: no implementation without a test | task template preamble |
| Async I/O in async contexts | `python-standards.md` |
| Raise specific exceptions | `python-standards.md` |
| Test assertions must be truthful | `python-standards.md` |
| Frozen dataclasses by default | `python-standards.md` |
| Pydantic at system boundaries | `python-standards.md` |
| Sub-agent context window management | `claude-code-auto-compact-window.md` |
| Credential scope in subprocess context | `subprocess-credential-scope.md` |
| Tier violation cost model | `workflow-awareness.md` |
| Backlog tag semantics | `ticket-taxonomy.md` |
| AST limitation awareness for DI | `architecture-gates.md` |
| # noqa: DI usage judgment | `architecture-gates.md` |
