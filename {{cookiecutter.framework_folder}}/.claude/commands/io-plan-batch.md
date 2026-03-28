---
name: io-plan-batch
description: Compose a dispatch batch from plans/plan.md. Sits between /io-checkpoint and dispatch-agents.sh in the orchestration chain.
---

# /io-plan-batch

## Purpose

Compose a dispatch batch from `plans/plan.md`. Sits between `/io-checkpoint` and `dispatch-agents.sh` in the orchestration chain.

```
/io-checkpoint -> /io-plan-batch -> bash .claude/scripts/dispatch-agents.sh
```

Owns: dependency resolution, parallelization safety, task file generation, confidence scoring, and human approval gate.

Does **not** own: agent dispatch (that is `dispatch-agents.sh`).

---

## Steps

### Step 0 — [HARD GATE] PLAN VALIDATION

Run `bash .claude/scripts/pre-invoke-io-plan-batch.sh`.

If it exits non-zero, HALT immediately with the error message returned by the script. Do not proceed to Step A or any subsequent step.

---

### Step A — Read Configuration

Read `.claude/iocane.config.yaml` and extract `parallel.limit`. This is the maximum number of checkpoints that may be included in a single batch. If the file is missing, default `parallel.limit` to `1` and warn. Create `plans/tasks/` if it does not exist.

### Step B — Identify Unblocked Checkpoints

**B1 — Discover completed checkpoints (cheap):**
Glob `plans/archive/CP-*/CP-*.status` to collect all completed checkpoint IDs. Read each `.status` file (single line) to confirm it is marked PASS. This replaces a full `plan.md` read for status discovery.

**B2 — Discover checkpoint metadata (targeted):**
Grep `plans/plan.md` for `^### CP-` to obtain line numbers for every checkpoint header. For each checkpoint NOT in the completed set from B1, perform a line-bounded read of that checkpoint's section (from its header to the next `---` separator) to extract: dependencies (`Depends on`), write targets, status, and sequence number. Do NOT read sections for completed checkpoints — their data is not needed.

**B3 — Resolve unblocked set:**
From the pending checkpoints read in B2, identify those where all declared dependencies appear in the completed set from B1.

**Remediation gate:** Before producing the candidate list, check whether `plans/plan.md`
contains a `## Remediation Checkpoints` section with any `[ ] pending` entries. If it
does, apply the dependency filter from B1/B2 to those remediation CPs to identify which
are unblocked (all their `Depends on` entries are in the completed set).

- If one or more remediation CPs are unblocked: restrict the candidate list exclusively
  to those unblocked remediation CPs. Roadmap checkpoints are excluded from this batch
  entirely. Remediation items MUST be cleared before the plan advances to roadmap
  checkpoints.
- If all pending remediation CPs are themselves blocked (their dependencies are not yet
  complete): fall through to roadmap candidates as normal. The remediation gate does not
  apply when no remediation CP can actually run.

Produce the candidate list ordered by checkpoint sequence within the selected pool
(remediation or roadmap).

### Step C — Parallelization Safety Check

For each candidate checkpoint, extract declared write targets. Check all pairs in the candidate list for write target overlap. Remove any checkpoint from the candidate list that shares a write target with a higher-priority checkpoint already in the batch.

Beyond write-target overlap, run `symbol_tracer.py --symbol "<Symbol1>,<Symbol2>" --root src/ --imports-only` to detect hidden cross-references between candidate checkpoints' key symbols.

Apply `parallel.limit` cap: take only the first N checkpoints that pass the disjoint check, where N = `parallel.limit`.

### Step D — Generate Draft Task Files (in memory only)

**Context gathering:** Before constructing task files, read `plans/seams.md` once. For each checkpoint in the batch, identify the components in its write targets and extract their seam entries (fields: `Receives (DI)`, `Key failure modes`, `External terminal`). Exclude `Backlog refs` — backlog remediation is a separate workflow concern. Hold this data in memory for embedding below.

For each checkpoint in the confirmed batch, construct the full `CP-XX.md` task file content. Do **not** write to disk at this step. The checkpoint section data needed below was already read (line-bounded) in Step B2 — do not re-read `plan.md` for it.

For connectivity tests (see below), grep `plans/plan.md` for the relevant `CT-` block headers and perform line-bounded reads of only the matching CT sections.

Each task file must include:

