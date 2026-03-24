---
name: io-backlog-triage
description: Assess open backlog items for relevance, risk, and routing. Produces a prioritized suggestion summary for human approval before execution routing.
---

# WORKFLOW: IO-BACKLOG-TRIAGE

**Objective:** Analyze all open `[ ]` items in `plans/backlog.md`, assess whether they
are still relevant, classify their risk, and produce a prioritized routing summary with
explicit prompt templates for each item. Human gates the routing decisions.

**Mode:** Tier 1 — plan mode required for Steps 1–5 (analysis and proposal only). No
writes until Step 6 human approval.

**Position in chain:**

```
post /io-review -> [/io-backlog-triage] -> human approves routing -> /io-architect | /validate-plan | /io-ct-remediate
```

This workflow can also be invoked independently of `/io-review` for periodic triage
(e.g., before a new `/io-plan-batch` cycle). The input section below applies in all cases.

**Input sources (checked in order):**

1. `plans/review-output.md` (staging file) — primary source for new findings from
   `/io-review` and `/gap-analysis`. If the staging file exists and contains
   unprocessed `### From CP-XXX` sections, those findings are the default input.
   The human may specify which sections to process; unprocessed sections remain
   in the staging file for a future triage cycle.
2. All open `[ ]` items from `plans/backlog.md` (each identified by its `**BL-NNN**`
   header) — used for periodic re-triage or when staging is empty.
3. A subset pasted by the human — overrides both sources above.

---

## PROCEDURE

### Step 1 — STATE INITIALIZATION

Load all open `[ ]` items from `plans/backlog.md` (or accept a pasted subset from the human).
Each item is identified by its `**BL-NNN**` header line. Use BL-IDs when referencing
specific items throughout this workflow.

Output a count of open items by tag:

```
Open backlog items:
  [DESIGN]:   N
  [REFACTOR]: N
  [CLEANUP]:  N
  [TEST]:     N
  [DEFERRED]: N
  [OTHER]:    N
  Total:      N
```

If any item has an unrecognized tag (not in the set above), classify it as `[OTHER]` and
flag it for human classification before proceeding:

```
UNRECOGNIZED TAG: "[TAG]" on item "[description]". Assign a known tag before routing.
```

If any `[DESIGN]` or `[REFACTOR]` items are open, flag immediately:

```
WARNING: N orchestration blocker(s) open. /io-plan-batch will halt until resolved.
```

Exclude items that already have a `Routed:` or `Triaged:` annotation from the
blocker count — these are in-flight remediation items, not active blockers.

Items with a `Triaged:` annotation (from a previous triage cycle) should be
listed separately as "Previously triaged — awaiting human action" and skipped
in Steps 2-4 unless the human explicitly includes them.

---

### Step 2 — RELEVANCE SCAN

#### 2a. Deduplication pass

Before scanning relevance, group items by their `Files:` field and function/class name.
If two or more items reference the same file and the same function or class, flag them
as potential duplicates:

```
POTENTIAL DUPLICATES (same file + function):
  - "[item A description]"
  - "[item B description]"
  Recommendation: merge into a single routing action, or confirm they are distinct.
```

Present duplicates in the Step 5 summary for human decision.

#### 2b. Per-item relevance check

For each open item:

1. Read the `Files:` field and the `Detail:` description from the backlog entry.
2. Read the referenced file(s) at the location(s) described. Use targeted reads — do
   not load full files unless necessary.
3. Determine whether the described issue still exists at that location in current code.

**Tag-specific guidance:**

- `[DESIGN]` items reference `interfaces/*.pyi` contracts. The check is whether the
  *contract gap* still exists (e.g., error types not exported, missing method), not
  whether source code has changed. Read the `.pyi` file, not the implementation.
- `[TEST]` items: check whether the referenced test file exists and contains the
  described coverage. Do not execute tests — existence and assertion shape are sufficient.
- `[CLEANUP]` / `[REFACTOR]` items: read the referenced source location.

#### 2c. Inter-item dependency check

Before classifying, check for blocking relationships between open items in the
current triage scope. Two items are in a blocking relationship when:

