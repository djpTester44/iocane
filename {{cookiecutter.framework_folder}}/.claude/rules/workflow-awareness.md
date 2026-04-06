---
paths:
  - "plans/PRD.md"
  - "plans/roadmap.md"
  - "plans/project-spec.md"
  - "plans/plan.yaml"
  - "plans/backlog.yaml"
  - "interfaces/**"
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
| Architecture Spec | `plans/project-spec.md` | Human (via /io-architect) | CRC cards, Interface Registry -- current codebase state only |
| Contracts | `interfaces/*.pyi` | Human (via /io-architect) | Binding Protocol definitions |
| Checkpoint Plan | `plans/plan.yaml` | Human (via /io-checkpoint) | Atomic checkpoints, connectivity test signatures |
| Task Files | `plans/tasks/[CP-ID].yaml` | Orchestrator | Per-checkpoint sub-agent work packages |
| Dispatch Script | `plans/tasks/run.sh` | Orchestrator | Worktree setup and sub-agent invocation |
| Status Files | `plans/tasks/[CP-ID].status` | Sub-agent | PASS/FAIL per checkpoint |
| Backlog | `plans/backlog.yaml` | Review workflows | Bugs, issues, enhancements from /io-review and /gap-analysis. Each item has a `**BL-NNN**` identifier (auto-assigned by hook). |
| Schema Definitions | `.claude/scripts/schemas.py` | Harness | Pydantic models for all workflow YAML |
| Backlog Parser | `.claude/scripts/backlog_parser.py` | Harness | Load/save/query `plans/backlog.yaml` |
| Plan Parser | `.claude/scripts/plan_parser.py` | Harness | Load/save/query `plans/plan.yaml` |
| Task Parser | `.claude/scripts/task_parser.py` | Harness | Load/save/query `plans/tasks/CP-*.yaml` |
| Seam Parser | `.claude/scripts/seam_parser.py` | Harness | Load/save/query `plans/seams.yaml` |
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
