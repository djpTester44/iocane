---
description: Validate plans/plan.md checkpoint structure against CDD principles before orchestration. Pre-entry gate for /io-plan-batch.
---

> **[CRITICAL] CONTEXT LOADING**
> Load the analysis constraints:
> `view_file .agent/rules/planning.md`
> `view_file .agent/rules/execution.md`

# WORKFLOW: VALIDATE-PLAN (CDD Compliance)

**Objective:** Pre-orchestration validation that `plans/plan.md` maintains CDD structural integrity — CRC-Protocol symmetry, checkpoint atomicity, connectivity test completeness, and write-target registry alignment — before any sub-agent is dispatched.

**Context:**

* Target artifact: `plans/plan.md`
* Output: Findings table with actionable recommendations and a PASS/FAIL stamp on `plans/plan.md`
* Trigger: Run before `/io-plan-batch` to catch structural violations before task files are generated. Iterate until PASS.

**Position in chain:**
```
/io-checkpoint -> [/validate-plan] -> /io-plan-batch -> /io-orchestrate
```

---

## 1. PROCEDURE

### Step 1: IDENTIFY SCOPE

* Load `plans/plan.md`.
* Identify all checkpoint entries (CP-NN sections).
* Count: total checkpoints, checkpoints with `depends_on`, parallelizable pairs, connectivity test signatures defined.

---

### Step 2: LOAD ANCHORS

For every component referenced across all checkpoints in `plans/plan.md`:

* Read its **CRC Card** from `plans/project-spec.md`.
* Read its **Protocol** from `interfaces/*.pyi`.
* Read the **Interface Registry** in `plans/project-spec.md` to verify file path mappings.
* For each component's implementation file, run `python extract_structure.py <file>` to load its structural skeleton (signatures, decorators, docstrings) into context. Do not load full file contents.

Files loaded in this step remain in context for all subsequent steps — do not re-read any file already loaded unless it has been modified during this run.

---

### Step 3: LOAD LAYER CONTRACTS

Read `pyproject.toml` section `[tool.importlinter]` to understand:

* Which packages are `root_packages`.
* All `[[tool.importlinter.contracts]]` entries. For each, note:
  * `type = "independence"` — these packages cannot import each other.
  * `type = "layers"` — packages are ordered top-to-bottom; lower layers cannot import higher.

Use this to inform checks 4–10 below.

---

### Step 4: CHECK — Private Method Gate

> **[HARD]** `_`-prefixed methods are internal implementation details.

* If any checkpoint write target or Protocol reference in `plan.md` names a `_`-prefixed method as a deliverable, flag immediately.
* **Flag:** `PRIVATE_METHOD_PROMOTION`

---

### Step 5: CHECK — CRC-Protocol Symmetry per Checkpoint

For each checkpoint:

* Every Protocol method listed in the checkpoint's Contract section must have a corresponding CRC responsibility in `project-spec.md`.
* Every CRC responsibility named in the checkpoint must map to at least one Protocol method.
* **Flag:** Protocol method with no CRC anchor = `UNANCHORED_CONTRACT`
* **Flag:** CRC responsibility with no Protocol method = `ORPHANED_DESIGN` (acceptable only for private helpers)

---

### Step 6: CHECK — Checkpoint Atomicity

* Each checkpoint must reference components from a single CRC card, or if multi-component, the components must be explicitly named and their Protocols cross-referenced.
* CRC + Protocol changes for the same component must appear in the same checkpoint, not split across multiple.
* **Flag:** CRC and Protocol for the same component in separate ungrouped checkpoints = `ATOMICITY_VIOLATION`

---

### Step 7: CHECK — Write Target Registry Alignment

For every write target listed in every checkpoint:

* Verify the file path appears in the Interface Registry of `plans/project-spec.md`.
* **Flag:** Write target not in Interface Registry = `UNREGISTERED_WRITE_TARGET`

---

### Step 8: CHECK — Layer Boundary Compliance

Using the contracts loaded in Step 3:

* Verify that all write targets respect layer and independence contracts.
* **Flag:** Plan proposes a write target that would introduce a lower-to-higher import = `LAYER_VIOLATION`
* **Flag:** Plan proposes a write target that would introduce a cross-peer import in an independence contract = `INDEPENDENCE_VIOLATION`

---

### Step 9: CHECK — Connectivity Test Completeness

For the Connectivity Tests section of `plan.md`:

* Every seam between checkpoints with a dependency relationship must have at least one connectivity test.
* Each connectivity test must have: a CT-ID, a gate command (concrete pytest invocation), and a named checkpoint pair (producer → consumer).
* **Flag:** Dependency seam with no connectivity test = `MISSING_CONNECTIVITY_TEST`
* **Flag:** Connectivity test with placeholder gate command (e.g., `# TODO`) = `PLACEHOLDER_GATE`

---

### Step 10: CHECK — DI Compliance Preview

If any checkpoint introduces a new collaborator:

* Verify the task description specifies injection via `__init__` parameter, not inline instantiation.
* **Flag:** New collaborator described as instantiated inline = `HARDCODED_DEPENDENCY`
* **Flag:** `os.environ` / `os.getenv` described outside Entrypoint layer = `ENV_LEAK`

