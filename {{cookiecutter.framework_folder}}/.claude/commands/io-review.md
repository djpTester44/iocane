---
name: io-review
description: Per-checkpoint behavioral review and connectivity verification. Findings route to backlog.yaml.
---

> **[NO PLAN MODE]**
> Read-only analysis. No file writes except `plans/seams.yaml` (Step F),
> `src/*/CLAUDE.md` (Step F-post, generated artifacts),
> `plans/review-output.yaml` (via `stage_review_findings.py` at the end),
> and `.iocane/review-pending.json` (Step I).

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load the component registry: `view_file plans/component-contracts.yaml`
> 3. Load the checkpoint being reviewed from `plans/plan.yaml`
> 4. Load CRC cards for checkpoint components from `plans/project-spec.md`
> 5. Load relevant Protocol contracts from `interfaces/*.pyi`
> 6. Load the Integration Seams reference via `seam_parser.load_seams('plans/seams.yaml')`
> 7. Load the task file: `view_file plans/tasks/[CP-ID].yaml` -- check for `execution_findings` and `evaluator_result` fields

# WORKFLOW: REVIEW

**Objective:** Verify that a completed checkpoint's implementation matches its CRC behavioral contract and that all connectivity tests at its seams are green.

**Scope:** Single checkpoint. Do not review components outside the current checkpoint's boundaries.

**Position in chain:**

```
(sub-agents complete) -> [/io-review] -> dispatch-agents.sh (next batch) | /gap-analysis (full system)
```

---

## 1. STATE INITIALIZATION

Before proceeding, output:

