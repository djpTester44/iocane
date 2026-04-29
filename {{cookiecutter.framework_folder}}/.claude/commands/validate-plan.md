---
name: validate-plan
description: Validate plans/plan.yaml checkpoint structure against CDD principles before orchestration. Pre-entry gate for /io-plan-batch.
---

> **[CRITICAL] CONTEXT LOADING**
> Load the analysis constraints:
> `view_file .claude/rules/planning.md`

# WORKFLOW: VALIDATE-PLAN (CDD Compliance)

**Objective:** Pre-orchestration validation that `plans/plan.yaml` maintains CDD structural integrity — checkpoint atomicity, connectivity test completeness, and write-target registry alignment — before any sub-agent is dispatched.

**Context:**

* Target artifact: `plans/plan.yaml`
* Output: Findings table with actionable recommendations and a PASS/FAIL stamp on `plans/plan.yaml`
* Trigger: Run before `/io-plan-batch` to catch structural violations before task files are generated. Iterate until PASS.

**Position in chain:**

```
/io-checkpoint | /auto-checkpoint -> [/validate-plan] -> /io-plan-batch -> /validate-tasks -> dispatch-agents.sh
```

---

## 1. PROCEDURE

### Step 1: IDENTIFY SCOPE

* Load `plans/plan.yaml` via plan_parser:

  ```bash
  uv run python -c "
  import sys, json
  sys.path.insert(0, '.claude/scripts')
  from plan_parser import load_plan
  plan = load_plan('plans/plan.yaml')
  print(json.dumps({'total_cps': len(plan.checkpoints), 'with_deps': sum(1 for cp in plan.checkpoints if cp.depends_on), 'cts': len(plan.connectivity_tests), 'validated': plan.validated}))
  "
  ```

* Identify all checkpoint entries.
* Count: total checkpoints, checkpoints with `depends_on`, parallelizable pairs, connectivity test signatures defined.

---

### Step 2: PHASE 1 — STRUCTURAL CONTEXT LOAD

Load the following — and only the following — before running Phase 1 checks:

* **`plans/component-contracts.yaml`** — provides file path mappings for write-target verification.
* **`pyproject.toml`** — load the `[tool.importlinter]` section to understand `root_packages` and all `[[tool.importlinter.contracts]]` entries (type `independence` and type `layers`).

If `plans/component-contracts.yaml` does not exist, HALT: "Run `/io-architect` to generate component contracts before validation."

`plans/plan.yaml` is already in context from Step 1.

Do NOT load `plans/seams.yaml` or run `extract_structure.py` here. Those belong to Phase 2.

Files loaded in this step remain in context for all subsequent steps — do not re-read any file already loaded unless it has been modified during this run.

---

### Step 4: CHECK — Private Method Gate [Phase 1]

> **[HARD]** `_`-prefixed methods are internal implementation details.

* If any checkpoint write target or Protocol reference in `plan.yaml` names a `_`-prefixed method as a deliverable, flag immediately.
* **Flag:** `PRIVATE_METHOD_PROMOTION`

---

### Step 7: CHECK — Write Target Registry Alignment [Phase 1]

For every write target listed in every checkpoint:

* Verify the file path appears as a `file` value in `plans/component-contracts.yaml`.
* **Flag:** Write target not in `component-contracts.yaml` = `UNREGISTERED_WRITE_TARGET`

**Exemptions (INFO only, not VIOLATION):**

* `tests/` files — test infrastructure is not an architectural component.
* Non-Python project tooling files outside `src/` (e.g. `pyproject.toml`, `config.toml`, `ui/src/*.ts`).

**Not exempt under any circumstances:**

* Any `.py` file under `src/` — including internal utilities annotated "no contract." A `src/` file absent from `component-contracts.yaml` is always `UNREGISTERED_WRITE_TARGET` (VIOLATION), regardless of prior log precedents or "internal utility" annotations. Route to `/io-architect` for explicit registration or exemption before orchestration.
* Any `.py` file outside `src/` and `tests/`. Runtime Python modules must live under `src/`. Flag as `MISPLACED_RUNTIME_MODULE` (VIOLATION).

---

### Step 8: CHECK — Layer Boundary Compliance [Phase 1]

Using the contracts loaded in Step 2 (`pyproject.toml`):

* Verify that all write targets respect layer and independence contracts.
* **Flag:** Plan proposes a write target that would introduce a lower-to-higher import = `LAYER_VIOLATION`
* **Flag:** Plan proposes a write target that would introduce a cross-peer import in an independence contract = `INDEPENDENCE_VIOLATION`

---

### Step 9: CHECK — Connectivity Test Completeness [Phase 1]

