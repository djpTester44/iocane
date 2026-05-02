---
name: io-ct-remediate
description: Retroactively create a missing connectivity test file from its CT spec in plan.yaml. Resolves open [TEST] HIGH backlog entries that have no /io-execute path.
---

# WORKFLOW: IO-CT-REMEDIATE

**Objective:** Write a missing connectivity test file from its fully-specified CT spec in
`plans/plan.yaml`. This is the remediation path for MISSING CT backlog entries that cannot
be resolved via `/io-execute` because the checkpoint is archived.

**Mode:** Mechanical execution — NO plan mode. CT spec is fully deterministic; no design
decisions are made here. Human gate triggers only on ambiguity or gate failure.

**Position in chain:**

```
/io-review (MISSING CT -> backlog [TEST]) -> [/io-ct-remediate] -> backlog resolved
```

This workflow is OPTIONAL — only invoked when `/io-review` Step B finds a MISSING CT.

---

## PROCEDURE

### Step 1 — STATE INITIALIZATION

Identify the target CT ID(s):

- If a CT ID argument was provided (e.g. `CT-001`), use it.
- Otherwise: scan `plans/backlog.yaml` for all open `[ ] [TEST]` items that contain a CT ID
  reference. List each found ID.

For each CT ID, output:

- CT ID (e.g. `CT-001`)
- Seam (e.g. `CP-01 → CP-02`)
- File path from the CT spec (`file:` field)
- Linked backlog entry (date and description)

---

### Step 2 — LOAD CT SPEC

Read the CT spec from `plans/plan.yaml` for each target CT ID using plan_parser:

```bash
uv run python -c "
import sys, json
sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan
plan = load_plan('plans/plan.yaml')
ct = next((ct for ct in plan.connectivity_tests if ct.test_id == 'CT-NNN'), None)
if ct: print(json.dumps(ct.model_dump(mode='json', exclude_none=True), indent=2))
else: print('NOT_FOUND')
"
```

The CT file is owned by the `target_cp` checkpoint. This remediation creates the file that the `target_cp`'s sub-agent should have written during `/io-execute` Step E.

Required fields:

- `test_id`
- `function`
- `file`
- `fixture_deps`
- `contract_under_test`
- `assertion`
- `gate`

HALT if any of the following are true:

- The CT spec block is not found in `plans/plan.yaml`.
- Any required field is missing or contains a placeholder (e.g. `# TODO`).
- The `gate` command is not a concrete, runnable pytest invocation.

Do NOT proceed without a fully-specified spec.

---

### Step 3 — LOAD SEAM CONTEXT

Load seams via `seam_parser.load_seams('plans/seams.yaml')` and use `find_by_component()` to read the relevant seam entry for the CP-A -> CP-B boundary named in the CT spec.

[Phase 5+ TODO: `receives_di` was removed from `SeamEntry` in Phase 4 per `decisions.md` D-32 (single canonical DI field is now `injected_contracts`). This check needs redesign -- options: (a) compare against contract names from `injected_contracts` (semantic shift); (b) compute collaborator component names from `component-contracts.yaml.collaborators` (alternate source); (c) retire the check if no longer valuable. Skipped until Phase 5+ designs this command's seam-validation surface.]

---

### Step 4 — WRITE TEST FILE

Read `.claude/skills/test-writer/SKILL.md` and follow it in Track B (Contract-Driven)
mode — CTs are always stateless contracts between two seam sides. Read
`references/track-b-contract.md` for the phase instructions. Use the CT spec's
`contract_under_test`, `assertion`, and `fixture_deps` fields as the Phase 1 contract
extraction input. Execute Phases 2-3 to design test cases and generate code.

Write the test file at the `file:` path from the CT spec.

Requirements:

- Imports from both checkpoint layers — do not mock either side of the seam.
- Fixtures named exactly as listed in `fixture_deps:`.
- Test function named exactly as in `function:`.
- Assertions match the `assertion:` field exactly.
- No I/O performed in the test body — fixtures provide all dependencies inline.
- Create `tests/connectivity/` directory if it does not exist.
- The CT file is a write target of `target_cp` only — do not modify any source CP's task file or write targets.

No worktree isolation — CTs are additive writes with no write-target conflicts.

HALT and surface to human if:

- Any `fixture_deps` name does not correspond to a resolvable fixture or constructible
  object from the imported modules.
- The `assertion:` field is ambiguous or contradictory.

---

### Step 5 — RUN GATE

Run the `gate:` command from the CT spec exactly as written.

- If **FAIL**: report the full failure output. Do NOT mark the backlog item resolved.
  Stop and surface the failure to the human. Do not retry.
- If **PASS**: proceed to Step 6.

---

### Step 6 — RESOLVE BACKLOG

In `plans/backlog.yaml`, find the open `[ ] [TEST]` entry for this CT ID.

- Change `- [ ]` to `- [x]`.
- Append on a new line: `Resolved: CT file written and gate passes (YYYY-MM-DD).`
  (Use today's date.)

---

### Step 7 — STAMP

Output the following:

```
CT REMEDIATION COMPLETE.
CT-[NNN]: PASS -- [file::function]
Backlog item closed.
```

---

## CONSTRAINTS

- Writes ONLY to the `file:` path and `plans/backlog.yaml`. Nothing else.
- Does NOT modify `plans/plan.yaml`, any `interfaces/*.pyi`, or any implementation file.
- Does NOT modify `plans/seams.yaml`.
- HALT and surface to human if the spec is ambiguous, any `fixture_deps` do not exist,
  or the gate command fails.
- This workflow has no self-healing loop. Gate failure = human escalation.