- Checkpoint ID and title
- Objective and acceptance criteria (from the checkpoint section read in B2)
- Declared write targets (including CT test file paths — see below)
- Any interface contracts or `.pyi` references
- Self-contained instructions sufficient for an agent to execute without clarification
- A `## Seam Context` section: for each component in this checkpoint's write targets, embed its seam entry from `plans/seams.md` (fields: `Receives (DI)`, `Key failure modes`, `External terminal` only — omit `Backlog refs`). Sub-agents executing this task must not read `plans/seams.md` directly; this section is their only seam reference. If a component has no entry in `plans/seams.md`, note it as "Not yet populated."
- For remediation checkpoints (identified by a `**Remediates:**` field): include a `Source: plans/backlog.md BL-NNN` line in the task file, where `BL-NNN` is read from the `**Source BL:**` field in the checkpoint's `plan.md` section. Sub-agents use this to `grep BL-NNN plans/backlog.md` for targeted context instead of reading the full backlog.
- A `## Connectivity Tests to Keep Green` section: scan `plans/plan.md` for all connectivity tests whose **downstream** checkpoint matches this task's checkpoint ID (i.e., this checkpoint appears on the right side of the arrow in `CT-NNN: CP-XX -> CP-YY`, or on the right side of a multi-source arrow like `CT-NNN: CP-XX + CP-YY -> CP-ZZ`). For each matching CT, include the full CT specification block verbatim from `plan.md` (test_id, function, file, fixture_deps, contract_under_test, assertion, gate). The CT test file path from the `file:` field must also be added to `## Declared Write Targets` so the sub-agent is authorized to create it. If no connectivity tests target this checkpoint as downstream, include the section header with the text "None for this checkpoint."
- A `## Step G` section with the exact status-write command. This must be verbatim — do not paraphrase or substitute a different script path:

```markdown
## Step G — Commit and Write Status

```bash
git add -A
git commit -m "CP-[CP-ID]: [one-line summary]"
bash "$IOCANE_REPO_ROOT/.claude/scripts/write-status.sh" CP-[CP-ID] PASS
```

```

- A `## Step Progress` section with checkboxes for resumable steps B–G (Step A is context-gathering and is never checkboxed):

```markdown
## Step Progress
- [ ] B: Red — write failing test
- [ ] C: Green — write implementation
- [ ] D: Gate command
- [ ] E: Connectivity tests
- [ ] F: Refactor
- [ ] G: Commit and write status
```

### Step E — Score Confidence Rubric

Score the batch against the following criteria:

| Criterion | Description |
|-----------|-------------|
| Dependency correctness | Unblocked checkpoints are genuinely unblocked |
| Parallelization safety | Write targets are genuinely disjoint |
| Task file completeness | Each task file is self-contained and executable |
| Batch size sanity | Batch respects `parallel.limit` and is coherent given project state |

Produce an overall confidence score (0–100%).

If score < 85%: revise the batch composition and re-score. Repeat up to 3 iterations total. If score does not reach 85% after 3 iterations, halt and present the failure reason to the user.

### Step F — Present Batch Summary for Human Approval

Present the following to the user:

```
## /io-plan-batch — Batch Summary

Confidence Score: XX%

Batch composition (N of LIMIT slots used):
- CP-XX: <title> — <brief rationale for inclusion>
- CP-YY: <title> — <brief rationale for inclusion>

Parallelization: [SAFE / SEQUENTIAL — reason]

Excluded checkpoints (and why):
- CP-ZZ: <reason — blocked dependency / write conflict / limit reached>

Task file previews available on request.

---
Accept / Modify / Reject?

- Accept: task files will be written to plans/tasks/. You are then responsible for running bash .claude/scripts/dispatch-agents.sh to dispatch agents.
- Modify: describe changes in natural language. A new /io-plan-batch run will incorporate your modifications.
- Reject: a new /io-plan-batch run will start from scratch.
```

**Do not proceed until the user responds.**

### Step G — Handle Response

**Accept:**
Write all draft task files to `plans/tasks/CP-XX.md`. Confirm each file written. Remind the user to invoke `bash .claude/scripts/dispatch-agents.sh` to dispatch agents.

**Modify:**
Acknowledge the requested modifications. Do not write any task files. Re-run from Step B incorporating the user's natural language modifications as constraints.

**Reject:**
Do not write any task files. Re-run from Step B from scratch.

---

## Output

On acceptance, for each checkpoint in the batch:

- `plans/tasks/CP-XX.md` written to disk

No other files are written or modified by this workflow.

---

## What This Workflow Does Not Do

- Does not dispatch agents
- Does not invoke `dispatch-agents.sh`
- Does not modify `plan.md`
- Does not update `.status` files

---

## Related

- `/io-checkpoint` — upstream; produces `plan.md`
- `/validate-plan` — must pass before this workflow runs
- `bash .claude/scripts/dispatch-agents.sh` — downstream; reads `plans/tasks/` and dispatches agents
- `.claude/iocane.config.yaml` — configuration (parallel limit)