- They share one or more files in their `Files:` field, AND one item must be
  resolved before the other can be safely implemented (e.g., a `[DESIGN]` item
  that changes a contract must precede a `[CLEANUP]` item that implements
  against that contract on the same file), OR
- One item's `Detail:` explicitly describes a fix that is a prerequisite for
  another item's fix (logical sequencing — e.g., a type annotation fix must
  land before a downstream consumer fix on the same boundary).

For each blocking pair, identify which item is the **blocker** and which is
the **dependent**. Flag the dependent as blocked:

```
BLOCKED ITEM: "[dependent item description]"
  Blocked by: "[blocker item description]"
  Reason: [shared file / logical prerequisite]
  Action: route blocker first; dependent cannot be routed until blocker is
  resolved and its remediation CP is complete.
```

Blocked items are excluded from Steps 3–4 routing. They appear in the Step 5
summary under "Blocked — awaiting resolution" only. Only unblocked items
proceed to risk classification and routing.

#### 2d. Classification

Classify each item as one of:

- `STILL OPEN` — the described issue is present in the current code.
- `PARTIALLY RESOLVED` — part of the described issue has been fixed but a residual gap
  remains. Note what was fixed and what remains. If the remaining gap is small, keep a
  single backlog entry with an updated Detail. If it is a distinct concern, recommend
  splitting into a new backlog entry.
- `LIKELY RESOLVED` — the described issue is not present (code has changed since entry
  was written, or the fix is already in place).
- `CANNOT VERIFY` — the referenced file does not exist, the issue requires test
  execution to confirm, or the description is ambiguous.

---

### Step 3 — RISK CLASSIFICATION

For each item classified `STILL OPEN`, `PARTIALLY RESOLVED`, or `CANNOT VERIFY`, assign
a risk category:

- **Orchestration blocker:** Tag is `[DESIGN]` or `[REFACTOR]` — `/io-plan-batch`
  will halt with a warning until resolved.
- **Destructive if unremediated:** HIGH severity items where failure to fix causes data
  loss, security exposure, or silent correctness failure (e.g. deleting without archiving,
  propagating blank credentials, non-atomic writes under concurrent access).
- **Low urgency:** MEDIUM or LOW items with no blocking or destructive consequence.

---

### Step 4 — ROUTING MAP

For each `STILL OPEN` or `PARTIALLY RESOLVED` item, determine the routing:

| Tag | CP Status | Routing |
|-----|-----------|---------|
| `[DESIGN]` | any | `/io-architect` then `/io-checkpoint` |
| `[REFACTOR]` | any | `/io-architect` (CRC only) then `/io-checkpoint` |
| `[CLEANUP]` | pending | `/validate-plan` -> `/io-plan-batch` -- sub-agent picks it up |
| `[CLEANUP]` | done | `/io-checkpoint` -- remediation checkpoint for completed CP |
| `[TEST]` CT gap | any | `/io-ct-remediate` |
| `[TEST]` unit gap | pending | Human amends CP scope in `plan.md`, then `/validate-plan` |
| `[TEST]` unit gap | done | `/io-checkpoint` -- remediation checkpoint for completed CP |
| Item requiring new CP | any | Flag for human scoping -- no prompt available |

**`[TEST]` disambiguation:** A `[TEST]` item is a **CT gap** if its `Files:` field
references `tests/connectivity/` or if the Detail mentions a connectivity test ID
(CT-NNN). All other `[TEST]` items are **unit gaps**.

**CP status check:** Read `plans/plan.md` to determine whether the parent
checkpoint is `[ ] pending` or `[x] done`. The routing table above uses this
status to select the correct path.

---

### Step 5 — [PLAN MODE] SUGGESTION SUMMARY

Present the following structured summary to the human. Do not write any files in this step.

