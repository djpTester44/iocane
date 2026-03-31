# ACTUAL_TARGET_SCOPE: Computability Heuristic

Defines the procedure for determining whether an `ACTUAL_STATE_ASSERTION` finding routes to `/task-recovery` (MECHANICAL) or escalates to the user (DESIGN). The test is: can the full exclusion set be derived deterministically from existing artifacts?

---

## Step 1 — Build the File-to-Checkpoint Map

From `plans/plan.md`, read each checkpoint's declared write targets. Produce a map:

```
file_path -> CP-ID
```

A file absent from every checkpoint's write targets is **unregistered**. Unregistered files cannot be excluded deterministically — any finding involving them is DESIGN.

---

## Step 2 — Compute the Transitive Reachable Set

The reachable set for a given CP-ID is:

1. All files owned by checkpoints archived as PASS (`plans/archive/CP-*/CP-*.status`).
2. All files in the current CP-ID's own write targets.
3. Transitively: files owned by checkpoints in this CP's `Depends on` chain, provided those checkpoints are archived PASS.

Files in the reachable set are at TARGET state from this CP's perspective. Acceptance criteria may assert TARGET state on these.

Files outside the reachable set are at ACTUAL state. Acceptance criteria must not assert TARGET state on these.

---

## Step 3 — Scan Acceptance Criteria

**Explicit paths:** Quoted file paths (`src/path/module.py`, `tests/path/test_module.py`). Map each to the file-to-checkpoint map.

**Broad directory patterns:** Language like "all components pass", "all tests green", "entire src/ directory". These implicitly reference all files in the named scope. Resolve to the registered file list from `plans/component-contracts.toml` for that directory.

**Behavioral assertions:** Criteria phrased as "X behavior works end-to-end". Cross-reference `plans/seams.md` and `component-contracts.toml` to identify implicated files.

---

## Step 4 — Apply the Computability Test

For each file outside the reachable set that an acceptance criterion references:

**Computable → MECHANICAL:** The file appears in `component-contracts.toml` and is owned by a CP-ID resolvable from the file-to-checkpoint map. The exclusion set is fully enumerable from `plan.md` + `component-contracts.toml`.

**Not computable → DESIGN:** Any of the following conditions:
- The file is absent from `component-contracts.toml` (unregistered component).
- The file's owning CP-ID is not reachable from the dependency graph.
- The acceptance criterion uses implicit scope language that cannot be resolved to a finite file list.
- Multiple CPs claim overlapping paths and authority is ambiguous.

If even one file in the exclusion set is not computable, the entire finding is DESIGN.

---

## Step 5 — Construct the MECHANICAL Finding Detail

For MECHANICAL findings, include the computed exclusion set in the validation report:

```yaml
flag: ACTUAL_STATE_ASSERTION
severity: MECHANICAL
routing: task-recovery
detail: "Criterion N asserts TARGET state on files not in CP-XX's reachable set."
exclusions:
  - file: "src/path/module.py"
    owner: "CP-YY"
  - file: "src/path/other.py"
    owner: "CP-ZZ"
```

`/task-recovery` reads these exclusions as negative constraints when regenerating the task file.

---

## Blind Spots

These cases require human judgment and produce DESIGN findings:

1. **Implicit references:** "All integration points are stable" — no finite file list derivable.
2. **Multi-CP files:** A file appears in two checkpoints' write targets (should be caught by `/io-plan-batch` parallelization safety, but may slip through in sequential batches).
3. **Non-component files:** Config files, scripts, templates absent from `component-contracts.toml`.
4. **Remediation CPs:** A remediation CP's scope may intentionally reference files outside the normal dependency graph. Flag as OBSERVATION rather than ACTUAL_STATE_ASSERTION unless the assertion is clearly incorrect.