Run the CT completeness check:

    uv run python .claude/scripts/check_ct_completeness.py

* **Flag:** `MISSING_CONNECTIVITY_TEST` — checkpoint has `src/` write targets and `depends_on` edge(s) but touches Protocol seam(s) with no covering CT.
* **Flag:** `PLACEHOLDER_GATE` — connectivity test exists but gate command is a placeholder (manual check: scan for `# TODO` in CT gate fields).

The script handles two exemptions internally:
1. **Verification-only:** CPs with no `src/` write targets (INFO, not VIOLATION).
2. **Covered seams:** CPs whose scope components are all covered by existing CTs (INFO, not VIOLATION). This subsumes remediation CPs that patch the same component as their parent.

---

### Step 9B: CHECK — CT Dependency Invariant [Phase 1]

Run the CT dependency invariant check:

```bash
uv run python .claude/scripts/check_ct_depends_on.py
```

For every connectivity test in `plan.yaml`, the `target_cp`'s `depends_on` list must include all CPs listed in `source_cps`. A missing dependency means the target checkpoint could be scheduled before its source completes.

* **Flag:** `CT_DEPENDS_ON_GAP` — target checkpoint missing dependency on a source checkpoint referenced by a connectivity test. Severity: VIOLATION (non-auto-remediable). The dependency graph must be fixed in plan.yaml before proceeding.

---

### Step 9C: CHECK — CT Assertion Behavior Keywords [Phase 1]

Run the soft lexical validator on every `ConnectivityTest.assertion`:

```bash
uv run python .claude/scripts/validate_ct_assertions.py
```

For every CT, the validator checks the assertion string (case-insensitive substring match) for at least one keyword from each of the three behavior-observable sets required by Step D of `/io-checkpoint`:

* **call binding:** called, invoke/invoked/invokes, with argument, passes, passed to
* **cardinality:** once, exactly, per, times, each, for every
* **error propagation:** raises, propagates, re-raises, error, exception

Surface the script's stderr output verbatim in the findings report. Each `WARN:` line names a CT whose assertion lacks keywords for one or more of the observables.

* **Flag:** `CT_ASSERTION_KEYWORDS` — CT assertion missing behavior-observable keywords. Severity: OBSERVATION (non-blocking). Does not cause Phase 1 to halt, but is listed in the Step 11 findings table and must be acknowledged by the human reviewer.

The script exits 0 regardless of findings. Absence of `WARN:` lines means every CT assertion covers all three observables.

---

### Step 9D: CHECK — Path Reference Resolvability [Phase 1]

Run the Appendix A §A.6 file-reference resolvability gate:

```bash
uv run python .claude/scripts/validate_path_refs.py --stage validate-plan
```

For every path reference extracted from spec artifacts (PRD, roadmap, project-spec, component-contracts, seams, plan.yaml), the script verifies the path resolves to one of:

* (a) an existing file on disk,
* (b) a CP `write_target` in `plans/plan.yaml`, or
* (c) a CP's `relies_on_existing` entry.

Surface the script's stderr output verbatim in the findings report. Each `WARN:` line names the source artifact, the line number, and the unresolved path.

* **Flag:** `UNRESOLVED_PATH_REF` — path reference in a spec artifact does not resolve to filesystem, a CP `write_target`, or a CP's `relies_on_existing` declaration. Severity: OBSERVATION (non-blocking). Same channel as `CT_ASSERTION_KEYWORDS` (Step 9C). Does not block Phase 1 or gate passage, but is listed in the Step 11 findings table for human review.

The script exits 0 regardless of findings. Absence of `WARN:` lines means every extracted path resolves.

---

### Step 9E: CHECK — Plan-Wide Raises Coverage [Phase 1]

Run the Appendix A §A.4d plan-wide Raises coverage check:

```bash
uv run python .claude/scripts/validate_plan_raises_coverage.py
```

For every `Raises:` declaration in every `interfaces/*.pyi` Protocol method, the script checks whether the exception class name appears in at least one `connectivity_tests[*].assertion` in `plans/plan.yaml`. This is the plan-wide tightening noted in A.4d: A.4a-c only require coverage on the source side of a declared DI seam, which misses exceptions raised inside a component rather than propagated across a seam.

Surface the script's stderr output verbatim in the findings report. Each `WARN:` line names the Protocol, method, and uncovered exception type.

* **Flag:** `RAISES_ASSERTION_UNCOVERED` — Protocol `Raises:` declaration not named in any CT assertion. Severity: OBSERVATION (non-blocking). Same channel as `CT_ASSERTION_KEYWORDS` (9C) and `UNRESOLVED_PATH_REF` (9D). Does not block Phase 1 or gate passage, but is listed in the Step 11 findings table for human review. Distinct from the Step 5 Phase 2 `RAISES_UNCOVERED` check, which verifies coverage in per-CP acceptance criteria -- 9E validates that the seam surface itself (CT assertions) names each exception.