```
## Backlog Triage Summary

### Potential Duplicates
For each group of items flagged in Step 2a:
- Items: "BL-NNN [item A]", "BL-NNN [item B]"
  Recommendation: [merge / keep separate]

### Likely Resolved (verify and close)
For each LIKELY RESOLVED item:
- BL-NNN [item description] -- [reason the issue appears resolved]
  Action: confirm manually by reading the referenced file, then mark [x] in backlog.md.

### Partially Resolved
For each PARTIALLY RESOLVED item:
- [item description]
  Fixed: [what was resolved]
  Remaining: [what gap persists]
  Action: [update Detail in backlog.md | split into new entry] then route as STILL OPEN.

### Blocked — awaiting resolution
For each item excluded in Step 2c:
- BL-NNN [TAG] [short description]
  Blocked by: BL-NNN [blocker item description]
  Reason: [shared file / logical prerequisite]
  Action: route blocker first; re-triage this item after blocker's remediation
  CP is complete.

### Route Immediately
For each STILL OPEN item with a clear routing (unblocked items only):

- BL-NNN [TAG] [short description]
  Risk: [Orchestration blocker | Destructive | Low urgency]
  Prompt: `[exact command to run]`
  Context to provide: "[any context the downstream workflow needs to begin]"

(See REFERENCE: Routing Examples at the end of this document for format examples.)

### Remediation Routing (done CPs — via /io-checkpoint)
For each completed CP with STILL OPEN items:

**Items requiring design gate first (DESIGN/REFACTOR -> CLEANUP):**
- BL-NNN [CLEANUP] [short description] (was [ORIGINAL TAG])
  Step 1: `/io-architect` — [context: what contract/CRC change is needed]
  Step 2: `/io-checkpoint` — [context: remediation CP scope, write targets,
  gate inherited from parent CP, Source BL: BL-NNN]

**Items routable directly (CLEANUP/TEST on done CP):**
- BL-NNN [TAG] [short description]
  Prompt: `/io-checkpoint`
  Context: "Remediation checkpoint for CP-NN. Source BL: BL-NNN. Scope: [backlog item description].
  Write targets: [Files from backlog item]. Gate: inherited from CP-NN."

### Requires Human Scoping (no prompt available -- plan.md amendment needed first)
For each item that requires a new checkpoint or amendment to an existing checkpoint:
- [item description]
  Guidance: Add [test file / implementation file] to write targets for CP-XX (or add a
  new checkpoint), then run `/validate-plan`.

### Orchestration Blockers (resolve before next /io-plan-batch)
List of [DESIGN] and [REFACTOR] items with routing prompt, if not already listed above.

### Destructive Risk (HIGH -- prioritize)
List of HIGH severity items with routing prompt, if not already listed above.

### CANNOT VERIFY items
List items that could not be assessed, with the reason.
```

---

### Step 6 — [HUMAN GATE] APPROVE ROUTING

The human reviews the summary and for each item:

- **Approves routing:** triage workflow outputs the final routing directive for that item
  (the exact prompt to run next).
- **Corrects routing:** triage workflow updates the suggestion and re-presents.
- **Defers item:** triage workflow appends a `[DEFERRED]` tag and reason note to the
  item in `plans/backlog.md`.
- **Acknowledges (no action):** item stays open with no tag change. Use this when the
  item is valid but not ready to route — distinct from `[DEFERRED]`, which implies an
  active postponement decision with a stated reason.
- **Confirms likely-resolved:** triage workflow changes `[ ]` to `[x]` in
  `plans/backlog.md` with a brief resolution note.
- **Approves routing (done CP):** For items on completed checkpoints, triage:
  (a) Writes routing prompts as annotations on the backlog item — the full
  playbook the human needs to execute (see Step 5 format). The routing prompts
  persist in `plans/backlog.md` so the human can return to them later without
  re-running triage. Use this annotation format for the `Routed:` field:

      - Routed:
        - Step 1: '/io-architect [context]'
        - Step 2: '/io-checkpoint [context]'

  The entire prompt including context MUST be wrapped in single quotes so it
  is copy-pasteable directly from the markdown file. Do NOT use backticks or
  double quotes.
  (b) **Atomic splitting** for items with non-None `Contract impact` (from
  `plans/review-output.md` staging format): instead of re-tagging a single
  item, produce separate atomic BL items:
    - A `[DESIGN]` item with `/io-architect` routing prompt for the contract
      change. Tags are permanent — no re-tagging.
    - One or more `[CLEANUP]`/`[TEST]` items with `/io-checkpoint` routing
      prompts for the implementation work. Each gets a `Blocked: BL-NNN`
      annotation referencing the `[DESIGN]` item, so they cannot be routed
      until the design gate clears.
  For items with `Contract impact: None`, write routing prompts directly
  as before (no splitting needed).
  (c) For items from `plans/review-output.md` that have NO contract impact
  and are tagged `[CLEANUP]` or `[TEST]`, write a single-step routing prompt:

      - Routed: CP-NNRN (YYYY-MM-DD)
        - '/io-checkpoint [context]'

