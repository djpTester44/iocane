---
name: io-specify
description: Generate the capability roadmap from a clarified PRD. Tier 1 — plan mode required.
---

> **[CRITICAL] PLAN MODE**
> This workflow runs in plan mode. Claude PROPOSES `roadmap.md` content before writing anything.
> Nothing is committed until the human explicitly approves.

> **[CRITICAL] CONTEXT LOADING**
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load the PRD: `view_file plans/PRD.md`

# WORKFLOW: IO-SPECIFY

**Objective:** Transform a clarified `plans/PRD.md` into a dependency-ordered capability roadmap (`plans/roadmap.md`). This is the first Tier 1 gate after PRD clarification.

**Position in chain:**
```
/io-clarify -> [/io-specify] -> /io-architect -> /io-checkpoint -> /io-plan-batch -> /validate-tasks -> dispatch-agents.sh
```

---

## 1. STATE INITIALIZATION

Before proceeding, output the following metadata:

- **PRD Clarification Status:** [Must be `True` to proceed]
- **Feature Count (estimated):** [Number of top-level capabilities identified in PRD]
- **Known Hard Dependencies:** [Any features that are obviously sequenced]

---

## 2. PROCEDURE

### Step A: [CRITICAL] CLARIFICATION GATE

* **Action:** Read the document header of `plans/PRD.md`.
* **Check:** Locate the `**Clarified:**` field.
* **Rule:** If missing or `False`, HALT immediately.
* **Output:** "HALT: PRD has not been clarified. Run `/io-clarify` first."

---

### Step B: ANALYZE PRD FOR CAPABILITIES

* **Action:** Read `plans/PRD.md` in full.
* **Goal:** Identify every distinct user-facing capability.
* **Distinction:** A capability is something a user can do or observe — not an implementation detail.
  * **YES:** "User can authenticate via OAuth", "System processes payments"
  * **NO:** "Implement JWT middleware", "Add Redis cache"
* **Output:** Enumerate capabilities as a flat list with one-line descriptions.
* **Brownfield verification:** If `plans/current-state.md` exists, scan each capability for claims about existing behavior. Verify each claim against source cited in `current-state.md`. Tag unconfirmed claims as `[UNVERIFIED]`; these must not be treated as dependencies in Step C.

#### B.5: IDENTIFY TRUST EDGES / SECURITY BOUNDARIES

* **Goal:** Identify all system boundaries where external or untrusted input crosses into the system, or where the system calls out to external services it does not control.
* **Scan for:** user-supplied data paths, third-party API calls, file/network ingestion points, authentication surfaces, inter-service trust relationships.
* **Output:** For each boundary found, draft a Trust Edge entry using this structure:

```
- component: [either a feature ID like `F-03`, or an identifier-form component name; the validator at /io-architect Step G accepts either form]
  attack_vectors:
    - [vector one — what an attacker or malformed input can do here]
    - [vector two — ...]
  thresholds_settings: [one or more Settings symbol names that parameterize limits/thresholds at this boundary; write "none declared" if no Settings symbol applies yet]
```

* When a boundary surface spans multiple components, pick the form that matches the enforcement reality:
  * **Feature-form (`F-NN`)** — when EVERY component owning the feature genuinely enforces an adversarial path at this boundary. The validator's STRICT multi-owner check at `/io-architect` Step G requires ALL owners to carry adversarial-rejection `raises` entries; if any owner is a pass-through, this form will fail the gate.
  * **Identifier-form, split into `TE-NNa` / `TE-NNb`** — when only ONE component is the actual enforcer and others co-own the feature as pass-through (logging, rate-limiting, instrumentation). Author one TE per genuine-enforcer component; the `TE-NN` root indicates a shared boundary surface; each suffix isolates one component's enforcement responsibility.
  * The `component:` field is singular by design — never pack multiple components into a single identifier-form TE entry.
* If NO trust edges are found, explicitly output: "No trust edges identified — PRD describes no external-input or external-service boundaries."
* These entries carry forward into the roadmap proposal (Step D) and are the authoring source for `validate_trust_edge_chain.py` Check 1 at `/io-architect` Step G. Weak or missing declarations are caught at the design tier; absent declarations are caught deterministically by the validator.

---

### Step C: [PLAN MODE] BUILD DEPENDENCY MAP

* **Goal:** Determine which capabilities depend on others being complete first.
* **Method:** For each capability pair, ask: "Can B be built and tested independently before A exists?"
  * If no → A must precede B.
  * If yes → B is independent or can be parallel.
* **Output:** A dependency graph expressed as a simple ordered list with `depends_on` annotations.

**Do not write any file yet.** Present the dependency map to the human for review.

---

### Step D: [PLAN MODE] PROPOSE ROADMAP.MD

Propose the full content of `plans/roadmap.md` using this format:

```markdown
# Roadmap

**Generated from:** plans/PRD.md
**Status:** Draft — awaiting human approval

---

## Features

### F-01: [Feature Name]
**Description:** [One sentence — what the user can do when this is complete]
**Depends on:** none | [F-XX, F-YY]
**PRD reference:** [Section or requirement ID]
**Acceptance criteria:**
- [ ] [Testable, observable outcome]
- [ ] [Testable, observable outcome]

### F-02: [Feature Name]
...

---

## Trust Edges / Security Boundaries

<!-- Required section. Every trust boundary between the system and external input or external services
     must be declared here. Omitting this section causes validate_trust_edge_chain.py Check 1 to
     fail at /io-architect Step G. -->

### TE-01: [Boundary name]
- **component:** [either a feature ID like `F-03`, or an identifier-form component name; both forms accepted by the validator]
- **attack_vectors:**
  - [vector one]
  - [vector two]
- **thresholds_settings:** [Settings symbol name(s) that parameterize limits here, e.g. `pipeline_yaml_max_bytes`]

### TE-02: [Boundary name]
...

<!-- If the system has no external-input or external-service boundaries, write exactly:
     "No trust edges — this system accepts no external input and calls no external services." -->
```