The script exits 0 regardless of findings.

---

### [PHASE 1 HALT GATE]

After running Steps 4, 7, 8, 9, 9B, 9C, 9D, and 9E:

* If any Phase 1 check produced a **non-auto-remediable VIOLATION**: HALT immediately. Do not load Phase 2 context. Output findings and escalate to user.
* If all Phase 1 violations are auto-remediable: apply auto-fixes, mark `[AUTO-AMENDED]`, and re-run Steps 4, 7, 8, 9, 9B only (no Phase 2 reload per self-heal iteration). Steps 9C, 9D, and 9E always emit OBSERVATION-severity findings -- never VIOLATION -- so they do not participate in the self-heal loop.
* Only when Phase 1 is clean (zero Phase 1 VIOLATIONs): proceed to Phase 2.

> **Note on symbol coverage:** these checks live at `/io-architect` Step G, NOT here. The architect is the authority that can act on a coverage failure cheaply (just amend the artifact being held in mind); re-checking here would only halt-and-route back to architect, which is the same round-trip the architect already closed. The reset-hook chain forces re-architect on any post-blessing mutation to `symbols.yaml`, so by the time `/validate-plan` runs the architect's coverage stamp is current.

---

### Step 2B: PHASE 2 — BEHAVIORAL CONTEXT LOAD

Load the following before running Phase 2 checks:

* **`plans/seams.yaml`** -- load now via `seam_parser.load_seams('plans/seams.yaml')`, not earlier. Steps 4, 7, 8, 9 do not require seam data.

Do NOT run `extract_structure.py` here. It runs at Step 10 only, scoped to checkpoints with new collaborators.

---

### Step 6: CHECK — Checkpoint Atomicity [Phase 2 — requires seams context loaded above]

* Each checkpoint must reference a single component contract, or if multi-component, the components must be explicitly named.
* Component contract changes for the same component must appear in the same checkpoint, not split across multiple.
* **Flag:** Component contract changes for the same component in separate ungrouped checkpoints = `ATOMICITY_VIOLATION`

---

### Step 10: CHECK — DI Compliance Preview [Phase 2 — requires seams context loaded above]

`plans/seams.yaml` is already in context from Step 2B (loaded via `seam_parser.load_seams()`).

If any checkpoint introduces a new collaborator:

* Run `python extract_structure.py <file>` **only for checkpoints that introduce a new collaborator** -- do not run it for all implementation files. Load structural skeletons (signatures, decorators, docstrings) into context for those files only.
* Verify the task description specifies injection via `__init__` parameter, not inline instantiation.
* Use `find_by_component()` to locate the receiving component's seam entry and cross-reference the collaborator name against its `receives_di` list. If the collaborator is absent, flag `HARDCODED_DEPENDENCY` -- the collaborator is either undeclared or being wired outside the approved DI contract.
* **Flag:** New collaborator described as instantiated inline = `HARDCODED_DEPENDENCY`
* **Flag:** New collaborator not present in the component's `receives_di` entry in `plans/seams.yaml` = `HARDCODED_DEPENDENCY`
* **Flag:** `os.environ` / `os.getenv` described outside Entrypoint layer = `ENV_LEAK`

---

### Step 11: OUTPUT FINDINGS

Generate a Plan Validation report:

* **Summary:** One-paragraph assessment (PASS / FAIL with violation count).
* **Findings Table:**

| # | Check | Checkpoint | Component | Finding | Severity | Auto-Remediable? |
|---|-------|------------|-----------|---------|----------|-----------------|
| 1 | Checkpoint Atomicity | CP-NN | ... | ... | VIOLATION | Yes/No |

* **Required Amendments:** Specific changes to `plan.yaml` (as checkboxes).

---

### Step 12: SELF-HEALING LOOP

**Auto-Remediable Violations** (agent amends `plan.yaml` directly):

| Flag | Auto-Fix Action |
|---|---|
| `PRIVATE_METHOD_PROMOTION` | Remove the `_`-prefixed method reference from the checkpoint section. |
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
| `MISPLACED_RUNTIME_MODULE` | Architectural placement error -- the correct `src/` destination requires design judgment. Route to `/io-checkpoint`. |

**Loop Procedure:**

