---
trigger: always_on
globs: **
---

# PROJECT WORKFLOW AWARENESS

> This file provides ambient awareness of the project framework. It does NOT enforce workflows - it informs the agent what exists so it can SUGGEST appropriately.

---

## Document Hierarchy (Macro / Meso / Micro)

**Macro (Strategic) -- Persistent:**

- **`plans/PRD.md`:** The origin seed. Business requirements and high-level data flow.
- **`plans/project-spec.md`:** **The Living Architecture.** Contains Interface Registry (Structure) and **Component Specifications (Behavioral Design/CRC)**. Single source of truth.
- **`plans/PLAN.md`:** Strategic roadmap and high-level Checkpoints (Persistent).
- **`interfaces/*.pyi`:** Protocol definitions, the binding contracts (Persistent, grows).

**Meso (Session) -- Ephemeral:**

- **`plans/execution-handoff-bundle.md`:** Bounded session scope for the next implementation phase (Ephemeral, overwritten per `/io-handoff`).

**Micro (Execution) -- Mixed:**

- **`plans/tasks.json`:** Current phase atomic work items (Ephemeral, overwritten per checkpoint).
- **`plans/progress.md`:** Historical log of completed work (Append-only archive).

**Flow:** Requirements (`plans/PRD.md`) -> **Design (`plans/project-spec.md` CRC)** -> Contracts (`interfaces/*.pyi`) -> **Handoff (`plans/execution-handoff-bundle.md`)** -> Tasks (`plans/tasks.json`) -> Implementation (Target paths defined in `plans/project-spec.md`).

---

## Core Methodology: Contract-Driven Development (CDD)

This project strictly follows **Contract-Driven Development**.

1. **Design First**: Behavior is defined in `plans/project-spec.md` (CRC Cards) before code.
2. **Contracts Second**: Interfaces are defined in `interfaces/*.pyi` (Pure Static Stubs) before implementation.
3. **Implementation Last**: Code implements the interfaces.

### [CRITICAL] STATIC TYPING RULES

1. **Pure Static Stubs**: `.pyi` files in `interfaces/` are for static analysis ONLY. NEVER rename them to `.py`.
2. **No Runtime Imports**: Python code (`.py`) must NEVER import from `.pyi` files at runtime (except inside `if TYPE_CHECKING:`).
3. **No Inheritance**: Implementation classes must NOT inherit from `.pyi` Protocols at runtime. Use structural subtyping (implicit implementation).

### [HARD] Protocol-Typed Injection Pattern

When a class receives a Protocol-typed collaborator via `__init__`:

1. Add `from __future__ import annotations` at the top of the module.
2. Import the Protocol inside `if TYPE_CHECKING:` only.
3. Use the Protocol name (not the concrete class) in the `__init__` signature.
4. The concrete class import is ONLY permitted in test fixtures and entrypoint wiring (Layer 4).

---

## Available Workflows

When user needs structured work, **SUGGEST** the appropriate prompt (never auto-invoke):

- **"Validate my plan", "Check this plan for CDD compliance"** -> `/review-plan`
- **"Start new project", "Initialize from PRD"** -> `/io-init`
- **"Design the interface", "Update architecture"** -> `/io-architect`
- **"Scope the next session", "Build handoff bundle"** -> `/io-handoff`
- **"Plan the next sprint", "Break down CP2"** -> `/io-tasking`
- **"Build feature", "Execute tasks"** -> `/io-loop`
- **"Review code", "Check this module"** -> `/review`
- **"Check for drift", "Compare code vs design"** -> `/gap-analysis`
- **"Sync the docs", "Update README"** -> `/doc-sync`
- **"PRD changed", "Propagate requirements"** -> `/io-replan`

## [HARD] Workflow Sequencing

When recommending or selecting the next workflow, follow this decision tree. Do NOT use informal reasoning about item complexity.

### Canonical Chain

```
[Pre-Entry Gate: /review-plan (iterate until PASS)]
    -> /io-architect -> /io-handoff -> /io-tasking -> /io-loop
    -> /review -> /gap-analysis -> /doc-sync
```

`/review-plan` is an iterative pre-entry gate run *before* the canonical chain. It is read-only and mutates no artifacts. Each workflow's output names the next step. Never skip links in the chain.

### Recommendation Gate (Pre-Invocation)

Before suggesting a workflow, read the Remediation Backlog in `plans/PLAN.md`:

1. **If an implementation plan exists and has not been validated** -> Recommend `/review-plan`.
2. **If open `[DESIGN]` or `[REFACTOR]` items exist** -> Recommend `/io-architect`.
3. **If only `[CLEANUP]`, `[TEST]`, or no backlog items** -> Recommend `/io-handoff`.
4. **If `execution-handoff-bundle.md` is current and `tasks.json` is empty** -> Recommend `/io-tasking`.
5. **If `tasks.json` has pending tasks** -> Recommend `/io-loop`.

The backlog tags are machine-readable gates, not suggestions. Never bypass step 2 based on informal assessment of item complexity.

## Workflow Constraints

> Stop-gates and enforcement rules are inlined into each workflow's `.md` file (e.g., `io-architect.md`, `io-tasking.md`, `io-handoff.md`). Ticket routing rules live in `.agent/rules/ticket-taxonomy.md`. This file provides awareness only.

---

## Default Behavior (No Workflow Invoked)

1. **Respond directly** to questions and requests
2. **Reference documents** when relevant (check plans/PLAN.md for requirements, interfaces/*.pyi for contracts)
3. **Suggest prompts** if structured output would help - phrase as a question, not an action
4. **Never assume** the user wants a formal workflow unless they invoke one

---

## Edit Permissions

- **`plans/PRD.md`:** Only with explicit approval (user-owned seed doc)
- **`plans/PLAN.md`:** Only with explicit approval (user-owned strategic doc)
- **`interfaces/*.pyi`:** Yes, when adding Protocols via io-architect
- **`plans/project-spec.md`:** Yes, when adding Protocol references or updating architecture
- **`plans/tasks.json`:** Yes, when planning phases or marking complete
- **`plans/progress.md`:** Append only, when tasks complete
- **Implementation files, `tests/**`:** Yes, during implementation work

---

## Context Gathering

When working on this project, check these sources:

1. **What is the system design and where does code live?** -> `plans/project-spec.md`
2. **What contracts exist?** -> `interfaces/*.pyi`
3. **What is the current session scope?** -> `plans/execution-handoff-bundle.md`
4. **What's being worked on now?** -> `plans/tasks.json`

## Claude Code Native Integration

1. **Slash commands are the canonical workflow entry points.** All workflows are available as native slash commands in `.claude/commands/`. Invoke them directly (e.g. `/io-handoff`, `/gap-analysis`, `/review-plan`) rather than describing or manually executing the workflow steps.

2. **PreToolUse hooks are the gate — do not duplicate their checks.** The write-gate, DI compliance gate, and forbidden-tools gate are enforced automatically by PreToolUse hooks before every relevant tool call. Do not manually verify these conditions before issuing a write; the hooks will block non-compliant actions without requiring a pre-flight check.

3. **Use `/ide` to connect to VS Code when running from an external terminal.** When Claude Code is launched from a terminal outside VS Code, run `/ide` to establish the IDE connection. This enables diff viewing inside the editor and diagnostic sharing (errors, warnings) between the IDE and the agent.
