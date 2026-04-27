---
paths:
  - "plans/PRD.md"
  - "plans/roadmap.md"
  - "plans/component-contracts.yaml"
  - "plans/seams.yaml"
  - "plans/symbols.yaml"
  - "plans/test-plan.yaml"
  - "plans/plan.yaml"
  - "plans/backlog.yaml"
  - "tests/contracts/**"
  - "tests/connectivity/**"
---

# WORKFLOW AWARENESS

## Three-Tier Architecture

The three-tier model ensures no generated code reaches the codebase without human design approval. Cost of a tier violation: unreviewed architectural changes propagate through automated merges. Nothing in Tier 2 or 3 executes until the human approves Tier 1 artifacts.

---

## Artifact Registry

| Artifact | Location | Owner | Purpose |
|----------|----------|-------|---------|
| PRD | `plans/PRD.md` | Human | Requirements, user stories, stack decisions |
| Roadmap | `plans/roadmap.md` | Human (via /io-specify) | Feature sequence, dependency order |
| CRC Contracts | `plans/component-contracts.yaml` | Human (via /io-architect) | Component contracts: CRC behavioral data (responsibilities, must_not, features) with component-level `raises` declarations |
| Integration Seams | `plans/seams.yaml` | Human (via /io-architect) | DI graph, external terminals, key failure modes |
| Symbols Registry | `plans/symbols.yaml` | Human (via /io-architect Step F) | Cross-CP identifiers: Settings fields, exception classes, shared types, fixtures, error messages. `used_by_cps` is backfilled by /io-checkpoint. |
| Test Plan | `plans/test-plan.yaml` | Human (via /io-architect Step F) | Behavioral invariants per component contract; stamped `validated: true` by architect Step G |
| Checkpoint Plan | `plans/plan.yaml` | Human (via /io-checkpoint) | Atomic checkpoints, connectivity test signatures; stamped `validated: true` by /validate-plan Step 13 |
| Task Files | `plans/tasks/[CP-ID].yaml` | Orchestrator | Per-checkpoint sub-agent work packages |
| Dispatch Script | `plans/tasks/run.sh` | Orchestrator | Worktree setup and sub-agent invocation |
| Status Files | `plans/tasks/[CP-ID].status` | Sub-agent | PASS/FAIL per checkpoint |
| Backlog | `plans/backlog.yaml` | Review workflows | Bugs, issues, enhancements from /io-review and /gap-analysis. Each item has a `**BL-NNN**` identifier (auto-assigned by hook). |
| Schema Definitions | `.claude/scripts/schemas.py` | Harness | Pydantic models for all workflow YAML |
| Backlog Parser | `.claude/scripts/backlog_parser.py` | Harness | Load/save/query `plans/backlog.yaml` |
| Plan Parser | `.claude/scripts/plan_parser.py` | Harness | Load/save/query `plans/plan.yaml` |
| Task Parser | `.claude/scripts/task_parser.py` | Harness | Load/save/query `plans/tasks/CP-*.yaml` |
| Seam Parser | `.claude/scripts/seam_parser.py` | Harness | Load/save/query `plans/seams.yaml` |
| Symbols Parser | `.claude/scripts/symbols_parser.py` | Harness | Load/save/query `plans/symbols.yaml`; conflict detection (env_var + message_pattern) |
| Test Plan Parser | `.claude/scripts/test_plan_parser.py` | Harness | Load/save/query `plans/test-plan.yaml` |
| Contract Parser | `.claude/scripts/contract_parser.py` | Harness | Load/save/query `plans/component-contracts.yaml` |
| Workflow State | `.iocane/workflow-state.json` | Hook | Deterministic workflow state derived from artifact writes; consumed by `workflow-state-gate.sh` |
| Escalation Flag | `.iocane/escalation.flag` | Hook | Sentinel written by `escalation-gate.sh`; blocks dispatch and implementation writes |
| Review Pending | `.iocane/review-pending.json` | Command (`/io-review`) | Sentinel marking "reviewed but not approved"; consumed by `session-start.sh`, cleaned by `archive-approved.sh` |
| Escalation Log | `.iocane/escalation.log` | Hook | Sub-agent failure records |
| Subagent Start Log | `.iocane/subagent-start.log` | Hook | Sub-agent context snapshot at start |
| Subagent Stop Log | `.iocane/subagent-stop.log` | Hook | Sub-agent termination and result logging |
| Subagent Stop Payload | `.iocane/subagent-stop-payload.json` | Hook | Structured output from subagent-stop event |
| Tool Failure Log | `.iocane/tool-failure.log` | Hook | Failed tool invocation records |
| Compaction Log | `.iocane/compact.log` | Hook | Pre- and post-compaction state snapshots |
| Pre-Compaction State | `.iocane/pre-compact-state.json` | Hook | Workflow state snapshot before compaction (consumed by post-compact.sh) |
| Session End Log | `.iocane/session-end.log` | Hook | Session termination and cleanup records |
| CI Wave Report | `.iocane/ci/ci-wave-report.json` | Script (`ci-sidecar.sh`) | Pre/post-wave test suite snapshot for regression diffing |
| Capability Session State | `.iocane/sessions/<session_id>.{jsonl,active.txt}` + `.iocane/sessions/manifest.yaml` + `.iocane/sessions/.current-session-id` | Harness (`capability.py` sole writer, consumed by reset-on-*.sh via `capability-covers.sh`) | Per-session grant/revoke event log (jsonl audit), hot-path cache (active.txt; flat text, bash-grep), LRU-50 session manifest (yaml). See `references/capability-gate.md` for the primitive. |

---

## Capability-Gate State

Workflow-authored write authorization is modeled as time-bounded capability grants, not as boolean sentinel files. Reset and guard hooks consult the per-session cache at `.iocane/sessions/<session_id>.active.txt` and bypass their resets when a write pattern is covered. Primer: [`references/capability-gate.md`](../references/capability-gate.md). Grant templates: `.claude/capability-templates/<workflow>.<step>.yaml` (git-tracked, PR-reviewable catalog of what each step writes).

---
