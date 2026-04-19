# Enforcement Mapping

Maps every harness constraint to its enforcement mechanism.

---

## Trust Model (interfaces-zone guard family)

The hooks below under "interfaces-*.sh" gate AGENT DRIFT UNDER CONTEXT
PRESSURE, not deliberate adversarial bypass. Specifically:

- `IOCANE_ROLE` is a caller-controlled string. An agent that reads
  `interfaces-codegen-only.sh` can inline `IOCANE_ROLE=gen_protocols`
  on any Bash tool call to obtain admission. The SessionStart role-leak
  guard catches only the "inherited-from-shell" case (`export`,
  `.envrc`, copy-pasted debug), not deliberate inline prefix.
- The Bash/PowerShell write-verb pattern sets are blocklists, not
  allowlists, and are non-exhaustive by design. Unlisted primitives
  (`ln -s`, `install` before this pass, `python -c "pathlib.Path(...)"`,
  `git checkout -- interfaces/foo.pyi`, etc.) bypass by construction.
  Adding verbs raises the drift bar incrementally; it does not close
  the structural admission gap.

Accepted under v3's threat model. Cryptographic admission engineering
(per-invocation tokens, parent-process verification, capability
binding) is deferred as out-of-scope. The hooks are load-bearing for
honest-agent drift; Phase 2.5 validation is drift-validation, not
adversarial red-team.

**No whack-a-mole.** New verbs enter the Bash/PowerShell matcher ONLY
when a plausible honest-agent drift pattern uses them -- not from
theoretical adversarial enumeration. `/challenge` rounds will surface
theoretical bypasses indefinitely; resist adding coverage unless the
verb is part of standard agent toolkit AND a reasoning-from-task-
pressure agent would naturally reach for it. If the verb requires
deliberate gate-evasion thinking to use, it is a structural bypass
(Path A territory) -- accept and document it, do not extend the
matcher. This rule exists because an unchecked verb-addition cycle
is indistinguishable from piecemeal Path A engineering and would
invalidate the v3 deferral decision by slow creep.

**Known-accepted residuals (documented, not fixed):**

- *Template whitelist TOCTOU.* `_validate_template_path` resolves via
  `.resolve()` + `is_file()`; jinja2 reads the file on a separate
  trip. Low-likelihood under the honest-agent threat (the agent
  does not race itself); acceptable trade for code simplicity.
- *Windows 8.3 short names / case sensitivity beyond `.lower()`.*
  Edit|Write path hooks call `os.path.realpath`, catching 8.3
  resolution; the Bash matcher does not re-resolve the command
  string. Honest-drift agents do not produce 8.3 paths, so the
  Windows-specific gap stays open.

---

## Hook-Enforced (gate via exit code 2)

