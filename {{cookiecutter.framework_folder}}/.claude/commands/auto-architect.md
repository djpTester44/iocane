---
name: auto-architect
description: Automated DESIGN/REFACTOR backlog resolution. Tier 1 -- plan mode required, evaluator-gated.
---

> **[CRITICAL] PLAN MODE**
> This is a Tier 1 design workflow -- it analyzes architecture, proposes CRC/Protocol
> changes, and writes binding contracts. Plan mode reflects the workflow's nature
> (design-first). Quality is enforced by an Opus evaluator agent, not a human gate.

> **[CONTEXT LOADING]**
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load the Design Skill: `view_file .claude/skills/mini-spec/SKILL.md` (CRC card format -- Section 2)
> 3. Load the PRD: `view_file plans/PRD.md`
> 4. Load the Roadmap: `view_file plans/roadmap.md`
> 5. Load current Architecture Spec: `view_file plans/project-spec.md`
> 6. Load component contracts: `view_file plans/component-contracts.yaml`

# WORKFLOW: AUTO-ARCHITECT

**Objective:** Resolve open DESIGN/REFACTOR backlog items by extracting routing prompts,
researching changes via sub-agents, validating via evaluator, and writing approved
changes to project-spec.md, interfaces/*.pyi, and supporting artifacts.

**Position in chain:**

```
/io-backlog-triage -> [/auto-architect] -> /auto-checkpoint -> /validate-plan -> /io-plan-batch
```

---

## Step 0: [HARD GATE] PRE-INVOCATION CHECK

```bash
bash .claude/scripts/pre-invoke-auto-architect.sh
```

If exit != 0, HALT with the error output. Do not proceed.

---

## Step A: EXTRACTION

Run the backing extraction script:

```bash
uv run python .claude/scripts/auto_architect.py [--repo-root PATH]
```

Parse the JSON manifest from stdout. It contains eligible items with dependency edges
and wave ordering.

If `"item_count": 0`, HALT: "No eligible DESIGN/REFACTOR items found."

---

## Step A.5: DEPENDENCY ENRICHMENT

Enrich the dependency graph with implicit edges from symbol analysis:

1. Extract component symbols from each item's `files` field
2. `/symbol-tracer --imports-only` on all candidate symbols to detect import edges
3. `/symbol-tracer --find-implementors` on Protocol symbols from DESIGN items
4. Add implicit dependency edges where cross-references detected
5. Re-run topological sort on merged graph (explicit + implicit edges)
6. If cycle detected: HALT with cycle details -- human resolution required

---

## Step B: CONTEXT LOAD (once)

Load Tier 1 artifacts into session (if not already loaded by the context loading block):

- `plans/PRD.md`
- `plans/roadmap.md`
- `plans/project-spec.md` (current CRC cards, Protocol signatures, Interface Registry)
- `plans/component-contracts.yaml`
- `.claude/skills/mini-spec/SKILL.md` (CRC card format reference)
- `.claude/rules/planning.md`

These are loaded ONCE for the entire batch. Sub-agents receive targeted slices.

---

## Step C: DISPLAY BATCH SUMMARY

Print a table to the user:

```
BL-ID      | Tag      | Severity | Wave | Prompt preview
-----------|----------|----------|------|-------------------------------
BL-003     | DESIGN   | HIGH     | 1    | Add UpstreamServiceError to...
BL-007     | REFACTOR | MEDIUM   | 2    | Extract validation logic...
```

Show dependency edges (explicit + implicit). Wait for user acknowledgment before proceeding.

---

## Step D: SEQUENTIAL RESEARCH (one Sonnet Plan agent per item, in topological order)

For each item, in wave order:

### D.1: Dispatch Plan agent (model: Sonnet)

Provide the agent with:
- The routing prompt text from the BL item (`architect_prompt`)
- `files` field (which files to read)
- Current CRC card for the affected component (from project-spec.md)
- Current Protocol signature (from interfaces/*.pyi, if DESIGN)
- CRC card format reference (from mini-spec Section 2)
- Accumulated plan context from previous agents' results
  (e.g., "BL-003 decided: add MatrixElementError to ITrafficProvider Raises")

### D.2: Agent returns structured findings

The agent explores code at the referenced files, reads current state, and returns:
- Atomic CRC card changes (which responsibility lines to add/modify/remove)
- Protocol signature changes if DESIGN (which methods/docstrings to update)
- Component-contracts.yaml changes if collaborators changed
- seams.yaml changes if failure modes or DI receivers changed (via seam_parser)
- file:line citations for all claims about existing code

### D.3: Incorporate results

Parent (Opus) incorporates agent result into the consolidated plan.

### D.4: Scope validation

If the agent reports changes beyond the item's tag scope (e.g., REFACTOR needs .pyi
change -- should be DESIGN), flag and skip the item. Log: "BL-NNN flagged for
re-triage: REFACTOR item requires .pyi changes (should be DESIGN)."

---

## Step E: EVALUATOR GATE (Opus agent)

Dispatch an Opus evaluator agent with:
- The consolidated plan (per-item changes grouped by artifact)
- Current project-spec.md, interfaces/*.pyi, component-contracts.yaml
- CRC card format reference (mini-spec Section 2)
- Planning rules (.claude/rules/planning.md)

### Evaluator checks:

1. CRC card changes follow mini-spec format (layer, responsibilities, collaborators, Must NOT)
2. Protocol signature changes are additive or explicitly flagged as breaking
3. REFACTOR items do NOT include .pyi changes
4. No orphaned collaborator references (component references a collaborator not in the registry)
5. file:line citations in CRC cards are valid (cited files/lines exist)
6. Dependency map consistency (new edges don't violate layer rules)

### Evaluator output:

- **PASS:** Proceed to execution.
- **FAIL:** List specific findings per item. Remove failing items from batch.
  Passing items proceed. Failing items remain `[ ]` for correction and next run.

---

## Step E.5: [MECHANICAL] CRC BUDGET PRE-GATE

After Step E filters the batch, and BEFORE Step F writes anything to `plans/` or `interfaces/`, serialize the proposed CRC state and run the deterministic budget gate. This mirrors `/io-architect` Step G-pre; invoking `/auto-architect` must never be a way to sidestep the A.1 caps.

1. Build the proposed `ComponentContractsFile`: start from the current `plans/component-contracts.yaml` and apply every remaining (post-Step-E) item's CRC changes in memory.
2. Write the proposed state to the staging path `.iocane/crc-budget-staging.yaml` using `contract_parser.save_contracts()`.
3. Run the validator against the staging file:

```bash
uv run python .claude/scripts/validate_crc_budget.py \
  --contracts .iocane/crc-budget-staging.yaml
```

4. On exit 1 (violations):
   - HALT before Step F. No real writes to `plans/` or `interfaces/` have happened.
   - Report violating components and the backlog items whose changes introduced the over-capacity state.
   - Instruct the user to either (a) narrow/split the offending items via `/io-backlog-triage`, or (b) decompose the affected components via `/io-architect`. `/auto-architect` cannot repair structural over-capacity on its own.
   - Leave failing items `[ ]` in backlog for the next run. Delete `.iocane/crc-budget-staging.yaml`.
5. On exit 2 (load error): HALT and surface the error -- something is wrong with the staging serialization.
6. On exit 0: delete `.iocane/crc-budget-staging.yaml` and proceed to Step F.

The staging path isolates the gate from `plans/component-contracts.yaml`, so a failed pre-gate does not leave partially-approved contracts on disk or perturb `hooks/design-before-contract.sh`.

---

## Step F: EXECUTE (sequential)

### F.0: Create sentinel

```bash
mkdir -p .iocane && touch .iocane/validating
```

### F.1: REFACTOR mode enforcement

For each REFACTOR item in the batch, set context:
`IOCANE_REFACTOR_MODE=1` -- write-gate.sh blocks interfaces/*.pyi writes when set.

### F.2: Update seams.yaml

If failure modes or DI receivers changed. Use `seam_parser.update_component()` and `save_seams()`.

### F.3: Write CRC card changes

Write CRC changes to `plans/component-contracts.yaml` via `save_contracts()`, then render to project-spec.md:

```bash
uv run python .claude/scripts/render_crc.py
```

Use `git diff plans/project-spec.md` to inspect what changed in the rendered output.

### F.4: Write Protocol signature changes

Write to `interfaces/*.pyi` -- DESIGN items only.

### F.5: Update component-contracts.yaml

If CRC data changed (collaborators, responsibilities, must_not, or protocol), write to `plans/component-contracts.yaml` via `save_contracts()`, then re-render:

```bash
uv run python .claude/scripts/render_crc.py
```

### F.6: Regenerate directory-level CLAUDE.md files

Run the sync script:

```bash
uv run python .claude/scripts/sync_dir_claude.py
```

**Rule:** These files are generated artifacts -- the script overwrites them.
They must stay under 20 lines. If the script reports exit code 2 (line-count
exceeded), flag the directory as a `[DESIGN]` finding.

### F.7: VALIDATE-SPEC GATE (Sonnet agent)

Dispatch Sonnet agent to run `/validate-spec` against the written artifacts.

validate-spec runs BEFORE the Approved: True stamp. Its Step 0 gate checks for
Approved: True and halts if present -- so we run it while the stamp is still False,
letting it verify CRC/.pyi consistency.

- **PASS:** Proceed to F.8.
- **FAIL:** Report drift findings. HALT. Sentinel cleanup needed manually.
  Items not marked resolved. Re-run after fixes.

### F.8: Strip markers

Remove all `<!-- CHANGED -->` markers from project-spec.md.

### F.9: Stamp approval

Write `**Approved:** True` to plans/project-spec.md.

### F.10: Delete sentinel

```bash
rm -f .iocane/validating
```

---

## Step G: POST-RESOLUTION

For each resolved item:

### G.1: Mark resolved in backlog

Mark the BL item `[x]` in plans/backlog.yaml and add annotation:
```
  - Resolved: auto-architect (YYYY-MM-DD)
```

### G.2: Unblock dependents

Scan backlog for items with `Blocked: BL-NNN` referencing the resolved item.
Replace the Blocked annotation with:
```
  - Unblocked: BL-NNN resolved by auto-architect (YYYY-MM-DD)
```

This unblocks dependent CLEANUP/TEST items for /auto-checkpoint pickup.

---

## Step H: SUMMARY

Output:
- Resolved count
- Unblocked dependents count
- Remaining blockers (if any)
- Evaluator failures (if any items were removed)
- Next step recommendation:
  - `/auto-checkpoint` if unblocked CLEANUP/TEST items now eligible
  - `/validate-plan` -> `/io-plan-batch` if no pending remediation
