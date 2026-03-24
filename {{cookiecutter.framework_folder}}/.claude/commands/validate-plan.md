---
name: validate-plan
description: Validate plans/plan.md checkpoint structure against CDD principles before orchestration. Pre-entry gate for /io-plan-batch.
---

> **[CRITICAL] CONTEXT LOADING**
> Load the analysis constraints:
> `view_file .claude/rules/planning.md`

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

### Step 2: PHASE 1 — STRUCTURAL CONTEXT LOAD

Load the following — and only the following — before running Phase 1 checks:

* **Interface Registry table** from `plans/project-spec.md` — load the registry section only, not the full file. This provides file path mappings for write-target verification.
* **`pyproject.toml`** — load the `[tool.importlinter]` section to understand `root_packages` and all `[[tool.importlinter.contracts]]` entries (type `independence` and type `layers`).

`plans/plan.md` is already in context from Step 1.

Do NOT load CRC cards, Protocol files, `plans/seams.md`, or run `extract_structure.py` here. Those belong to Phase 2.

Files loaded in this step remain in context for all subsequent steps — do not re-read any file already loaded unless it has been modified during this run.

---

### Step 4: CHECK — Private Method Gate [Phase 1]

> **[HARD]** `_`-prefixed methods are internal implementation details.

* If any checkpoint write target or Protocol reference in `plan.md` names a `_`-prefixed method as a deliverable, flag immediately.
* **Flag:** `PRIVATE_METHOD_PROMOTION`

---

### Step 7: CHECK — Write Target Registry Alignment [Phase 1]

For every write target listed in every checkpoint:

* Verify the file path appears in the Interface Registry of `plans/project-spec.md`.
* **Flag:** Write target not in Interface Registry = `UNREGISTERED_WRITE_TARGET`

**Exemptions (INFO only, not VIOLATION):**

* `tests/` files — test infrastructure is not an architectural component.
* Project tooling files outside `src/` (e.g. `pyproject.toml`, `ui/src/`).

**Not exempt under any circumstances:**

* Any file under `src/` — including internal utilities annotated "no Protocol." A `src/` file absent from the Interface Registry is always `UNREGISTERED_WRITE_TARGET` (VIOLATION), regardless of prior log precedents or "internal utility" annotations. Route to `/io-architect` for explicit registration or exemption before orchestration.

---

### Step 8: CHECK — Layer Boundary Compliance [Phase 1]

Using the contracts loaded in Step 2 (`pyproject.toml`):

* Verify that all write targets respect layer and independence contracts.
* **Flag:** Plan proposes a write target that would introduce a lower-to-higher import = `LAYER_VIOLATION`
* **Flag:** Plan proposes a write target that would introduce a cross-peer import in an independence contract = `INDEPENDENCE_VIOLATION`

---

### Step 9: CHECK — Connectivity Test Completeness [Phase 1]

For the Connectivity Tests section of `plan.md`:

* Every seam between checkpoints with a dependency relationship must have at least one connectivity test.
* Each connectivity test must have: a CT-ID, a gate command (concrete pytest invocation), and a named checkpoint pair (producer → consumer).
* **Flag:** Dependency seam with no connectivity test = `MISSING_CONNECTIVITY_TEST`
* **Flag:** Connectivity test with placeholder gate command (e.g., `# TODO`) = `PLACEHOLDER_GATE`

---

### [PHASE 1 HALT GATE]

After running Steps 4, 7, 8, and 9:

* If any Phase 1 check produced a **non-auto-remediable VIOLATION**: HALT immediately. Do not load Phase 2 context. Output findings and escalate to user.
* If all Phase 1 violations are auto-remediable: apply auto-fixes, mark `[AUTO-AMENDED]`, and re-run Steps 4, 7, 8, 9 only (no Phase 2 reload per self-heal iteration). See Step 12 for loop procedure.
* Only when Phase 1 is clean (zero Phase 1 VIOLATIONs): proceed to Phase 2.

---

### Step 2B: PHASE 2 — BEHAVIORAL CONTEXT LOAD

