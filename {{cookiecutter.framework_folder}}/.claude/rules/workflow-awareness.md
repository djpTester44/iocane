---
paths:
  - "plans/PRD.md"
  - "plans/roadmap.md"
  - "plans/project-spec.md"
  - "plans/plan.md"
  - "plans/backlog.md"
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
| Checkpoint Plan | `plans/plan.md` | Human (via /io-checkpoint) | Atomic checkpoints, connectivity test signatures |
| Task Files | `plans/tasks/[CP-ID].md` | Orchestrator | Per-checkpoint sub-agent work packages |
| Dispatch Script | `plans/tasks/run.sh` | Orchestrator | Worktree setup and sub-agent invocation |
| Status Files | `plans/tasks/[CP-ID].status` | Sub-agent | PASS/FAIL per checkpoint |
| Backlog | `plans/backlog.md` | Review workflows | Bugs, issues, enhancements from /io-review and /gap-analysis. Each item has a `**BL-NNN**` identifier (auto-assigned by hook). |
| Escalation Log | `.iocane/escalation.log` | Hook | Sub-agent failure records |

---

## Edit Permissions

| Artifact | Permission |
|----------|------------|
| `plans/PRD.md` | Only with explicit human approval |
| `plans/roadmap.md` | Only via `/io-specify` with human approval |
| `plans/project-spec.md` | Via `/io-architect` (design) or `/doc-sync` (reconciliation only) |
| `interfaces/*.pyi` | Only via `/io-architect` with human approval -- never during execution |
| `plans/plan.md` | Only via `/io-checkpoint` with human approval |
| `plans/tasks/[CP-ID].md` | Written by `/io-orchestrate` -- not edited manually |
| `plans/tasks/run.sh` | Written by `/io-orchestrate` -- not edited manually |
| `plans/backlog.md` | Append via `/review-capture` -- never delete entries. Route via `route-backlog-item.sh`. |
| `src/`, `tests/` | Only during execution, scoped to checkpoint write_targets |

---
