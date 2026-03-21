# WORKFLOW AWARENESS

## Three-Tier Architecture

Iocane operates across three tiers. Each tier has distinct ownership, tooling, and autonomy level.

| Tier | Owner | Mode | Artifacts |
|------|-------|------|-----------|
| Tier 1 — Strategic | Human + Claude | Plan mode | `PRD.md`, `roadmap.md`, `project-spec.md`, `interfaces/*.pyi`, `plan.md` |
| Tier 2 — Orchestration | Harness autonomous | No plan mode | `plans/tasks/[CP-ID].md`, `plans/tasks/run.sh` |
| Tier 3 — Execution | Sub-agents | No plan mode | `src/`, `tests/`, `plans/tasks/[CP-ID].status` |

Human owns all Tier 1 decisions. Nothing in Tier 2 or Tier 3 executes until the human approves the Tier 1 artifacts.

---

## Artifact Registry

| Artifact | Location | Owner | Purpose |
|----------|----------|-------|---------|
| PRD | `plans/PRD.md` | Human | Requirements, user stories, stack decisions |
| Roadmap | `plans/roadmap.md` | Human (via /io-specify) | Feature sequence, dependency order |
| Architecture Spec | `plans/project-spec.md` | Human (via /io-architect) | CRC cards, Interface Registry — current codebase state only |
| Contracts | `interfaces/*.pyi` | Human (via /io-architect) | Binding Protocol definitions |
| Checkpoint Plan | `plans/plan.md` | Human (via /io-checkpoint) | Atomic checkpoints, connectivity test signatures |
| Task Files | `plans/tasks/[CP-ID].md` | Orchestrator | Per-checkpoint sub-agent work packages |
| Dispatch Script | `plans/tasks/run.sh` | Orchestrator | Worktree setup and sub-agent invocation |
| Status Files | `plans/tasks/[CP-ID].status` | Sub-agent | PASS/FAIL per checkpoint |
| Backlog | `plans/backlog.md` | Review workflows | Bugs, issues, enhancements from /io-review and /gap-analysis. Each item has a `**BL-NNN**` identifier (auto-assigned by hook). |
| Escalation Log | `.iocane/escalation.log` | Hook | Sub-agent failure records |
| Progress Log | `plans/progress.md` | Append-only | Historical task completion ledger |

---

## Canonical Workflow Sequence

```
[Tier 1 — Human + Plan Mode]

/brainstorm         — optional ideation before PRD exists
/io-clarify         — resolve PRD ambiguities, stamp Clarified: True
/io-specify         — PLAN MODE — propose roadmap.md, human approves
/io-architect       — PLAN MODE — propose CRC + Protocols + Interface Registry, human approves
                      ^ CONTRACT LOCK — Tier 1 / Tier 2 boundary
/io-checkpoint      — PLAN MODE — propose plan.md + connectivity test signatures, human approves

[Tier 2 — Harness Autonomous]

/io-orchestrate     — read plan.md, score confidence rubric, generate task files + run.sh
                    — human runs: bash plans/tasks/run.sh

[Tier 3 — Sub-agents]

(sub-agents execute via run.sh in isolated git worktrees)
(status files written to plans/tasks/[CP-ID].status)

[Tier 1 — Human Review]

/io-review             — per-checkpoint behavioral + connectivity review, findings → backlog.md
/io-orchestrate     — next checkpoint batch (loop)

[Full-system, after all checkpoints]

/gap-analysis       — integration correctness, findings → backlog.md
/doc-sync           — reconcile project-spec.md + roadmap.md with codebase state
```

---

## Plan Mode Usage

| Workflow | Plan Mode | Reason |
|----------|-----------|--------|
| `/io-specify` | YES | Proposes roadmap.md — human must approve before write |
| `/io-architect` | YES | Proposes CRC + Protocols — highest-value gate, contract lock |
| `/io-checkpoint` | YES | Proposes plan.md — human must approve checkpoint boundaries |
| `/io-orchestrate` | NO | Autonomous — reads approved artifacts, generates task files |
| `/io-execute` | NO | Autonomous — executes single checkpoint, terminates |
| `/io-review` | NO | Read-only analysis |
| `/gap-analysis` | NO | Read-only analysis |
| `/doc-sync` | NO | Reconciliation against approved artifacts |

---

## Workflow Recommendations

When no workflow is invoked, recommend based on project state:

1. No `plans/PRD.md` → suggest `/brainstorm` or manual PRD creation
2. PRD exists, `Clarified: False` → suggest `/io-clarify`
3. PRD clarified, no `roadmap.md` → suggest `/io-specify`
4. Roadmap present, no `interfaces/*.pyi` → suggest `/io-architect`
5. Contracts locked, no `plan.md` → suggest `/io-checkpoint`
6. `plan.md` present, `.iocane/escalation.flag` exists → instruct human to review escalation log
7. `plan.md` present, open `[DESIGN]` backlog items → suggest `/io-architect` before orchestrating
8. Unblocked checkpoints available → suggest `/io-orchestrate`
9. `plans/tasks/run.sh` written but not executed → instruct: `bash plans/tasks/run.sh`
10. All checkpoints complete → suggest `/io-review`, then `/gap-analysis`, then `/doc-sync`

---

## Edit Permissions

| Artifact | Permission |
|----------|------------|
| `plans/PRD.md` | Only with explicit human approval |
| `plans/roadmap.md` | Only via `/io-specify` with human approval |
| `plans/project-spec.md` | Via `/io-architect` (design) or `/doc-sync` (reconciliation only) |
| `interfaces/*.pyi` | Only via `/io-architect` with human approval — never during execution |
| `plans/plan.md` | Only via `/io-checkpoint` with human approval |
| `plans/tasks/[CP-ID].md` | Written by `/io-orchestrate` — not edited manually |
| `plans/tasks/run.sh` | Written by `/io-orchestrate` — not edited manually |
| `plans/backlog.md` | Append via `/review-capture` — never delete entries. Route via `route-backlog-item.sh`. |
| `plans/progress.md` | Append only — never read into context during execution |
| `src/`, `tests/` | Only during execution, scoped to checkpoint write_targets |

---

## Context Gathering

When working on a project, check these sources in order:

1. What is the system design? → `plans/project-spec.md`
2. What contracts exist? → `interfaces/*.pyi`
3. What checkpoints are planned? → `plans/plan.md`
4. What is being worked on now? → `plans/tasks/[CP-ID].md` (current checkpoint)
5. What needs fixing? → `plans/backlog.md`

---

## Claude Code Native Integration

1. **Slash commands are the canonical entry points.** All workflows are available as slash commands in `.claude/commands/`. Invoke directly — do not manually execute workflow steps.

2. **PreToolUse hooks enforce gates automatically.** The write-gate, DI compliance gate, and forbidden-tools gate fire before every relevant tool call. Do not duplicate these checks manually.

3. **Sub-agents run headless via `bash plans/tasks/run.sh`.** Do not attempt to invoke sub-agents directly from an interactive session. The orchestrator generates `run.sh` for this purpose.