| Constraint | Hook | Event | Async |
|------------|------|-------|-------|
| No pip/pip3 invocations | `forbidden-tools.sh` | PreToolUse Bash | |
| No bare python/python3 invocations | `forbidden-tools.sh` | PreToolUse Bash | |
| No cd .. traversal in sub-agent context | `forbidden-tools.sh` | PreToolUse Bash | |
| RTK prefix required for CLI tools | `rtk-enforce.sh` | PreToolUse Bash | |
| No .py writes during /io-architect phase | `architect-boundary.sh` | PreToolUse Edit/Write | |
| Implementation writes gated by workflow state | `workflow-state-gate.sh` | PreToolUse Edit/Write | |
| Tier-1 Test Author bypass (scoped to `tests/contracts/`) | `workflow-state-gate.sh` (`IOCANE_ROLE=tester` branch) | PreToolUse Edit/Write | |
| Tier-3a CT Author bypass (scoped to `tests/connectivity/`) | `workflow-state-gate.sh` (`IOCANE_ROLE=ct_author` branch, Phase 4) | PreToolUse Edit/Write | |
| `.iocane/amend-signals/*.yaml` gate exemption (contract) | `workflow-state-gate.sh` (line 34 filter: gate scope is `src/` + `tests/` + `interfaces/*.py` only) | PreToolUse Edit/Write | |
| Write targets scoped to checkpoint | `write-gate.sh` | PreToolUse Edit/Write | |
| No secrets in written files | `secret-scan.sh` | PreToolUse Edit/Write | |
| No backslash paths in written files | `backslash-path.sh` | PreToolUse Edit/Write | |
| No emoji in written files | `emoji-scan.sh` | PreToolUse Edit/Write | |
| Design file required before .pyi contract | `design-before-contract.sh` | PreToolUse Edit/Write | |
| interfaces/ is type-only (.pyi extension required) | `interfaces-pyi-only.sh` -> `interfaces_zone_check.py is_violation_pyi_only` | PreToolUse Edit/Write | |
| interfaces/ writes require IOCANE_ROLE=gen_protocols | `interfaces-codegen-only.sh` -> `is_violation_codegen_only` | PreToolUse Edit/Write | |
| Bash commands writing into interfaces/ must honor extension + role | `interfaces-bash-write.sh` -> `is_violation_bash_write` | PreToolUse Bash | |
| PowerShell commands writing into interfaces/ must honor extension + role | `interfaces-powershell-write.sh` -> `is_violation_powershell_write` | PreToolUse PowerShell | |
| Session refuses if IOCANE_ROLE=gen_protocols is inherited at session start | `session-start.sh` (role-leak guard near top) | SessionStart | |
| Sub-agent warned if IOCANE_ROLE=gen_protocols is inherited at subagent start | `subagent-start.sh` (role-leak warning in additionalContext) | SubagentStart | |
| Env vars filtered by phase (Phase A/B/C) | `environ-gate.sh` | PreToolUse Edit/Write | |
| Plan mode required when flag set | `environ-gate.sh` | PreToolUse Edit/Write | |
| .py file creation context injection | `py-create-context.sh` | PreToolUse Edit/Write | yes |
| Validation stamp reset on PRD write | `reset-on-prd-write.sh` | PostToolUse Edit/Write | |
| Validation stamp reset on project-spec write | `reset-on-project-spec-write.sh` | PostToolUse Edit/Write | |
| Validation stamp reset on plan.yaml write | `reset-on-plan-write.sh` | PostToolUse Edit/Write | |
| Validation stamp reset on .pyi write (resets plan.yaml + test-plan.yaml) | `reset-on-pyi-write.sh` | PostToolUse Edit/Write | |
| Validation stamp reset on symbols.yaml write (resets plan.yaml + test-plan.yaml) | `reset-on-symbols-write.sh` | PostToolUse Edit/Write | |
| Validation stamp reset on test-plan.yaml write (resets plan.yaml) | `reset-on-test-plan-write.sh` | PostToolUse Edit/Write | |
| Within-session sentinel staleness guard (30-min TTL) | `scripts/check-validating-sentinel.sh` (called by bypass-aware hooks) | -- | |
| BL-NNN assignment on backlog write | `backlog-id-assign.sh` -> `assign_backlog_ids.py` | PostToolUse Edit/Write | |
| Backlog tag validation (blocking on schema failure) | `backlog-tag-validate.sh` -> `backlog_parser.load_backlog()` | PostToolUse Edit/Write | |
| YAML schema validation (task, plan, backlog, seams, component-contracts, symbols, test-plan) | `validate-yaml.sh` | PostToolUse Edit/Write | |
| Archive sync on checkpoint approval | `archive-sync.sh` | PostToolUse Edit/Write | yes |
| Workflow state derivation from validation report | `task-validation-report-write.sh` | PostToolUse Edit/Write | |
| Escalation capture on command failure | `escalation-gate.sh` | PostToolUse Bash | |
| Tool failure logging and corrective feedback | `tool-failure.sh` | PostToolUseFailure | |
| Block turn when escalation flag present | `stop-gate.sh` | Stop | |
| Per-turn dynamic state injection | `prompt-submit.sh` | UserPromptSubmit | |
| Sentinel cleanup on session exit | `session-end.sh` | SessionEnd | |
| Sub-agent harness context injection | `subagent-start.sh` | SubagentStart | |
| Role-scoped orientation (tester, ct_author) for `claude -p` dispatched sessions | `session-start.sh` (`IOCANE_ROLE` branch) | SessionStart | |
| Sub-agent exit logging and loop guard | `subagent-stop.sh` | SubagentStop | |
| Workflow state snapshot before compaction | `pre-compact.sh` | PreCompact | |
| Harness re-orientation after compaction | `post-compact.sh` | PostCompact | |
| No credential exfiltration via subprocess | `subprocess-credential-scope.md` (rule, no hook) | -- | |

---

## Gate-Enforced (compliance commands and workflow gates)