Load the following before running Phase 2 checks:

* **CRC cards** from `plans/project-spec.md` for every component referenced across all checkpoints that survived Phase 1.
* **Protocol files** (`interfaces/*.pyi`) for those same components.
* **`plans/seams.md`** — load now, not earlier. Steps 4, 7, 8, 9 do not require seam data.

Do NOT run `extract_structure.py` here. It runs at Step 10 only, scoped to checkpoints with new collaborators.

---

### Step 5: CHECK — CRC-Protocol Symmetry per Checkpoint [Phase 2 — requires CRC/Protocol context loaded above]

For each checkpoint:

* Every Protocol method listed in the checkpoint's Contract section must have a corresponding CRC responsibility in `project-spec.md`.
* Every CRC responsibility named in the checkpoint must map to at least one Protocol method.
* For each Protocol method in the checkpoint's Contract section, run `symbol_tracer.py --symbol "<Symbol1>,<Symbol2>" --root src/ --imports-only` to verify an implementation file imports and references it.
* **Flag:** Protocol method with no CRC anchor = `UNANCHORED_CONTRACT`
* **Flag:** CRC responsibility with no Protocol method = `ORPHANED_DESIGN` (acceptable only for private helpers)

---

### Step 6: CHECK — Checkpoint Atomicity [Phase 2 — requires CRC/Protocol context loaded above]

* Each checkpoint must reference components from a single CRC card, or if multi-component, the components must be explicitly named and their Protocols cross-referenced.
* CRC + Protocol changes for the same component must appear in the same checkpoint, not split across multiple.
* **Flag:** CRC and Protocol for the same component in separate ungrouped checkpoints = `ATOMICITY_VIOLATION`

---

### Step 10: CHECK — DI Compliance Preview [Phase 2 — requires CRC/Protocol context loaded above]

`plans/seams.md` is already in context from Step 2B.

If any checkpoint introduces a new collaborator:

* Run `python extract_structure.py <file>` **only for checkpoints that introduce a new collaborator** — do not run it for all implementation files. Load structural skeletons (signatures, decorators, docstrings) into context for those files only.
* Verify the task description specifies injection via `__init__` parameter, not inline instantiation.
* Cross-reference the collaborator name against the `Receives (DI)` list for the receiving component in `plans/seams.md`. If the collaborator is absent from that list, flag `HARDCODED_DEPENDENCY` — the collaborator is either undeclared or being wired outside the approved DI contract.
* **Flag:** New collaborator described as instantiated inline = `HARDCODED_DEPENDENCY`
* **Flag:** New collaborator not present in the component's `Receives (DI)` entry in `plans/seams.md` = `HARDCODED_DEPENDENCY`
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

1. If all VIOLATIONs are auto-remediable: amend `plan.md`, mark each change `[AUTO-AMENDED]`, and re-run **Phase 1 checks only** (Steps 4, 7, 8, 9). Do not reload Phase 2 context on each loop iteration — Phase 2 context remains in context from initial load.
2. If any non-auto-remediable VIOLATION exists: stop immediately and escalate to user with findings.
3. After each pass, compare violation set to previous pass. If no new violations appear, the loop has converged — proceed to Step 13.
4. If the same violation recurs across 3 passes: the violation is structural. Execute the 3x-failure path below.
5. On success: proceed to Step 13.

**3x-Failure Path:**

When a violation has appeared in 3 consecutive passes without being resolved, auto-heal has exhausted its scope. The problem is in the underlying design, not in `plan.md` surface edits.

1. Stamp `plans/plan.md` with `**Plan Validated:** FAIL` (via Step 13 sentinel procedure).
2. Append an `## Architect Brief` section to `plans/plan.md`:

