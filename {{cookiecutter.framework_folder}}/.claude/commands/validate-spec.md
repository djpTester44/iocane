---
name: validate-spec
description: Detect and remediate drift between plans/project-spec.md CRC cards and interfaces/*.pyi files. Re-earns **Approved:** True after out-of-band .pyi changes.
---

# WORKFLOW: VALIDATE-SPEC (CRC-Protocol Drift Detection)

**Objective:** Detect drift between `plans/project-spec.md` CRC cards and `interfaces/*.pyi` Protocol definitions. Auto-remediate stale CRC entries, escalate structural changes to human judgment, and re-earn the `**Approved:** True` stamp that gates `/io-checkpoint`.

**Context:**

* Target artifact: `plans/project-spec.md` (CRC cards section) and `interfaces/*.pyi`
* Output: Drift report and re-stamped `**Approved:** True` on `plans/project-spec.md`
* Trigger: Recovery path. Run after `reset-on-pyi-write.sh` has reset `**Approved:** False` due to an out-of-band `.pyi` modification.

**Position in chain:**

```
/io-architect ──────────────────────────────────────────> /io-checkpoint
     └── [.pyi OOB change] -> /validate-spec ───────────> /io-checkpoint
```

---

## PROCEDURE

### Step 0 — [HARD GATE] APPROVED STAMP CHECK

* Read `plans/project-spec.md` header.
* If `**Approved:** True` is present: inform the user "No drift detected — stamp is current. /io-checkpoint may proceed." Halt.
* If `plans/project-spec.md` does not exist: halt with "Run /io-architect first to generate the project spec."
* If `**Approved:** False` (or stamp absent): continue to Step A.

---

### Step A — Load Structural Skeletons

* For each file in `interfaces/*.pyi`: run `python extract_structure.py <file>` to load its structural skeleton (Protocol names, method signatures, decorators) into context.
* Load the CRC cards section from `plans/project-spec.md`.
* Do not load full `.pyi` file contents or implementation files — signatures and Protocol names only.

Files loaded in this step remain in context for all subsequent steps — do not re-read unless modified during this run.

---

### Step B — Detect Drift (CRC-Protocol Symmetry)

For each Protocol in `interfaces/*.pyi`, compare against the corresponding CRC card in `plans/project-spec.md`.

Four classes of finding:

1. **MISSING_CRC_METHOD** — Method present in `.pyi` Protocol but not listed in the CRC card.
2. **STALE_SIGNATURE** — Method listed in CRC card with a signature that does not match the `.pyi` Protocol method.
3. **ORPHANED_CRC_METHOD** — Method listed in CRC card but absent from the `.pyi` Protocol (possible `.pyi` regression or intentional removal). For ORPHANED_CRC_METHOD findings, run `symbol_tracer.py --symbol "<Symbol1>,<Symbol2>" --root src/` to check if the method is still referenced in implementation code despite being absent from the `.pyi` Protocol.
4. **PROTOCOL_MISMATCH** — Entire Protocol class in `.pyi` with no corresponding CRC card, or a CRC card with no corresponding Protocol in `.pyi`.

---

### Step C — Classify Violations

**AUTO-REMEDIABLE** (`.pyi` is authoritative; `project-spec.md` is stale):

| Finding | Auto-Fix Action |
|---------|-----------------|
| `MISSING_CRC_METHOD` | Add the missing method entry to the CRC card in `plans/project-spec.md`. |
| `STALE_SIGNATURE` | Update the CRC card signature to match the `.pyi` Protocol signature. |

**REQUIRES_HUMAN_JUDGMENT** (structural change; cannot auto-fix):

| Finding | Escalation |
|---------|------------|
| `ORPHANED_CRC_METHOD` | Present to user: "Was this method intentionally removed from `.pyi`, or was the `.pyi` edit a mistake?" If intentional removal confirmed: remove from CRC card (auto-remediable after confirmation). If `.pyi` edit was a mistake: user must correct `.pyi` and re-run `/validate-spec`. |
| `PROTOCOL_MISMATCH` (new Protocol in `.pyi`, no CRC card) | Requires `/io-architect` — structural addition outside the recovery scope of this workflow. |
| `PROTOCOL_MISMATCH` (CRC card exists, Protocol removed from `.pyi`) | Requires `/io-architect` — structural removal outside the recovery scope of this workflow. |

---

### Step D — Report Findings

Present a drift table to the user:

| File | Finding Class | Method / Protocol | Violation | Action |
|------|---------------|-------------------|-----------|--------|

* If zero violations found: skip directly to Step F (stamp immediately).
* If only AUTO-REMEDIABLE findings: inform the user of the changes to be applied, then proceed to Step E.
* If any REQUIRES_HUMAN_JUDGMENT findings:
  * Present each finding with the clarifying question from Step C.
  * If the user resolves all judgment findings (confirms intentions): treat resolved items as auto-remediable and proceed to Step E.
  * If any finding cannot be resolved here: halt and direct the user to `/io-architect` for full redesign.

---

### Step E — Auto-Remediate

* Set sentinel: `bash: mkdir -p .iocane && touch .iocane/validating`
* Apply all MISSING_CRC_METHOD and STALE_SIGNATURE fixes to `plans/project-spec.md`.
* Apply any ORPHANED_CRC_METHOD removals confirmed by the user in Step D.
* Re-run Step B to verify no further drift remains after edits. If new violations surface, return to Step D.

---

### Step F — Stamp

* Confirm zero unresolved violations.
* If Step E was skipped (zero violations detected in Step B): set sentinel now: `bash: mkdir -p .iocane && touch .iocane/validating`
* Write `**Approved:** True` to the `plans/project-spec.md` header.
* The sentinel is auto-deleted by `reset-on-project-spec-write.sh` when it detects the `**Approved:** True` write — no explicit cleanup step required.

---

### Step G — Confirm

* Inform the user: "`**Approved:** True` written to `plans/project-spec.md`. `/io-checkpoint` may now proceed."

---

## CONSTRAINTS

* Scope is limited to CRC-Protocol symmetry only. Do not validate connectivity tests, checkpoint structure, or layer contracts — those are the domain of `/validate-plan`.
* Do not modify `interfaces/*.pyi` files. `.pyi` files are the authoritative source; `plans/project-spec.md` is updated to match.
* `PROTOCOL_MISMATCH` findings (new or removed Protocol classes) must route to `/io-architect`, not be auto-amended.
* `extract_structure.py` output is the sole source for `.pyi` structural facts — do not read `.pyi` files directly unless `extract_structure.py` is unavailable.
* The sentinel must be active before any write to `plans/project-spec.md` in Step E and Step F. Never write to `project-spec.md` without the sentinel.
* If Step E and Step F writes are performed in sequence, a single sentinel set at the start of Step E covers both — do not re-set between steps.