| Constraint | Command | When |
|------------|---------|------|
| CRC budget caps (responsibilities, features, composition-root fan-out) | `validate_crc_budget.py` | io-architect Step G-pre [HARD GATE] |
| Symbols coverage (every Protocol Raises type declared as exception_class) | `validate_symbols_coverage.py` | io-architect Step H-post-validate [HARD GATE] |
| Symbol conflict detection (env_var + message_pattern) | `symbols_parser.detect_env_var_conflicts` / `detect_message_pattern_conflicts` | io-architect Step H-post-validate + Step I-3 [HARD GATE] |
| Test-plan completeness (every Protocol method has TestPlanEntry) | `validate_test_plan_completeness.py` | io-architect Step H-post-validate [HARD GATE] |
| Write-target collision detection | `check_write_target_overlap.py` (includes CT files owned by target_cp) | io-plan-batch Step C [HARD GATE] |
| CT seam completeness (covers source + target sides) | `check_ct_completeness.py` | validate-plan Step 9 [HARD GATE] |
| CT dependency invariant | `check_ct_depends_on.py` | validate-plan Step 9B [HARD GATE] |
| CT assertion behavior keywords (call binding, cardinality, error propagation) | `validate_ct_assertions.py` | validate-plan Step 9C [OBSERVATION] |
| File-reference resolvability | `validate_path_refs.py` | io-architect Step I-3 + validate-plan Step 9D [OBSERVATION] |
| Plan-wide Raises coverage in CT assertions | `validate_plan_raises_coverage.py` | validate-plan Step 9E [OBSERVATION] |
| Protocol under-specification signal (AMEND) | `io-test-author.md` Step E, writes `.iocane/amend-signals/<stem>.yaml` per `AmendSignalFile` schema | io-test-author Step E [HARD GATE] |
| AMEND retry cap + DESIGN escalation | `handle_amend_signal.py --consume <stem>` (reads `architect.amend_retries`, default 2; zero/negative/non-int rejected with fallback) | io-architect Section 4 AMEND MODE Step 2 [HARD GATE]; exit 2 HALTs amend before any artifact write |
| Batch architect-mode preflight (blocks dispatch while `/io-architect` mid-design) | `dispatch-agents.sh` (post-escalation-flag gate, pre-worktree) | pre-batch-dispatch |
| Tester preflight (architect-mode sentinel, validated stamps, `interfaces/<stem>.pyi` exists) | `spawn-tester.sh` (defense-in-depth for standalone spawns) | pre-dispatch |
| CT Author preflight (architect-mode sentinel, task-file validity, target_cp CT count) | `spawn-ct-writer.sh` (Phase 4; defense-in-depth for standalone spawns) | pre-dispatch |
| CT-Writer stage per CP (before generator) | `dispatch-agents.sh` run_checkpoint_pipeline Phase 2A | per-CP, pre-generator |
| Post-ct_author identity-CT escape detection (AST import check) | `dispatch-agents.sh` Phase 2A, invoking `symbol_tracer.py --imports-from-prefix src` | per-CP, post-ct_author, pre-generator [HARD GATE] |
| Generator AMEND signal emission on impl-Protocol gap | `io-execute.md` Section 3 AMEND-on-impl-gap path, writes `${IOCANE_REPO_ROOT:-.}/.iocane/amend-signals/<cp-id>.yaml` per `AmendSignalFile` schema (parent-scoped; generator CWD = worktree, so `IOCANE_REPO_ROOT` is required for the architect to read the signal) | io-execute Step B/C/D/E (any point impl cannot proceed) [HARD GATE] |
| Batch confidence threshold (85%) | inline scoring rubric | io-plan-batch Step E [HARD GATE] |
| Batch human approval | user accept/modify/reject | io-plan-batch Step F [HUMAN GATE] |
| Ruff lint compliance | `run-compliance.sh` → `uv run rtk ruff check` | io-review Step D, gap-analysis Step C |
| Mypy type correctness | `run-compliance.sh` → `uv run mypy` | io-review Step D, gap-analysis Step C |
| Import-linter layer contracts | `run-compliance.sh` → `uv run rtk lint-imports` | io-review Step D, gap-analysis Step C |
| Bandit security scan (optional) | `run-compliance.sh` → `bandit -q -ll` (WARN if not installed) | io-review Step D, gap-analysis Step C |
| DI compliance (full run) | `run-compliance.sh` → `check_di_compliance.py` | io-review Step D, gap-analysis Step C |
| `ci-sidecar.sh post-wave` | Advisory | Post-dispatch regression diff -- appends `[CI-REGRESSION]` / `[CI-COLLECTION-ERROR]` findings to `plans/backlog.yaml` |

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
| CDD doctrine (contracts are behavioral; tests derived from clauses) | `cdd.md` + `references/cdd/principles.md` |
| CDT vs Implementation TDD (contract tests in tests/contracts/) | `cdd.md` + `references/cdd/cdt-vs-impl-testing.md` |