1. If all VIOLATIONs are auto-remediable: amend `plan.yaml`, mark each change `[AUTO-AMENDED]`, and re-run **Phase 1 checks only** (Steps 4, 7, 8, 9). Do not reload Phase 2 context on each loop iteration — Phase 2 context remains in context from initial load.
2. If any non-auto-remediable VIOLATION exists: stop immediately and escalate to user with findings.
3. After each pass, compare violation set to previous pass. If no new violations appear, the loop has converged — proceed to Step 13.
4. If the same violation recurs across 3 passes: the violation is structural. Execute the 3x-failure path below.
5. On success: proceed to Step 13.

**3x-Failure Path:**

When a violation has appeared in 3 consecutive passes without being resolved, auto-heal has exhausted its scope. The problem is in the underlying design, not in `plan.yaml` surface edits.

1. Stamp `plans/plan.yaml` with `**Plan Validated:** FAIL` (via Step 13 capability procedure).
2. Append an `## Architect Brief` section to `plans/plan.yaml`:

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
"CP-03 and CP-04 cannot be consolidated because they reference distinct components
from `component-contracts.yaml` with disjoint contract scopes. The component
contracts may need to be split or merged at `/io-architect` to align with the
natural CP boundary, or the CP scope redrawn at `/io-checkpoint` to consolidate
touched components."]
```

1. Inform the user:

```
VALIDATE-PLAN: 3x self-heal failure. Plan stamped FAIL.

Architect Brief written to plans/plan.yaml — open the file and read the
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
* If the same violation recurs across 3 passes, the plan **FAILS** and an Architect Brief is written to `plans/plan.yaml`. Path forward: `/io-architect` → `/io-checkpoint` → `/validate-plan`.
* Only a **PASS** result (zero VIOLATIONs) allows `/io-plan-batch` to proceed.

**Gate Artifact:**

Write the stamp using the following strictly sequential steps. Do NOT parallelize — the capability grant must exist before the Edit tool call fires.

* **Step 13-pre:** `bash: uv run python .claude/scripts/capability.py grant --template validate-plan.13`
* **Step 13:** On **PASS**, stamp `plans/plan.yaml` with `validated: true`, `validated_date`, and `validated_note` via plan_parser:

  ```bash
  uv run python -c "
  import sys
  sys.path.insert(0, '.claude/scripts')
  from plan_parser import load_plan, set_validated, save_plan
  plan = load_plan('plans/plan.yaml')
  plan = set_validated(plan, True, date='YYYY-MM-DD', note='PASS')
  save_plan('plans/plan.yaml', plan)
  "
  ```

  On **FAIL**, stamp with `validated: false` and a note listing blocking violations.

* **Step 13-post:** `bash: uv run python .claude/scripts/capability.py revoke --template validate-plan.13`

The capability grant prevents `reset-on-plan-write.sh` from reverting the PASS stamp. Explicit revoke at Step 13-post is required so the grant does not persist across the gate boundary (the 24h hard TTL ceiling and session-end sweep are crash-safety floors, not substitutes for explicit revoke).

* `/io-plan-batch` **MUST** check for `validated: true` before composing the batch. If missing or false, halt and recommend `/validate-plan`.

**Self-Healing Log:**

* All auto-amendments must be logged in `plans/plan.yaml` under the `self_healing_log` list.
* Each entry is a structured object: `{tag: "AUTO-AMENDED", iteration: N, flag: "<flag>", checkpoint: "<CP-ID>", description: "<what was changed>"}`. Use `save_plan` to persist.

---

## 2. CONSTRAINTS

* Target artifact is `plans/plan.yaml` — not any session-specific plan document.
* Files loaded into context are not re-read unless the file has been modified during the current run.
* Auto-amend only the violations classified as auto-remediable above.
* Do not expand scope beyond what `plan.yaml` proposes.
* Do not route findings to `plans/backlog.yaml` — this is a pre-orchestration gate, not a post-implementation review.
* Do not execute the plan. Amend and validate only.
* `UNREGISTERED_WRITE_TARGET` findings must route to `/io-architect`, not be auto-amended.
* `MISSING_CONNECTIVITY_TEST` findings must route to `/io-checkpoint` amendment, not be auto-amended.
* Phase 1 context load (Step 2) does not load `seams.yaml` or run `extract_structure.py`.
* Phase 2 context load (Step 2B) does not re-load anything already in context from Phase 1.
* Self-healing loop re-validates Phase 1 checks only — no Phase 2 context reload per iteration.
* `extract_structure.py` runs only at Step 10, and only for checkpoints that introduce a new collaborator.
* **Plan-layer `component-contracts.yaml` method coverage** (every method covered by at least one CP scope) is NOT YET CHECKED. Pending Plan B authoring of `validate_plan_contract_coverage.py` (see `plans/v4-meso-pivot/plan-B-decisions.md` D-03). Until that lands, plan-layer method-coverage is enforced only by `/io-checkpoint`'s authoring discipline.
