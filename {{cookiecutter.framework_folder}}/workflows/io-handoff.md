---
description: Generate a bounded execution session from the macro plan or remediation backlog.
---

> **[CRITICAL] CONTEXT LOADING**
> 1. Load the planning rules: `view_file .agent/rules/planning.md`
> 2. Load the Roadmap: `view_file plans/PLAN.md`
> 3. Load the Architecture: `view_file plans/project-spec.md`

# WORKFLOW: IOCANE HANDOFF

**Objective:** Slice the macro architecture into a strictly bounded meso-state for the next implementation phase.

## 1. STATE INITIALIZATION
Before proceeding to Step 2, you must output the following metadata to confirm the session boundaries:
- **Active Path:** [Backlog Cleanup OR Sequential Checkpoint]
- **Target Component:** [Component Name and Layer, e.g., src/domain/router.py]
- **Dependency Scope:** [List required .pyi interfaces from project-spec.md]
- **Restricted Zones:** [List directories explicitly out of bounds for this session]

---

## 2. PROCEDURE

### Step A: [HARD GATE] REMEDIATION BACKLOG CHECK
* **Action:** Read `plans/PLAN.md` section `## 3. Remediation Backlog`.
* **Logic:** Check for pending `[ ]` items, ignoring `[DEFERRED]`.
* **Routing:** Route the execution path according to the Hard Gates defined in `.agent/rules/ticket-taxonomy.md` (e.g., haling on `[DESIGN]` or `[REFACTOR]`, setting Active Path to "Backlog Cleanup" for `[CLEANUP]`).

### Step A.5: [SOFT GATE] DI PRE-FLIGHT
* **Action:** Run `uv run python .agent/scripts/check_di_compliance.py`.
* **Logic:** If any `[WARNING]` or `[CRITICAL]` findings exist:
    * Check if each finding already has a matching entry in the Remediation Backlog.
    * If unmatched findings exist: WARN (do not hard-halt) and list them. Suggest running `/gap-analysis` with context to validate before proceeding.
    * If all findings are tracked: proceed normally.

### Step B: IDENTIFY ACTIVE SCOPE (Standard Checkpoint)
* **Action:** Identify the first Checkpoint in `plans/PLAN.md` not marked `[x]`.
* **Action:** Identify the specific component and layer targeted by this Checkpoint.

### Step C: DEFINE BOUNDARIES
* **Action:** Determine exact read-only `.pyi` interfaces required for this component.
* **Action:** Identify forbidden directories (e.g., if in `src/inference`, then `src/data` is forbidden).
* **Action:** Determine the necessary test files for validation.

### Step C.5: [HARD] CONTEXT INGESTION (L8)
* **Action:** Read the Target Implementation `.py` file and the corresponding `.pyi` Protocol contract.
* **Action:** Compare the implementation against the contract to identify concrete gaps (missing methods, signature mismatches, missing return types).
* **Output:** Emit a **Concrete Findings** section in the handoff bundle listing exact method signatures that need to be added, changed, or removed. This is epistemic work that MUST be completed here in the Meso tier -- never delegate "review," "understand," or "research" to `tasks.json` or `/io-loop`.

### Step D: GENERATE BUNDLE
* **Action:** Overwrite `plans/execution-handoff-bundle.md` using the exact structure below:

```markdown
# Execution Handoff Bundle

## Session Goal
[Insert precise technical objective]

## Allowed Scope
- **Target Implementation:** `src/[module_path]`
- **Read-Only Context:** `interfaces/[protocol].pyi`
- **Restricted Zones:** Modification of any file outside the Target Implementation is strictly forbidden.

## Concrete Findings
[List exact missing/mismatched method signatures discovered in Step C.5, e.g.:]
- Missing: `get_params(self, model_type: ModelType) -> dict[str, Any]`
- Missing: `incremental_train(self, model_type: ModelType, new_dtrain: TrainMatrix, current_booster: xgb.Booster, num_rounds: int = 10) -> BanditLearner`

## Preload Targets
- `interfaces/[protocol].pyi`
- `tests/[module_path]/test_[target].py`
- `src/[module_path]`

## Active Tasking Instruction
Run `/io-tasking`. The tasking agent must ONLY use the files listed in the Preload Targets above to generate `tasks.json`.
```

---

## 3. OUTPUT
* Output: "MESO STATE LOCKED. Run `/io-tasking` to generate the micro-queue."