**Worked example — multi-component split:**

When a single boundary surface has attack vectors that span multiple components, split into TE-NNa / TE-NNb suffix entries — one per component. The example below shows an "external connector endpoints" boundary split between an HTTP-transport owner and a log-redaction surface owner:

```
### TE-07a: External connector endpoints — HTTP transport
- **component:** BoundaryComponentA
- **attack_vectors:**
  - SSRF / malicious URL
  - oversize response body
- **thresholds_settings:** `webhook_response_max_bytes`

### TE-07b: External connector endpoints — log-redaction surface
- **component:** BoundaryComponentB
- **attack_vectors:**
  - credential leak in log emission
- **thresholds_settings:** `log_redaction_patterns`
```

**Rules for roadmap entries:**
- Every feature must have at least one testable acceptance criterion.
- Acceptance criteria must be observable at the system boundary — no internal implementation details.
- `depends_on` must be explicit. If a feature truly has no dependencies, write `none`.
- PRD reference is mandatory — every feature must trace to a PRD requirement.

**Rules for Trust Edges section:**
- The section is mandatory in every roadmap. Either one or more `TE-NN` entries, OR the explicit "no trust edges" statement — never omit the section entirely.
- `component` is either a feature ID (`F-NN`, matching a roadmap feature) or an identifier-form component name (e.g. `PipelineYamlParser`, matching a key in `plans/component-contracts.yaml`). The validator at `/io-architect` Step G accepts either form: feature-form resolves to all components whose contract `features:` field includes the cited feature; identifier-form resolves to that contract directly. Mixed forms (e.g. `F-01 — PipelineYamlParser`) are rejected — pick one.
- `attack_vectors` must be free-text bullets — at least one per Trust Edge.
- `thresholds_settings` must name at least one Settings symbol if the boundary has a configurable threshold; write "none declared" only if no threshold exists at this boundary.
- Trust Edges sourced from Step B.5. If Step B.5 produced no entries, the "no trust edges" statement satisfies the requirement.

**Present the full proposed `roadmap.md` to the human. Do not write the file.**

Output: "PROPOSAL READY. Review the roadmap above. Reply with approval to write, or provide corrections."

---

### Step E: [HUMAN GATE] APPROVAL REQUIRED

**WAIT** for explicit human approval before writing. Do NOT write `roadmap.md` until the operator approves.

#### E.1 — WAIT / TRIAGE SUB-PHASE (pre-approval)

While waiting for approval, the operator may optionally invoke `/challenge` to stress-test the proposal before deciding. This is operator-decided; no chain-mandatory invocation.

**Menu coverage scope (per D-06):** declaration QUALITY — weak, thin, or implausible declarations that technically satisfy structure but fail adversarial scrutiny. Declaration PRESENCE (does the Trust Edges section exist?) is handled deterministically by `validate_trust_edge_chain.py` Check 1 at `/io-architect` Step G; do not use the menu as a substitute for that check.

**Canned targeting prompts — paste one into `/challenge` targeted mode:**

1. `"argue against trust-edge declarations as a bypass attacker"` — stress-tests whether attack vectors are genuinely adversarial or optimistically thin; surfaces plausible bypass paths the declarations don't cover.
2. `"find the strongest feature-decomposition coherence problem"` — challenges whether the feature split is coherent, surfacing over-bundled or arbitrarily split capabilities.
3. `"argue against the dependency ordering for this domain"` — challenges the `depends_on` ordering; surfaces sequencing assumptions that reverse under realistic build conditions.
4. Broad fallback (novel / first-PRD cases): `"what is the strongest argument that this roadmap will fail to deliver the PRD's stated outcomes?"` — use when none of the targeted prompts fit the project shape.

**Post-finding flow:** If `/challenge` surfaces findings the operator accepts, revise the proposal in-session, re-present the revised roadmap, and re-block at Step E. The `/challenge` menu does NOT fire post-approval — once the operator approves, the file write proceeds.

#### E.2 — APPROVAL ACTION

* If corrections requested (from `/challenge` findings or operator review): revise the proposal, re-present. Do not write until approved.
* On approval: write `plans/roadmap.md` with `**Status:**` updated to `Approved`.

---

### Step F: STAMP AND ROUTE

* After writing `roadmap.md`, output:

```
ROADMAP LOCKED.

Features: [N]
Dependency layers: [N]

Next step: Run /io-architect to define CRC cards and component contracts.
```

---

## 3. CONSTRAINTS

- This workflow produces ONLY `plans/roadmap.md`. No `project-spec.md` or `component-contracts.yaml` edits.
- Do not decompose features into checkpoints here — that is `/io-checkpoint`'s job.
- Do not propose implementation approaches — roadmap entries describe outcomes, not mechanisms.
- If the PRD is ambiguous about whether two things are one feature or two, flag it and ask before proceeding.
- In brownfield repos, any PRD claim about existing behavior that cannot be verified against source must carry an `[UNVERIFIED]` tag through to `roadmap.md`.
- **Appendix A §A.6e -- Grep-verify paths before writing.** Before naming any file path in a feature's `PRD reference` or acceptance criteria, use the Grep tool to verify the path either (a) exists on disk, (b) traces back to the PRD, or (c) is explicitly flagged as a planned artifact with the producing feature named. Paths authored from memory here propagate through every downstream artifact and surface as orphan warnings at `/validate-plan` Step 9D.
