---
description: Assess open backlog items for relevance, risk, and routing. Produces a
             prioritized suggestion summary for human approval before execution routing.
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

**Input:** All open `[ ]` items from `plans/backlog.md`, OR a subset pasted by the human.

---

## PROCEDURE

### Step 1 — STATE INITIALIZATION

Load all open `[ ]` items from `plans/backlog.md` (or accept a pasted subset from the human).

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

#### 2c. Classification

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

| Tag | Routing |
|-----|---------|
| `[DESIGN]` | `/io-architect` — contract changes require design review |
| `[REFACTOR]` | `/io-architect` (CRC only) then `/validate-plan` |
| `[CLEANUP]` | `/validate-plan` -> `/io-plan-batch` — no contract change |
| `[TEST]` CT gap | `/io-ct-remediate` |
| `[TEST]` unit gap | Human amends a checkpoint in `plan.md`, then `/validate-plan` |
| Item requiring a new checkpoint | Flag for human scoping decision — no prompt available |

**`[TEST]` disambiguation:** A `[TEST]` item is a **CT gap** if its `Files:` field
references `tests/connectivity/` or if the Detail mentions a connectivity test ID
(CT-NNN). All other `[TEST]` items are **unit gaps**.

---

### Step 5 — [PLAN MODE] SUGGESTION SUMMARY

Present the following structured summary to the human. Do not write any files in this step.

```
## Backlog Triage Summary

### Potential Duplicates
For each group of items flagged in Step 2a:
- Items: "[item A]", "[item B]"
  Recommendation: [merge / keep separate]

### Likely Resolved (verify and close)
For each LIKELY RESOLVED item:
- [item description] -- [reason the issue appears resolved]
  Action: confirm manually by reading the referenced file, then mark [x] in backlog.md.

### Partially Resolved
For each PARTIALLY RESOLVED item:
- [item description]
  Fixed: [what was resolved]
  Remaining: [what gap persists]
  Action: [update Detail in backlog.md | split into new entry] then route as STILL OPEN.

### Route Immediately
For each STILL OPEN item with a clear routing:

- [TAG] [ID if applicable] [short description]
  Risk: [Orchestration blocker | Destructive | Low urgency]
  Prompt: `[exact command to run]`
  Context to provide: "[any context the downstream workflow needs to begin]"

(See REFERENCE: Routing Examples at the end of this document for format examples.)

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

After processing all items, output an audit table summarizing every decision:

```
## Triage Decisions

| # | Item | Classification | Human Decision | Action Taken |
|---|------|----------------|----------------|--------------|
| 1 | [TAG] short description | STILL OPEN | APPROVE | Route to /validate-plan |
| 2 | [TAG] short description | LIKELY RESOLVED | CONFIRM | Marked [x] in backlog.md |
| 3 | [TAG] short description | STILL OPEN | DEFER | Tagged [DEFERRED] in backlog.md |
| 4 | [TAG] short description | STILL OPEN | ACKNOWLEDGE | No change — remains open |
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

## CONSTRAINTS

- Steps 1-5 are ANALYSIS AND PROPOSAL ONLY. No writes until Step 6 human approval.
- Does NOT modify `plans/plan.md`, any `interfaces/*.pyi`, or any source or test file.
- Writes ONLY to `plans/backlog.md` (Step 6: tagging deferred items, closing
  confirmed-resolved items).
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
- [TEST] CT-NNN -- ComponentA CP-XX->CP-YY seam
  Risk: Destructive if unremediated (seam unverified)
  Prompt: `/io-ct-remediate CT-NNN`

- [CLEANUP] ComponentB docstring out of sync with implementation
  Risk: Low urgency
  Prompt: `/validate-plan`
  Context to provide: "CLEANUP items require no plan.md amendment -- route directly."

- [DESIGN] ComponentC error types not exported from Protocol
  Risk: Orchestration blocker
  Prompt: `/io-architect`
  Context to provide: "ErrorTypeX and ErrorTypeY need to be exported from
  interfaces/component_c.pyi. See backlog item [date]."
```
