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
  - "interfaces/**"
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
| CRC Contracts | `plans/component-contracts.yaml` | Human (via /io-architect) | CRC behavioral data (responsibilities, must_not, protocol, features) |
| Integration Seams | `plans/seams.yaml` | Human (via /io-architect) | DI graph, external terminals, key failure modes |
| Symbols Registry | `plans/symbols.yaml` | Human (via /io-architect Step H-6) | Cross-CP identifiers: Settings fields, exception classes, shared types, fixtures, error messages. `used_by_cps` is backfilled by /io-checkpoint. |
| Test Plan | `plans/test-plan.yaml` | Human (via /io-architect Step H-7) | Per-Protocol-method behavioral invariants; stamped `validated: true` by architect Step H-post-validate |
| Contracts | `interfaces/*.pyi` | Human (via /io-architect) | Binding Protocol definitions with mandatory Raises clauses |
| Contract Tests | `tests/contracts/test_<stem>.py` | Test Author (via io-test-author dispatched by `spawn-tester.sh`) | Pytest tests exercising test-plan invariants against one Protocol |
| Connectivity Tests | `tests/connectivity/*.py` | CT Author (via io-ct-author dispatched by `spawn-ct-writer.sh`) | Pytest tests exercising seam contracts (source Protocol spy-mocked); authored per CP before generator runs |
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
| Test Author Dispatch | `.claude/scripts/spawn-tester.sh` | Harness | Dispatches `claude -p` for one Protocol with `IOCANE_ROLE=tester` + `IOCANE_PROTOCOL=<stem>`; preflights architect-mode sentinel, validated stamps, target `.pyi` existence |
| CT Author Dispatch | `.claude/scripts/spawn-ct-writer.sh` | Harness (Phase 4) | Dispatches `claude -p` for one CP with `IOCANE_ROLE=ct_author` + `IOCANE_CP_ID=<CP-ID>`; preflights architect-mode sentinel, task-file validity, target_cp CT count. Invoked by `dispatch-agents.sh` before the generator stage. |
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

---