- **Checkpoint under review:** [CP-ID and name]
- **Components in scope:** [list from plan.yaml]
- **Protocols in scope:** [list from plan.yaml]
- **Gate command status:** [PASS / FAIL — run gate command to verify]
- **Connectivity tests in scope:** [list CT-IDs at this checkpoint's seams]

---

## 2. PROCEDURE

### Step A: GATE VERIFICATION

- **Action:** Run the checkpoint's gate command from `plans/plan.yaml`.
- **Rule:** If gate is not passing, the checkpoint is not complete. Stop.
- **Output:** "GATE: [PASS/FAIL] — [gate command]"

---

### Step B: CONNECTIVITY TEST VERIFICATION

- **Action:** For each connectivity test in `plans/plan.yaml` where this checkpoint is the `target_cp`:
  1. Check whether the CT test file exists on disk at the `file:` path in the CT spec.
  2. If it exists: run the gate command and report PASS or FAIL.
  3. If it does **not** exist: report as `MISSING`. A missing CT file is a HIGH-severity finding — the `target_cp` sub-agent failed to create it during `/io-execute` Step E. Record in the findings report and route to backlog.
- **Rule:** Every connectivity test must be green (and present) before this checkpoint is considered approved.
- **Output:** For each CT: `CT-[NNN]: [PASS/FAIL/MISSING] -- [test file::function]`

---

### Step B2: EXECUTION FINDINGS AND EVAL TRIAGE

- **Action:** Check whether the task file (`plans/tasks/[CP-ID].yaml`) contains
  an `execution_findings` field.
- **If present:**
  1. For each finding row, assess:
     - Is the observation accurate? (Spot-check the adjacent file.)
     - Did the agent work around the issue appropriately?
     - Does this warrant a backlog entry?
  2. Classify each as:
     - `CONFIRMED` -- real issue, route to backlog via Step I
     - `WORKAROUND_OK` -- agent handled it acceptably, note but no action
     - `FALSE_POSITIVE` -- agent misidentified, discard
  3. `CONFIRMED` findings become MEDIUM-severity entries in Step H with tag `[ADJACENT]`.
- **If absent:** No execution findings. Proceed.

- **Action:** Check whether `plans/tasks/[CP-ID].eval.json` exists.
- **If verdict is `EVAL_SKIPPED`:** The automated evaluator did not run (crash or timeout).
  Apply extra scrutiny in Steps D-G. Note in Step H findings: "Automated evaluator skipped -- manual review substituted."
- **If verdict is `PASS`:** Note eval passed. Proceed normally.
- **If eval.json absent:** Checkpoint predates evaluator pipeline. Proceed normally.

---

### Step C: LOAD BEHAVIORAL ANCHORS

- **Action:** Read the CRC card for each component in scope from `plans/project-spec.md`.
- **Action:** Read the Protocol contract for each component from `interfaces/*.pyi`.
- **Goal:** Establish the behavioral intent before reading implementation.

---

### Step D: STRUCTURAL PRE-SCAN

For each implementation file in the checkpoint's write targets:

- Run `uv run python .claude/scripts/extract_structure.py <file>` — map public surface area
- Run `bash .claude/scripts/run-compliance.sh <write_targets>` — ruff, mypy, lint-imports, bandit, DI check
- Invoke `/symbol-tracer` with `--summary` on the checkpoint's Protocol symbols — verify Protocol is consumed
- **Registry check:** For each write target under `src/`, verify the file path (or its parent component) appears in `plans/component-contracts.yaml` as a top-level component key. A `src/` file whose component is absent from the YAML registry is a HIGH finding: `UNREGISTERED_WRITE_TARGET` — route to `/io-architect` before the checkpoint can be considered approved. `tests/` files and tooling files outside `src/` are exempt.
- **[HARD] Location check:** For each write target that is a `.py` file, verify it resides under `src/` or `tests/`. A `.py` file outside these directories is a HIGH finding: `MISPLACED_RUNTIME_MODULE`. The `interfaces/` directory must contain only `.pyi` stub files; any `.py` file there is a violation. Record in findings and route to backlog -- do not defer to Step E.

Flag any violations. Do not fix — record for findings.

---

### Step E: BEHAVIORAL REVIEW

For each component in scope, verify:

- **CRC Responsibilities:** Does the implementation fulfill every responsibility listed in the CRC card? Flag any responsibility with no corresponding implementation.
- **CRC Must-Nots:** Does the implementation violate any explicit constraint in the CRC card?
- **Protocol compliance:** Does every public method match its Protocol signature exactly? Flag any signature deviation.
- **Protocol Raises coverage:** For each Protocol method in scope, verify that every `Raises:` declaration in the `.pyi` docstring has a corresponding `pytest.raises()` call in the test file. The compliance script `check_raises_coverage.py` (run via `run-compliance.sh`) performs this check mechanically. Flag any uncovered raises path as a finding.
- **Collaborators:** Are all collaborators received via `__init__`? Flag any that are instantiated internally.
- **Sequence diagrams:** If a sequence diagram exists in `project-spec.md` for this component's flows, does the implementation follow it?
- **Side effects:** Are there any observable side effects not described in the CRC?

---

### Step F: SEAMS SYNC

For each component in scope, load seams via `seam_parser.load_seams('plans/seams.yaml')` and use `find_by_component()` to locate the entry. Compare the actual `__init__` signature in `src/` against the seam entry.

**Check each field for drift:**

- **receives_di:** Compare `__init__` parameters against the `receives_di` field. Flag any parameter added, removed, renamed, or re-typed since the last `/io-architect` run.
- **external_terminal:** Scan the implementation for direct client instantiation (e.g., `httpx.AsyncClient()`, `boto3.client()`, `create_async_engine()`) that is not reflected in the `external_terminal` field.
- **key_failure_modes:** Compare raised exception types in the implementation against the `key_failure_modes` field. Flag any new exception type not listed, or any listed exception no longer raised.

**Actions:**

- If drift is detected: use `seam_parser.update_component()` to update `plans/seams.yaml` for each affected component, then `save_seams()`. Record each change as a LOW-severity finding in Step H ("Seams drift -- updated `plans/seams.yaml`").
- If a component in scope has no entry in `plans/seams.yaml` at all: use `seam_parser.add_component()` to create the entry. Record as MEDIUM-severity ("Missing seam entry -- created in `plans/seams.yaml`").
- Do **not** modify the `backlog_refs` field -- that is populated by `/io-backlog-triage` during drain.
- Do **not** update seam entries for components outside the current checkpoint's scope.

---

### Step F-post: REGENERATE NAVIGATION ARTIFACTS

After seams sync, regenerate directory CLAUDE.md files for directories
containing the checkpoint's components:

```bash
uv run python .claude/scripts/sync_dir_claude.py --dir src/[directory]
```

Run once per distinct `src/` subdirectory in the checkpoint's write targets.

**Rule:** If the script exits with code 2 (line count exceeded), record as a
MEDIUM-severity [DESIGN] finding in Step H.

---

### Step G: CORRECTNESS REVIEW

- Logic errors, edge cases not covered by tests
- Error handling — are failure modes handled or silently swallowed?
- Type correctness beyond what mypy catches (semantic type misuse)
- Test quality — do tests assert meaningful behavior, or just "does not raise"?

---

### Step H: OUTPUT FINDINGS

Generate a findings report:

```markdown
## Review: [CP-ID] — [Checkpoint Name]

### Summary
[One paragraph overall assessment]

### Gate Status
- Gate: PASS/FAIL
- Connectivity tests: [N/N passing]

### Findings

**Tag assignment (from `.claude/rules/ticket-taxonomy.md`):**

Each finding gets one tag. Decision gate:

1. Does this require a new or updated `.pyi` contract? -> [DESIGN]
2. Does this require a CRC update (but no `.pyi` change)? -> [REFACTOR]
3. Is this a missing or inadequate test? -> [TEST]
4. Otherwise (implementation fix, spec already correct) -> [CLEANUP]

| Severity | Tag | Location | Issue | Recommendation |
|----------|-----|----------|-------|----------------|
| HIGH | [TAG] | `src/[path]:[line]` | [issue] | [fix] |
| MEDIUM | [TAG] | ... | ... | ... |

### Strengths
- [What was done well]

### Action Items
- [ ] [Specific fix needed]
```

**Severity guide:**

- HIGH: Unanchored behavior (contradicts CRC), broken connectivity test, DI violation, layer violation
- MEDIUM: Should fix -- affects maintainability or contract completeness
- ADJACENT (MEDIUM): Bug or gap in code outside checkpoint scope, reported by execution agent
- LOW: Nice to fix -- minor improvement
- INFO: Observation only

---

### Step I: ROUTE FINDINGS

- **Action:** Write all HIGH and MEDIUM findings from Step H as structured YAML to a temp file, then invoke the staging script:

  **Temp file schema** (write to `/tmp/review-findings-[CP-ID].yaml`):

  ```yaml
  source: "[CP-ID]"
  date: "[YYYY-MM-DD]"
  items:
    - tag: "[TAG from Step H]"
      severity: "HIGH"
      component: "[ComponentName]"
      files:
        - "[repo-relative path]"
      issue: "[one-line description]"
      detail: "[implementation guidance]"
      contract_impact: null  # or description of CRC/Protocol change needed
  ```

  **Invoke:**

  ```bash
  uv run python .claude/scripts/stage_review_findings.py --input /tmp/review-findings-[CP-ID].yaml
  ```

- **Rule:** Findings not captured in staging are invisible to subsequent workflows. This step is mandatory if any HIGH or MEDIUM findings exist. Findings flow from staging to `plans/backlog.yaml` via `/io-backlog-triage`.
- **Rule:** The script validates tags against `BacklogTag` and exits non-zero on invalid input. If the script fails, fix the YAML and re-run before proceeding.
- **Action (mechanical):** After findings are routed, write the review-pending sentinel:
  ```bash
  printf '{"cp_ids":[%s],"timestamp":"%s","trigger":"io-review Step I complete"}\n' \
    "$(echo '[CP-IDs]' | sed 's/ /","/g; s/^/"/; s/$/"/')" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > .iocane/review-pending.json
  ```
- **Rule:** This sentinel marks "reviewed but not yet approved." It persists across session boundaries. `archive-approved.sh` removes it after archival. If present at session start, the briefing surfaces the pending approval gate.

---

### Step J: REVIEW COMPLETE — FINDING ROUTING

Completion is already registered in `plan.yaml` by `dispatch-agents.sh` at merge time. This step routes review findings and cleans up task artifacts.

**Single CP — present to the human:**

```
REVIEW COMPLETE: [CP-ID]

Findings: [N HIGH], [N MEDIUM], [N LOW]
Staged: [N findings routed to staging by Step I -- drains via /io-backlog-triage]

Options:
1. Archive task artifacts and proceed
2. Escalate to /io-architect -- finding reveals a design gap
```

**Batch (multiple CPs from completed wave) — present to the human:**

```
REVIEW COMPLETE: Wave [N]

| CP    | HIGH | MEDIUM | LOW | Staged |
|-------|------|--------|-----|--------|
| CP-XX | 0    | 2      | 1   | 2      |
| CP-YY | 0    | 0      | 1   | 0      |
| CP-ZZ | 0    | 0      | 0   | 0      |

Staged findings drain via /io-backlog-triage.

Recommended:
- Archive task artifacts: bash .claude/scripts/archive-approved.sh [all CP-IDs]
- Escalate [CPs with design gaps] to /io-architect
```

- **Human decides.** Do not auto-approve.
- **If option 1 selected (or batch archive recommended):** Run `bash .claude/scripts/archive-approved.sh [CP-ID ...]` -- this moves task artifacts to `plans/archive/[CP-ID]/`, and for remediation checkpoints automatically marks all corresponding backlog items as `[x]` with a `Remediated:` annotation.
- **Note:** `archive-approved.sh` removes `.iocane/review-pending.json` on invocation. No manual cleanup needed.
- **If option 2 selected:** Escalate to `/io-architect` for design-level resolution.

Archiving and backlog triage are independent operations. `archive-approved.sh` moves task artifacts; `/io-backlog-triage` drains staged findings to `plans/backlog.yaml`. Neither blocks the other. The "is this worth tracking?" judgment belongs to `/io-backlog-triage`, not this step.

---

## 3. CONSTRAINTS

- Scope is strictly limited to the current checkpoint's components
- Do not review components from other checkpoints even if they appear in the same files
- Do not make fixes -- output findings only (exception: `plans/seams.yaml` is updated in Step F to stay in sync with implementation)
- Do not route findings to `plans/plan.yaml` — backlog goes to `plans/backlog.yaml` only
- No git operations
