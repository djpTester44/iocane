---
name: validate-spec
description: Detect and remediate drift between plans/project-spec.md CRC cards and interfaces/*.pyi files. Re-syncs plans/component-contracts.yaml. Re-earns **Approved:** True after out-of-band .pyi changes.
---

# WORKFLOW: VALIDATE-SPEC (CRC-Protocol Drift Detection)

**Objective:** Detect drift between `plans/project-spec.md` CRC cards and `interfaces/*.pyi` Protocol definitions. Auto-remediate stale CRC entries, escalate structural changes to human judgment, re-sync `plans/component-contracts.yaml`, and re-earn the `**Approved:** True` stamp that gates `/io-checkpoint`.

**Context:**

* Target artifacts: `plans/project-spec.md` (CRC cards section), `interfaces/*.pyi`, and `plans/component-contracts.yaml`
* Output: Drift report, updated `plans/component-contracts.yaml`, and re-stamped `**Approved:** True` on `plans/project-spec.md`
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
* Load the CRC cards section and Interface Registry from `plans/project-spec.md`.
* Load `plans/component-contracts.yaml`. If the file does not exist, note it as missing — it will be generated in Step E-1.
* Do not load full `.pyi` file contents or implementation files — signatures and Protocol names only.

Files loaded in this step remain in context for all subsequent steps — do not re-read unless modified during this run.

---

### Step B — Detect Drift (CRC-Protocol Symmetry)

For each Protocol in `interfaces/*.pyi`, compare against the corresponding CRC card in `plans/project-spec.md`.

Four classes of finding:

1. **MISSING_CRC_METHOD** — Method present in `.pyi` Protocol but not listed in the CRC card.
2. **STALE_SIGNATURE** — Method listed in CRC card with a signature that does not match the `.pyi` Protocol method.
3. **ORPHANED_CRC_METHOD** — Method listed in CRC card but absent from the `.pyi` Protocol (possible `.pyi` regression or intentional removal). For ORPHANED_CRC_METHOD findings, invoke `/symbol-tracer` on the method symbols to check if the method is still referenced in implementation code despite being absent from the `.pyi` Protocol.
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

### Step E-1 — Sync component-contracts.yaml and Render CRC

After CRC-Protocol drift is resolved (or if zero drift was found in Step B), ensure `plans/component-contracts.yaml` is consistent and re-render the CRC section of project-spec.md.

**Drift detection (rendered CRC vs. YAML):** Run `render_crc.py --dry-run` and diff its output against the current `## CRC Cards` section in `plans/project-spec.md`. Any difference means the rendered narrative has drifted from the YAML source of truth.

```bash
uv run python .claude/scripts/render_crc.py --dry-run
```

**Drift detection (structural):** Compare the current `component-contracts.yaml` (loaded in Step A) against what the .pyi Protocols imply. If any of the following differ, remediation is required:

* A component appears in the Interface Registry or as a composition root but has no entry in `component-contracts.yaml`
* A component has an entry in `component-contracts.yaml` but no longer exists in the Interface Registry
* A component's `collaborators` list does not match the `Receives (DI)` list implied by its Protocol
* A component's `file` path does not match the implementation path in the Interface Registry
* A component's `responsibilities` do not align with the methods in its `.pyi` Protocol

**Auto-remediation procedure:**

When .pyi contracts drift from CRC responsibilities, write corrected behavioral data (`responsibilities`, `must_not`, `protocol`) directly to `plans/component-contracts.yaml` via `contract_parser.save_contracts()`. Then re-render:

```bash
uv run python .claude/scripts/render_crc.py
```

This follows the same save-then-render pattern as `/io-architect` Step H-2c + Step I-0: write YAML first, then generate the project-spec.md CRC section from it.

* Overwrite `plans/component-contracts.yaml` completely -- it is always regenerated, never patched.
* Prepend the standard header comment block (matching the format in the existing file).

If `component-contracts.yaml` is already in sync and the rendered CRC matches project-spec.md (no differences detected), skip the write -- no unnecessary file churn.

Report: "component-contracts.yaml: in sync" or "component-contracts.yaml: regenerated (N changes)".

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

* Scope is limited to CRC-Protocol symmetry and component-contracts sync. Do not validate connectivity tests, checkpoint structure, or layer contracts — those are the domain of `/validate-plan`.
* Do not modify `interfaces/*.pyi` files. `.pyi` files are the authoritative source; `plans/project-spec.md` is updated to match.
* `PROTOCOL_MISMATCH` findings (new or removed Protocol classes) must route to `/io-architect`, not be auto-amended.
* `extract_structure.py` output is the sole source for `.pyi` structural facts — do not read `.pyi` files directly unless `extract_structure.py` is unavailable.
* The sentinel must be active before any write to `plans/project-spec.md` in Step E and Step F. Never write to `project-spec.md` without the sentinel.
* If Step E and Step F writes are performed in sequence, a single sentinel set at the start of Step E covers both — do not re-set between steps.
* `plans/component-contracts.yaml` is always regenerated in full — never patched. Partial edits risk inconsistency with `check_di_compliance.py`.
* Step E-1 runs regardless of whether Step E made changes. Even if zero CRC-Protocol drift was found, `component-contracts.yaml` may still be stale from a prior OOB change.
