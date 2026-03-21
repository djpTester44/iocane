---
description: Classify review findings and write them to plans/review-output.md staging file. Called by /io-review and /gap-analysis.
---

> **[NO PLAN MODE]**
> Append-only to staging file. Never deletes or modifies existing entries.

> **[CRITICAL] CONTEXT LOADING**
> 1. Load ticket taxonomy: `view_file .agent/rules/ticket-taxonomy.md`
> 2. Load current staging file: `view_file plans/review-output.md` (if exists)

# WORKFLOW: REVIEW-CAPTURE

**Objective:** Take findings from `/io-review` or `/gap-analysis` and append them to
`plans/review-output.md` (staging file) with correct taxonomy tags and structured
fields. Findings in staging are invisible to orchestration until `/io-backlog-triage`
drains them into `plans/backlog.md`.

---

## 1. PROCEDURE

### Step A: RECEIVE FINDINGS

* Accept the findings table from the calling workflow (`/io-review` or `/gap-analysis`).
* Filter: include only HIGH and MEDIUM severity findings.
* LOW and INFO findings are not captured unless explicitly requested by the human.

---

### Step B: CLASSIFY EACH FINDING

Apply routing tags from `.agent/rules/ticket-taxonomy.md`:

| Tag | When to apply |
|-----|--------------|
| `[DESIGN]` | Finding reveals a gap or error in the CRC or Protocol — requires `/io-architect` |
| `[REFACTOR]` | Implementation violates DI, layer boundaries, or SOLID — requires code change |
| `[CLEANUP]` | Minor improvement — naming, docstrings, test coverage — does not block execution |
| `[TEST]` | Missing or inadequate test coverage — does not block execution |
| `[DEFERRED]` | Acknowledged but intentionally postponed — must include a reason |

**Private method gate:** Do not capture findings for `_`-prefixed methods unless they represent a DI or layer violation. Internal implementation details are not backlog items.

---

### Step C: FORMAT ENTRIES

Each finding becomes one structured entry in the staging file. No BL-NNN headers
or checkboxes — those are assigned when triage drains to `plans/backlog.md`.

```markdown
#### Finding N
- Tag: [TAG]
- Severity: HIGH | MEDIUM
- Component: [ComponentName]
- Files: [comma-separated repo-relative paths — omit if cross-cutting or unknown]
- Issue: [one line description of the issue]
- Detail: [implementation guidance — what to fix and why]
- Contract impact: None | [description of CRC/Protocol change needed]
```

---

### Step D: APPEND TO REVIEW-OUTPUT.MD

* **If `plans/review-output.md` does not exist:** Create it with this header, then append:

```markdown
# Review Staging

Findings from /io-review and /gap-analysis. Append-only until triage drains.
Partial triage supported: human specifies which sections to process.

---
```

* **Append** a new group under a heading:

```markdown
### From [CP-ID | gap-analysis] -- [YYYY-MM-DD]

#### Finding 1
- Tag: [TAG]
- Severity: HIGH | MEDIUM
- Component: [ComponentName]
- Files: [paths]
- Issue: [summary]
- Detail: [guidance]
- Contract impact: None
```

* **Never** modify existing entries in the staging file.

---

### Step E: OUTPUT

```
CAPTURE COMPLETE.

Items appended to plans/review-output.md: [N]
  [DESIGN]: [N]
  [REFACTOR]: [N]
  [CLEANUP]: [N]
  [TEST]: [N]

[If DESIGN items captured:]
Note: [DESIGN] items will require /io-architect after triage drains them to backlog.

Next: /io-backlog-triage to drain staging into plans/backlog.md.
```

---

## 2. CONSTRAINTS

- Append only — no edits to existing entries under any circumstance
- Output target is `plans/review-output.md` (staging), NOT `plans/backlog.md`
- Does not route findings to `plans/plan.md`, `plans/roadmap.md`, or any other artifact
- Does not create tasks — findings are pulled by `/io-backlog-triage` for routing
- `[DEFERRED]` items must include a human-provided reason — do not defer autonomously
