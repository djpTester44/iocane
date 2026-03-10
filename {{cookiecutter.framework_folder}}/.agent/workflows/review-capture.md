---
description: Classify review findings and append them to plans/backlog.md. Called by /review and /gap-analysis.
---

> **[NO PLAN MODE]**
> Append-only. Never deletes or modifies existing backlog entries.

> **[CRITICAL] CONTEXT LOADING**
> 1. Load ticket taxonomy: `view_file .agent/rules/ticket-taxonomy.md`
> 2. Load current backlog: `view_file plans/backlog.md` (if exists)

# WORKFLOW: REVIEW-CAPTURE

**Objective:** Take findings from `/review` or `/gap-analysis` and append them to `plans/backlog.md` with correct taxonomy tags. Findings not in `backlog.md` are invisible to subsequent planning workflows.

---

## 1. PROCEDURE

### Step A: RECEIVE FINDINGS

* Accept the findings table from the calling workflow (`/review` or `/gap-analysis`).
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

Each finding becomes one backlog entry in this format:

```markdown
- [ ] [TAG] [ComponentName] — [one line description of the issue]
  - Source: /review CP-[ID] | /gap-analysis [date]
  - Severity: HIGH | MEDIUM
  - Detail: [one sentence of context — what to fix and why]
```

---

### Step D: APPEND TO BACKLOG.MD

* **If `plans/backlog.md` does not exist:** Create it with this header, then append:

```markdown
# Backlog

Findings from /review and /gap-analysis. Append-only — never delete entries.
Items marked [x] are resolved. Items marked [ ] are active.

---
```

* **Append** a new group under a heading:

```markdown
### From [CP-ID | gap-analysis] — [YYYY-MM-DD]

- [ ] [TAG] [ComponentName] — [description]
  - Source: ...
  - Severity: ...
  - Detail: ...
```

* **Never** modify existing entries.
* **Never** delete resolved `[x]` entries — they are the audit trail.

---

### Step E: OUTPUT

```
CAPTURE COMPLETE.

Items appended to plans/backlog.md: [N]
  [DESIGN]: [N]
  [REFACTOR]: [N]
  [CLEANUP]: [N]
  [TEST]: [N]

[If DESIGN items captured:]
Note: [DESIGN] items require /io-architect before next orchestration cycle.
```

---

## 2. CONSTRAINTS

- Append only — no edits to existing entries under any circumstance
- Does not route findings to `plans/plan.md`, `plans/roadmap.md`, or any other artifact
- Does not create tasks — backlog items are pulled by `/io-orchestrate` as inputs to the next cycle
- `[DEFERRED]` items must include a human-provided reason — do not defer autonomously
