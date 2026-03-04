# Project Lifecycle and Maintenance

This artifact defines the workflows for bootstrapping projects, executing atomic tasks using the Iocane Loop, and maintaining the codebase through cleanup and refactoring.

---

## 1. Project Lifecycle (Strategic Management)

Execution follows a strict chronology to ensure code is designed before being implemented.
1. **Strategic Selection**: Bootstrap a project via **/io-init** (greenfield) or **/io-adopt** (brownfield).
2. **Behavioral Design**: Anchor components in [plans/project-spec.md](cci:7://file:///c:/Users/danny/projects/agy/cMab_013126/plans/project-spec.md:0:0-0:0) using CRC cards and Mermaid diagrams.
3. **Structural Contract**: Define [.pyi](cci:7://file:///c:/Users/danny/projects/agy/cMab_013126/interfaces/orchestrator.pyi:0:0-0:0) protocols using **/io-architect**.
4. **Execution Handoff**: Scope a bounded execution session via **/io-handoff**. Enforces the backlog gate (`[DESIGN]`/`[REFACTOR]` items block new CP work).
5. **Tactical Tasking**: Decompose designs into atomic TDD tasks in [plans/tasks.json](cci:7://file:///c:/Users/danny/projects/agy/cMab_013126/plans/tasks.json:0:0-0:0) via **/io-tasking**.
6. **Atomic Execution**: Execute tasks via **/io-loop**.
7. **Gap Analysis**: Compare current state against architectural designs via **/gap-analysis** to verify implementation fidelity and identify drift.

**Pre-Entry Gate:** **/review-plan** is an iterative validation gate run *before* steps 2-3. Plans are iterated until they receive a `**Plan Validated:** PASS` marker, which `/io-architect` checks before modifying any CRC or Protocol artifacts.

---

## 2. Atomic Execution: The Iocane Loop

The Iocane Loop prevents "Context Overload" by forcing a STOP and verification after every operation.

| State | Goal | Action | Stop Condition |
| :--- | :--- | :--- | :--- |
| **SETUP (Scaffold)** | Map architectural surface area. | Create/Update target files and stubs. | Complete. |
| **RED (Test)** | Create a failing test. | Write unit tests using `pytest` and mocks. | Verify test fails. |
| **GREEN (Implement)**| Pass the test. | Implement minimal logic. | Verify test passes. |
| **REFACTOR (Blue)** | Clean the code. | Run `ruff`, `mypy`, and `lint-imports`. | Complete. |
| **VERIFY (Observe)** | Confirm integration. | Execute verification commands. | Complete. |

### 3.1 State Management (LOOP)
- **Mark Task Complete**: Update `tasks.json`.
- **Append Log**: Add a log entry to [plans/progress.md](cci:7://file:///c:/Users/danny/projects/agy/cMab_013126/plans/progress.md:0:0-0:0).
- **Drift Guard**: If implementation deviates from the spec, STOP and update the spec before continuing.

---

## 3. Fresh Workspace Scaffolding (CDD)

Used for new projects to ensure all architectural rules and hooks are correctly placed.
- **Scaffold Runner**: Use `python C:\Users\danny\.gemini\scripts\scaffold_runner_CDD.py`.
- **Primary Setup**: Injects `.agent/` rules, templates, and initializes `interfaces/`.
- **Verification**: `uv sync`, `ruff check`, `mypy`, `pytest`.

---

## 4. Maintenance: Dead Code Deletion Protocol

When removing redundant or dead code, prove it is unused before deletion.

1. **PROVE Dead Status**:
   - `grep -r "from src.path.to.module" src/`
   - `grep -r "import src.path.to.module" src/`
   - Verify zero integration test usage.
2. **DELETE Code**: Remove the [.py](cci:7://file:///c:/Users/danny/projects/agy/cMab_013126/src/core/config.py:0:0-0:0) and corresponding [.pyi](cci:7://file:///c:/Users/danny/projects/agy/cMab_013126/interfaces/orchestrator.pyi:0:0-0:0).
3. **Verify Integrity**:
   - `uv run lint-imports` (Broken internal references).
   - `uv run mypy .` (Type signature drift).
   - `uv run pytest` (Broken and behavioral regressions).
4. **Cleanup Spec**: Prune the Interface Registry or Architecture Map in [plans/project-spec.md](cci:7://file:///c:/Users/danny/projects/agy/cMab_013126/plans/project-spec.md:0:0-0:0).

---

## 5. Document Synchronization (/doc-sync)

The **Doc-Sync** workflow reconciles the **Macro/Meso/Micro Hierarchy** (Design > Contracts > Code) after completing a phase or making significant architectural changes.

**Objective**: Ensure that documentation is not just a historical log, but an active, accurate reflection of the current codebase state.

### 5.1 Verification Checklist
1.  **Identity Sync**: Update [README.md](cci:7://file:///c:/Users/danny/projects/agy/cMab_013126/README.md:0:0-0:0) to match the current structural template ([.agent/templates/README.md](cci:7://file:///c:/Users/danny/projects/agy/cMab_013126/.agent/templates/README.md:0:0-0:0)) while preserving project identity and instructions.
2.  **Constraint Integrity**: Ensure `project-spec.md` reflects the actual layer mappings and core stack.
3.  **Anchor Check**: Run the automated **Design Anchor Audit** (`check_design_anchors.py`) to verify Spec-to-Code alignment. Use `extract_structure.py` to map files to registry entries.
4.  **Backlog Reconciliation**: Read the `Remediation Backlog` in [PLAN.md](cci:7://file:///c:/Users/danny/projects/agy/cMab_013126/plans/PLAN.md:0:0-0:0). For each pending item, verify if the fix exists in the codebase and mark `[x]` if confirmed.
5.  **Strategic Doc Review**: Any updates to strategic roadmaps (e.g., [PLAN.md](cci:7://file:///c:/Users/danny/projects/agy/cMab_013126/plans/PLAN.md:0:0-0:0) checkpoints or `PRD.md`) require **explicit user approval**. Present proposed changes as a diff before applying.
6.  **Link Integrity**: Verify that all `file:///` and relative markdown links are valid using link checker tools or manual searches across `plans/` and `README.md`.