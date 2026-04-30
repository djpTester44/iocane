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
| Implementation writes gated by workflow state (capability-grant bypass via β-delegation to `capability-covers.sh`) | `workflow-state-gate.sh` | PreToolUse Edit/Write | |
| Write targets scoped to checkpoint | `write-gate.sh` | PreToolUse Edit/Write | |
| No secrets in written files | `secret-scan.sh` | PreToolUse Edit/Write | |
| No backslash paths in written files | `backslash-path.sh` | PreToolUse Edit/Write | |
| No emoji in written files | `emoji-scan.sh` | PreToolUse Edit/Write | |
| Env vars filtered by phase (Phase A/B/C) | `environ-gate.sh` | PreToolUse Edit/Write | |
| Plan mode required when flag set | `environ-gate.sh` | PreToolUse Edit/Write | |
| .py file creation context injection | `py-create-context.sh` | PreToolUse Edit/Write | yes |
| Validation stamp reset on PRD write | `reset-on-prd-write.sh` | PostToolUse Edit/Write | |
| Validation stamp reset on project-spec write | `reset-on-project-spec-write.sh` | PostToolUse Edit/Write | |
| Validation stamp reset on plan.yaml write | `reset-on-plan-write.sh` | PostToolUse Edit/Write | |
| Validation stamp reset on symbols.yaml write (resets plan.yaml) | `reset-on-symbols-write.sh` | PostToolUse Edit/Write | |
| Within-session sentinel staleness guard (60-min TTL) | `scripts/check-validating-sentinel.sh` (DEPRECATED 2026-04-22; unregistered, no longer consulted by any active hook -- retained in-place for rollback reference) | -- | |
| Workflow write-authorization (capability grant + hot-path cache + catastrophic-rm deny) | `scripts/capability.py` (sole writer) + `hooks/capability-gate.sh` (PreToolUse Bash + Edit/Write, hardcoded catastrophic deny, fail-open baseline) + `scripts/capability-covers.sh` (helper invoked by reset-on-* hooks) | PreToolUse Bash, Edit/Write | |
| BL-NNN assignment on backlog write | `backlog-id-assign.sh` -> `assign_backlog_ids.py` | PostToolUse Edit/Write | |
| Backlog tag validation (blocking on schema failure) | `backlog-tag-validate.sh` -> `backlog_parser.load_backlog()` | PostToolUse Edit/Write | |
| YAML schema validation (task, plan, backlog, seams, component-contracts, symbols); routes `.iocane/wire-tests/eval_*.yaml` writes to `eval_parser.load_eval_report` for EvalReport schema validation | `validate-yaml.sh` | PostToolUse Edit/Write | |
| Archive sync on checkpoint approval | `archive-sync.sh` | PostToolUse Edit/Write | yes |
| Workflow state derivation from validation report | `task-validation-report-write.sh` | PostToolUse Edit/Write | |
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
| CRC budget caps (responsibilities, domain_concerns, features, composition-root fan-out) | `validate_crc_budget.py` | io-architect Step G [HARD GATE] |
| Symbols coverage (raises types declared as exception_class; `used_by` referential integrity; `used_by` reciprocity for `Settings.X` citations and structured `raises[]`) | `validate_symbols_coverage.py` | io-architect Step G [HARD GATE] |
| Symbol conflict detection (env_var + message_pattern) | `symbols_parser.detect_env_var_conflicts` / `detect_message_pattern_conflicts` | io-architect Step G [HARD GATE] |
| Trust-edge cross-artifact chain (PRD keyword presence + roadmap Trust Edges section + contract raises adversarial coverage + Settings parameterization) | `validate_trust_edge_chain.py` | io-architect Step G [HARD GATE] |
| Write-target collision detection | `check_write_target_overlap.py` (includes CT files owned by target_cp) | io-plan-batch Step C [HARD GATE] |
| CT seam completeness (covers source + target sides) | `check_ct_completeness.py` | validate-plan Step 9 [HARD GATE] |
| CT dependency invariant | `check_ct_depends_on.py` | validate-plan Step 9B [HARD GATE] |
| CT assertion behavior keywords (call binding, cardinality, error propagation) | `validate_ct_assertions.py` | validate-plan Step 9C [OBSERVATION] |
| File-reference resolvability | `validate_path_refs.py` | io-architect Step G + validate-plan Step 9D [OBSERVATION] |
| Plan-wide Raises coverage in CT assertions | `validate_plan_raises_coverage.py` | validate-plan Step 9E [OBSERVATION] |
| Batch architect-mode preflight (blocks dispatch while `/io-architect` mid-design) | `dispatch-agents.sh` (post-escalation-flag gate, pre-worktree) | pre-batch-dispatch |
| Batch confidence threshold (85%) | inline scoring rubric | io-plan-batch Step E [HARD GATE] |
| Batch human approval | user accept/modify/reject | io-plan-batch Step F [HUMAN GATE] |
| Ruff lint compliance | `run-compliance.sh` → `uv run rtk ruff check` | io-review Step D, gap-analysis Step C |
| Mypy type correctness | `run-compliance.sh` → `uv run mypy` | io-review Step D, gap-analysis Step C |
| Import-linter layer contracts | `run-compliance.sh` → `uv run rtk lint-imports` | io-review Step D, gap-analysis Step C |
| Bandit security scan (optional) | `run-compliance.sh` → `bandit -q -ll` (WARN if not installed) | io-review Step D, gap-analysis Step C |
| DI compliance (full run) | `run-compliance.sh` → `check_di_compliance.py` | io-review Step D, gap-analysis Step C |
| `ci-sidecar.sh post-wave` | Advisory | Post-dispatch regression diff -- appends `[CI-REGRESSION]` / `[CI-COLLECTION-ERROR]` findings to `plans/backlog.yaml` |
| CDT wire-test evaluation | `/io-wire-tests-cdt` | Capability-bracketed Author + Critic spawns; per-target Actor-Critic loop bounded by `wire_tests.max_turns`; resolved-suffix sweep on all-PASS gated by no-collision; post-batch collision detection emits FindingFile (defect_kind=`parallel_write_collision`) per affected target |
| CT wire-test precondition validation | `/io-wire-tests-ct` | Same as CDT, plus STRICT precondition: matching CDT eval YAMLs (src + dst) STATUS=PASS and not `.collision-tainted`; precondition-FAIL emits FindingFile (defect_kind=`ct_precondition_cdt_missing` / `ct_precondition_cdt_not_pass` / `ct_precondition_cdt_collision_tainted`) |

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
| CDD doctrine (contracts are behavioral; tests derived from clauses) | `cdd.md` |
| CDT vs Implementation TDD (contract tests in tests/contracts/) | `cdd.md` |