```markdown
## Architect Brief

**Reason:** validate-plan self-heal failed to converge after 3 passes.
**Action required:** Run /io-architect to correct the design, then re-run /io-checkpoint and /validate-plan.

### Persistent Violations

| Pass | Flag | Checkpoint | Component | Attempted Fix | Why It Did Not Resolve |
|------|------|------------|-----------|---------------|------------------------|
| 1    | ...  | ...        | ...       | ...           | ...                    |
| 2    | ...  | ...        | ...       | ...           | ...                    |
| 3    | ...  | ...        | ...       | ...           | ...                    |

### Implied Structural Issue

[One paragraph: what the recurring violation reveals about the design — e.g.,
"CP-03 and CP-04 cannot be merged because they reference components from different
CRC cards with no shared Protocol anchor. The CRC card for ComponentX may need
to be split, or the checkpoint boundary redrawn at /io-checkpoint."]
```

1. Inform the user:

```
VALIDATE-PLAN: 3x self-heal failure. Plan stamped FAIL.

Architect Brief written to plans/plan.md — open the file and read the
## Architect Brief section. Then run /io-architect to correct the design.

Path forward: /io-architect -> /io-checkpoint -> /validate-plan
```

Do NOT offer to re-run `/validate-plan`. The loop cannot converge without a design change.

---

### Step 13: STAMP RESULT

**Severity Guide:**

* **VIOLATION:** Blocks orchestration. Must be resolved (auto or manual) before proceeding.
* **OBSERVATION:** Should fix. Orchestration may proceed but risk of drift.
* **INFO:** Optional improvement. Does not block.

**Gate Behavior:**

* If all VIOLATIONs are auto-remediable, the agent fixes them and re-validates until no new violations appear.
* If any non-auto-remediable VIOLATION exists, the plan **FAILS** immediately and the user must intervene.
* If the same violation recurs across 3 passes, the plan **FAILS** and an Architect Brief is written to `plans/plan.md`. Path forward: `/io-architect` → `/io-checkpoint` → `/validate-plan`.
* Only a **PASS** result (zero VIOLATIONs) allows `/io-plan-batch` to proceed.

**Gate Artifact:**

Write the stamp using the following strictly sequential steps. Do NOT parallelize — the sentinel must exist before the Edit tool call fires.

* **Step 13-pre:** `bash: mkdir -p .iocane && touch .iocane/validating`
* **Step 13:** On **PASS**, stamp `plans/plan.md` with: `**Plan Validated:** PASS (YYYY-MM-DD)`. On **FAIL**, stamp `plans/plan.md` with: `**Plan Validated:** FAIL (YYYY-MM-DD)` and list the blocking violations.

The sentinel prevents `reset-on-plan-write.sh` from immediately reverting a PASS stamp back to FAIL. The hook auto-deletes the sentinel when it detects the `**Plan Validated:** PASS` or `**Plan Validated:** FAIL` stamp write — no explicit cleanup step required.

* `/io-plan-batch` **MUST** check for a `**Plan Validated:** PASS` marker before composing the batch. If missing or FAIL, halt and recommend `/validate-plan`.

**Self-Healing Log:**

* All auto-amendments must be logged in `plans/plan.md` under a `## Self-Healing Log` section.
* Each entry: `[AUTO-AMENDED] <iteration> | <flag> | <checkpoint> | <what was changed>`

---

## 2. CONSTRAINTS

* Target artifact is `plans/plan.md` — not any session-specific plan document.
* Files loaded into context are not re-read unless the file has been modified during the current run.
* Auto-amend only the violations classified as auto-remediable above.
* Do not expand scope beyond what `plan.md` proposes.
* Do not route findings to `plans/backlog.md` — this is a pre-orchestration gate, not a post-implementation review.
* Do not execute the plan. Amend and validate only.
* `UNREGISTERED_WRITE_TARGET` findings must route to `/io-architect`, not be auto-amended.
* `MISSING_CONNECTIVITY_TEST` findings must route to `/io-checkpoint` amendment, not be auto-amended.
* Phase 1 context load (Step 2) does not load CRC cards, Protocol files, seams.md, or run extract_structure.py.
* Phase 2 context load (Step 2B) does not re-load anything already in context from Phase 1.
* Self-healing loop re-validates Phase 1 checks only — no Phase 2 context reload per iteration.
* `extract_structure.py` runs only at Step 10, and only for checkpoints that introduce a new collaborator.