---

### Step 11: OUTPUT FINDINGS

Generate a Plan Validation report:

* **Summary:** One-paragraph assessment (PASS / FAIL with violation count).
* **Findings Table:**

| # | Check | Checkpoint | Component | Finding | Severity | Auto-Remediable? |
|---|-------|------------|-----------|---------|----------|-----------------|
| 1 | CRC-Protocol Symmetry | CP-NN | ... | ... | VIOLATION | Yes/No |

* **Required Amendments:** Specific changes to `plan.md` (as checkboxes).

---

### Step 12: SELF-HEALING LOOP

**Auto-Remediable Violations** (agent amends `plan.md` directly):

| Flag | Auto-Fix Action |
|---|---|
| `PRIVATE_METHOD_PROMOTION` | Remove the `_`-prefixed method reference from the checkpoint section. |
| `UNANCHORED_CONTRACT` | Add the missing CRC responsibility reference to the checkpoint's description. |
| `ORPHANED_DESIGN` | Add the missing Protocol method reference to the checkpoint's Contract section. |
| `ATOMICITY_VIOLATION` | Merge the split checkpoint sections into a single checkpoint entry. |
| `PLACEHOLDER_GATE` | Flag for human — cannot auto-generate a concrete gate command. Treat as non-auto-remediable. |

**Non-Auto-Remediable Violations** (escalate to user immediately):

| Flag | Why |
|---|---|
| `LAYER_VIOLATION` | Requires architectural judgment on import placement. |
| `INDEPENDENCE_VIOLATION` | Requires architectural judgment on dependency direction. |
| `HARDCODED_DEPENDENCY` | Needs human decision on DI wiring location. |
| `ENV_LEAK` | Needs human decision on config injection approach. |
| `UNREGISTERED_WRITE_TARGET` | Requires `/io-architect` to register the component before orchestration. |
| `MISSING_CONNECTIVITY_TEST` | Requires `/io-checkpoint` amendment — gate command must be human-specified. |
| `PLACEHOLDER_GATE` | Gate command must be a concrete, runnable pytest invocation. |

**Loop Procedure:**

1. If all VIOLATIONs are auto-remediable: amend `plan.md`, mark each change `[AUTO-AMENDED]`, and re-run checks 4–10.
2. If any non-auto-remediable VIOLATION exists: stop immediately and escalate to user with findings.
3. After each pass, compare violation set to previous pass. If no new violations appear, the loop has converged — proceed to Step 13.
4. If the same violation recurs across two consecutive passes: stop and escalate to the user.
5. On success: proceed to Step 13.

---

### Step 13: STAMP RESULT

**Severity Guide:**

* **VIOLATION:** Blocks orchestration. Must be resolved (auto or manual) before proceeding.
* **OBSERVATION:** Should fix. Orchestration may proceed but risk of drift.
* **INFO:** Optional improvement. Does not block.

**Gate Behavior:**

* If all VIOLATIONs are auto-remediable, the agent fixes them and re-validates until no new violations appear, or escalates if the same violation recurs across two consecutive passes.
* If any non-auto-remediable VIOLATION exists, the plan **FAILS** and the user must intervene.
* Only a **PASS** result (zero VIOLATIONs) allows `/io-plan-batch` to proceed.

**Gate Artifact:**

Write the stamp using the following strictly sequential steps. Do NOT parallelize — the sentinel must exist before the Edit tool call fires.

- **Step 13-pre:** `bash: mkdir -p .iocane && touch .iocane/validating`
- **Step 13:** On **PASS**, stamp `plans/plan.md` with: `**Plan Validated:** PASS (YYYY-MM-DD)`. On **FAIL**, stamp `plans/plan.md` with: `**Plan Validated:** FAIL (YYYY-MM-DD)` and list the blocking violations.

The sentinel prevents `reset-on-plan-write.sh` from immediately reverting a PASS stamp back to FAIL. The hook auto-deletes the sentinel when it detects the `**Plan Validated:** PASS` or `**Plan Validated:** FAIL` stamp write — no explicit cleanup step required.

* `/io-plan-batch` **MUST** check for a `**Plan Validated:** PASS` marker before composing the batch. If missing or FAIL, halt and recommend `/validate-plan`.

**Self-Healing Log:**

* All auto-amendments must be logged in `plans/plan.md` under a `## Self-Healing Log` section.
* Each entry: `[AUTO-AMENDED] <iteration> | <flag> | <checkpoint> | <what was changed>`

---

## 2. CONSTRAINTS

- Target artifact is `plans/plan.md` — not any session-specific plan document.
- Files loaded into context are not re-read unless the file has been modified during the current run.
- Auto-amend only the violations classified as auto-remediable above.
- Do not expand scope beyond what `plan.md` proposes.
- Do not route findings to `plans/backlog.md` — this is a pre-orchestration gate, not a post-implementation review.
- Do not execute the plan. Amend and validate only.
- `UNREGISTERED_WRITE_TARGET` findings must route to `/io-architect`, not be auto-amended.
- `MISSING_CONNECTIVITY_TEST` findings must route to `/io-checkpoint` amendment, not be auto-amended.