After processing all items, output an audit table summarizing every decision:

```
## Triage Decisions

| # | Item | Classification | Human Decision | Tag Change | Action Taken |
|---|------|----------------|----------------|------------|--------------|
| 1 | [CLEANUP] description | STILL OPEN | APPROVE | [REFACTOR]->[CLEANUP] | Routing prompts written |
| 2 | [CLEANUP] description | STILL OPEN | APPROVE | -- | Routing prompt written |
```

**The triage workflow TERMINATES after Step 6.** It does not perform any implementation
or invoke any downstream workflow itself. All subsequent execution flows through the
existing harness:

- `/io-ct-remediate` for CT gaps
- `/io-architect` for design changes
- `/validate-plan` → `/io-plan-batch` for cleanup and refactor items
- Manual `plan.md` amendment for items requiring new checkpoint scope

Human triggers each downstream workflow in sequence.

---

### Step 7 — ARCHIVE STAGING FILE

After all items from `plans/review-output.md` have been processed (or the human
confirms partial processing is complete for now):

1. If all `### From CP-XXX` sections in `plans/review-output.md` were processed:
   move the file to `plans/archive/review-output-YYYY-MM-DD-HHMM.md`.
2. If only some sections were processed: remove the processed sections from
   `plans/review-output.md` and archive them to
   `plans/archive/review-output-YYYY-MM-DD-HHMM.md`. Unprocessed sections
   remain in the staging file.

This step is skipped if the input source was `plans/backlog.md` directly
(periodic re-triage mode) or a human-pasted subset.

---

## CONSTRAINTS

- Steps 1-5 are ANALYSIS AND PROPOSAL ONLY. No writes until Step 6 human approval.
- Does NOT modify `plans/plan.md`, any `interfaces/*.pyi`, or any source or test file.
- Writes to `plans/backlog.md` (Step 6: tagging deferred items, closing
  confirmed-resolved items, writing routing prompt annotations, atomic BL items
  from staging).
- Archives processed staging sections from `plans/review-output.md` to
  `plans/archive/` (Step 7).
- Does not execute implementation work, invoke downstream workflows, or run gate commands.
- Relevance scan reads are targeted -- use line bounds or section reads, not full-file loads.
- If the human provides a subset of items rather than the full backlog, scope the analysis
  to only those items.
- **Scope limit:** If more than 15 open items are detected in Step 1, present the tag
  count and ask the human to select a subset or explicitly confirm full-backlog triage
  before proceeding to Step 2. This prevents context exhaustion on large backlogs.

---

## REFERENCE: Routing Examples

These examples illustrate the format for Step 5 "Route Immediately" entries:

```
- BL-012 [TEST] CT-NNN -- ComponentA CP-XX->CP-YY seam
  Risk: Destructive if unremediated (seam unverified)
  Prompt: `/io-ct-remediate CT-NNN`

- BL-015 [CLEANUP] ComponentB docstring out of sync with implementation
  Risk: Low urgency
  Prompt: `/validate-plan`
  Context to provide: "CLEANUP items require no plan.md amendment -- route directly."

- BL-003 [DESIGN] ComponentC error types not exported from Protocol
  Risk: Orchestration blocker
  Prompt: `/io-architect`
  Context to provide: "ErrorTypeX and ErrorTypeY need to be exported from
  interfaces/component_c.pyi. See BL-003."
```
