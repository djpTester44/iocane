---
name: run-state-snapshot
description: Capture a workflow-agnostic run-state snapshot to .iocane/findings/<datestamp>_<workflow>-state.md. Tier 2 -- operator-invoked mid-run, at workflow exit, or on interrupt. Reasoning-tier sections (1, 8, 9) authored by the host agent; mechanical sections (2-7) composed by compose_run_state.py.
model: claude-sonnet-4-6
---

> **[NO PLAN MODE]**
> Snapshot workflow. Bounded scope: one draft YAML, one compose call, one findings file.

# WORKFLOW: RUN-STATE-SNAPSHOT

**What this solves:** mid-run state, anomaly notes, and a recommended-continuation checklist often live only in the active conversation. A snapshot captures them to disk so a continuation session (or a remediation-analysis pass) can pick up cold.

**Position in chain:** standalone. Invokable from any workflow context. Output is consumed downstream by `/HARNESS-remediation-analyze` (the snapshot path is one of its required inputs).

```
[/run-state-snapshot]  -->  .iocane/findings/<datestamp>_<workflow>-state.md
                                  -->  /HARNESS-remediation-analyze (later)
```

---

## 1. STATE INITIALIZATION

Output the following before proceeding:

- **Workflow argument:** `<workflow-name>` (defaults to `generic` if omitted)
- **Repo root:** `git rev-parse --show-toplevel` (or cwd fallback)
- **Active workflow context:** what command/loop the operator was running when invoking this snapshot (one sentence)

---

## 2. PROCEDURE

### Step A: [HARD GATE] CAPABILITY GRANT

```bash
uv run python .claude/scripts/capability.py grant --template run-state-snapshot
```

Authorizes writes to `.iocane/drafts/run-state-draft.yaml` and `.iocane/findings/*-state.md`. Without this grant the writes in Steps B and C are unauthored and reset hooks may fire on the findings write.

Verification: `capability.py grant` exits 0 and the grant appears in `list-active --json` under template name `run-state-snapshot`.

---

### Step B: AUTHOR DRAFT YAML

Write `.iocane/drafts/run-state-draft.yaml` with the reasoning-tier sections. Schema is enforced by `compose_run_state.py` -- malformed draft halts Step C.

```yaml
# Required fields
workflow_label: "<short label>"        # e.g., "/io-architect cycle 4 H-loop interrupted"
generated_note: "<one-sentence>"       # optional; rendered under the H1
run_state:                             # bullets for §1
  - "..."
anomalies:                             # entries for §8
  - label: "INFRASTRUCTURE"            # required; categorical tag
    qualifier: "confirmed before cycle 1"   # optional; suffix on the bold head
    body: "..."                        # required; full-prose body
recommended_continuation:              # numbered checklist for §9
  - "..."
agent_decisions:                       # optional but encouraged for any deliberate departure from defaults
  - choice: "<what the agent picked>"
    alternatives_considered:           # may be empty list
      - "<other-option-A>"
      - "<other-option-B>"
    reasoning: "<why this choice>"
    deliberated: true                  # false if reflexive/default
```

**Authoring guidance (host agent reads this BEFORE filling the draft):**

- **`workflow_label`** -- short label naming the workflow + state (e.g., `/io-architect cycle 4 H-loop interrupted`, `/io-checkpoint Step D in progress`, `idle / mid-session`).
- **`run_state`** (§1) -- one bullet per load-bearing fact about *where the workflow is right now*: active cycle, last completed step, in-flight subprocess at interrupt, approximate remaining context. Mechanical-section data (canonical YAML counts, finding counts, capability state) does NOT belong here -- those render mechanically. §1 is what the operator needs to know that the disk does not show.
- **`anomalies`** (§8) -- categorical, labeled observations. Use stable labels: `INFRASTRUCTURE`, `EVALUATOR FINDING DELIVERY`, `EVALUATOR PROGRESS PATTERN`, `STAMP STATE`, `INDEX MAY BE OUT OF SYNC`, `OUTSTANDING`. Each entry is a load-bearing concern that future-you needs to act on; if it is just colorful narration, drop it.
- **`recommended_continuation`** (§9) -- numbered checklist of concrete next moves a continuation session should run. Each item is an executable action (`Glob ...`, `re-spawn ...`, `view_file ...`), not a status statement. Aim for 3-6 items; this is the handoff payload.
- **`agent_decisions`** (§10) -- populate whenever you escape a default workflow path or pick between two non-obvious mechanisms. Each entry: the choice, what was considered, the reasoning, and whether the call was deliberated or reflexive. The `deliberated` flag matters most -- a "reflexive default" entry is the harness team's signal that the option space wasn't actually evaluated, which is upstream-evidence for fix-shape design. Without this field, downstream remediation passes have to infer agent intent from artifact shapes (per `AGENTS.md` 2026-04-27 lesson, the failure mode that produced the substage-A.5 plan-revision cascade).

Mechanical sections (canonical artifact counts, agent-authored scripts, drafts/scratch, capability state, finding emissions, Step G outputs) are composed automatically by `compose_run_state.py` -- do not duplicate them in the draft.

Verification: `.iocane/drafts/run-state-draft.yaml` exists and parses as valid YAML; required fields present.

---

### Step C: [HARD GATE] COMPOSE SNAPSHOT

```bash
uv run python .claude/scripts/compose_run_state.py \
    --draft .iocane/drafts/run-state-draft.yaml \
    --output .iocane/findings/<YYYYMMDD-HHMM>_<workflow>-state.md \
    --workflow <workflow-name>
```

`<workflow-name>` is the operator's argument (defaults to `generic`). Pass `io-architect` for io-architect-specific sections (§2 canonical artifacts, §4 finding emissions, §7 Step G validator outputs); other variants ship as workflows add per-step machinery.

`<YYYYMMDD-HHMM>` matches the existing `.iocane/findings/` datestamp convention used by `findings_emitter.py`.

Verification: script exits 0; output markdown file exists at the named path. On exit 1 the draft is malformed -- repair Step B and re-run.

---

### Step D: [HARD GATE] CAPABILITY REVOKE

```bash
uv run python .claude/scripts/capability.py revoke --template run-state-snapshot
```

Explicit revoke is the primary cleanup; the template's 600s `ttl_seconds` is a crash-safety floor only.

Verification: `list-active --json` no longer reports the `run-state-snapshot` grant for this session.

---

### Step E: SURFACE OUTPUT

Print the absolute output path to the operator. The path is the consumable handoff -- continuation sessions and `/HARNESS-remediation-analyze` both read this file.

---

## 3. CONSTRAINTS

- Workflow-agnostic: do NOT add reasoning specific to a particular `/io-*` workflow into the command file. Per-workflow optional sections live in `compose_run_state.py`'s `SECTIONS_<WORKFLOW>` constants and are selected by the `--workflow` flag.
- The draft schema (`RunStateDraft` Pydantic model in `compose_run_state.py`) is the contract. Schema drift surfaces as a Step C halt; do not work around it by hand-editing the output markdown.
- Do not invoke this command as part of an automated workflow chain -- it is operator-invoked. Mid-workflow snapshots are valid; the snapshot itself does not modify any canonical artifact.
