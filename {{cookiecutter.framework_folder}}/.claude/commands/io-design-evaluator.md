---
name: io-design-evaluator
description: Semantic design-evaluator subprocess. Reads io-architect's canonical three-artifact set and emits OBSERVATION findings against the design rubric. Tier 1 (Opus). Spawned by .claude/scripts/spawn-artifact-evaluator.sh --rubric design at io-architect Step H. Single-pass per attempt; subprocess remains read-only on canonicals.
---

> **[NO PLAN MODE]**
> This workflow runs as a subprocess from the architect spawn helper.
> No proposals. No human interaction. Emit findings; exit 0.

> **[CRITICAL] CONTEXT LOADING**
> Load only the four canonical artifacts named in the spawn prompt
> plus the artifact-evaluator skill (`SKILL.md` +
> `references/design-eval-rubric.md`). Do NOT read implementation
> files, dispatch logs, or upstream planning documents.

# WORKFLOW: IO-DESIGN-EVALUATOR

**Objective.** Apply the eight-category design rubric semantically
against the canonical artifact set. Emit one Finding per defect via
`findings_emitter.emit_finding`. Print a summary line. Exit 0.

**Chain positioning.**

```
io-architect Step H -> spawn-artifact-evaluator.sh --rubric design
  -> [io-design-evaluator] -> findings emitted to .iocane/findings/
  -> io-architect Step I (operator-gate)
```

Single-pass per architect attempt (R2-narrow). Subprocess emits findings
or PASS; caller (architect) consumes findings at Step I operator gate
and decides next action. No auto-iteration from subprocess.

---

## 1. STATE INITIALIZATION

The spawn prompt names three canonical artifact paths:

- `contracts` -- `plans/component-contracts.yaml`
  (`ComponentContractsFile`)
- `seams` -- `plans/seams.yaml` (`SeamsFile`)
- `symbols` -- `plans/symbols.yaml` (`SymbolsFile`)

Read all three. Read the artifact-evaluator skill `SKILL.md` and
`references/design-eval-rubric.md` to load the methodology and the
reasoning categories. Do not read any other file -- the rubric
is self-contained against the three canonical artifacts.

---

## 2. PROCEDURE

**Step A-pre:** `bash: uv run python .claude/scripts/capability.py grant --template io-design-evaluator.A`

Issues the capability grant that authorizes findings emission to `.iocane/findings/*.yaml`. The grant is declared in `.claude/capability-templates/io-design-evaluator.A.yaml` -- git-tracked, PR-reviewable. Step D-1 explicitly revokes the grant at subprocess exit; the template's `ttl_seconds` and the parent session's `session-end.sh` sweep are crash-safety fallbacks, NOT a substitute for explicit revoke. `claude -p` subprocesses are non-interactive and fire no Stop hook on exit, so without Step D-1 the grant lingers in the active cache until TTL expiry, masking reset-hook behavior on any subsequent canonical-YAML write.

### Step A: APPLY THE RUBRIC

For each of the categories in `design-eval-rubric.md`,
reason across the three-artifact set:

1. **Tautological Invariants** -- scan
   `ComponentContract.responsibilities` and `raises` entries for
   restatements of types, names, or framework guarantees.
2. **Vague Raises Triggers** -- scan
   `ComponentContract.raises[]` strings for trigger phrasing that
   does not name a concrete precondition.
3. **Suspicious Symbol Classifications** -- cross-reference
   `SymbolsFile` `kind` / `declared_in` against the same names'
   usage in `ComponentContractsFile`.
4. **Missing Adversarial Coverage** -- scan
   `ComponentContract.responsibilities` for security-sensitive or
   input-validation surfaces; check that the matching `raises` and
   the matching `entries[component].invariants` carry adversarial
   triggers.
5. **Near-Duplicate Symbols** -- scan `SymbolsFile` for entries that
   differ only in case, pluralization, underscores, or one-character
   typos and that both appear on the same component's surface.
6. **Over-Abstracted Parameter Types** -- scan
   `ComponentContract.responsibilities` and
   `ComponentContract.raises[]` for `Any`, `object`, `dict`, or
   unparameterized `Mapping` references that strip the test surface.
7. **Implementation-Leaking Docstrings** -- scan
   `ComponentContract.responsibilities` for prose describing HOW (algorithm,
   internal state, library) instead of WHAT (guaranteed behavior).
8. **Responsibility Cohesion Drift** -- scan
   `ComponentContract.responsibilities` for two-or-more unrelated
   concerns bundled into one component (composition_root components
   exempt).

### Step B: EMIT FINDINGS

For each defect surfaced under Step A, author a Finding payload and
emit via the `findings_emitter` CLI. Workflow per finding:

1. Use the Write tool to author a transient finding-payload YAML
   (e.g., `.iocane/findings/.tmp-finding-payload.yaml`) containing a
   single Finding payload. See SKILL.md Finding Emission Contract for
   the field shape.
2. Invoke the emitter CLI:

   ```bash
   uv run python -m findings_emitter --from-yaml .iocane/findings/.tmp-finding-payload.yaml
   ```

   The emitter validates the payload against the `Finding` schema,
   computes the canonical `<role>-<timestamp>-<NNN>.yaml` filename,
   writes to `.iocane/findings/`, and prints the absolute path of the
   written file on stdout. Non-zero exit means schema validation or
   write failure -- repair the payload and re-invoke.

3. The `validate-yaml.sh` PostToolUse hook independently validates
   the written `.iocane/findings/<role>-<ts>-<seq>.yaml` against
   `FindingFile.model_validate`. Belt-and-suspenders: emitter
   validates the input; hook validates the output.

Each Finding emits to a separate file -- one defect per FindingFile
per the SKILL.md emission contract. Use the CLI; do not write
findings YAML by hand to `.iocane/findings/<role>-<ts>-<seq>.yaml`
(the canonical-naming logic lives in the emitter).

Required Finding fields (per SKILL.md Finding Emission Contract):

- `role: evaluator_design`
- `defect_kind` -- the slug named in the rubric category (the schema
  validator rejects unknown slugs)
- `diagnosis.what` -- the concrete defect (one sentence)
- `diagnosis.where` -- artifact path + locator
  (`plans/component-contracts.yaml components.router responsibilities[0]` style)
- `diagnosis.why` -- the specific reasoning (NEVER empty; the
  schema validator rejects empty values for this role)
- `affected_artifacts` -- the canonical YAML files the architect
  must edit
- `remediation.root_cause_layer: yaml_contract` (design defects are
  YAML-layer)
- `remediation.fix_steps` -- the actionable edit
- `remediation.re_entry_commands: ["/io-architect"]`

### Step C: SUMMARY LINE

Print exactly one line to stdout:

- If zero findings emitted: `PASS    -- 0 findings emitted`
- If one or more emitted:
  `OBSERVATION -- N findings emitted; first at <path-from-emitter>`

The architect parses this line; per-defect chatter is noise.

### Step D-1: REVOKE CAPABILITY

`bash: uv run python .claude/scripts/capability.py revoke --template io-design-evaluator.A`

Explicit capability revoke. Run whether or not Step B emitted findings -- the alternative is a lingering grant that masks reset-hook behavior until TTL expiry (the 1800s template ceiling and the parent session's `session-end.sh` sweep are defense-in-depth, not a substitute for explicit revoke). Mirrors the io-architect Step J-2 pattern.

### Step D-2: EXIT 0

Always exit 0 -- whether findings were emitted or not. A non-zero
exit is interpreted as evaluator infrastructure failure, not as a
design verdict. Termination and next action are determined at io-architect
Step I (operator-gate), not inside this subprocess.

---

## 3. CONSTRAINTS

- **Read-only on canonical artifacts.** Never write or edit
  `component-contracts.yaml`, `seams.yaml`, or `symbols.yaml`. The architect re-authors them.
- **Write only via emitter.** Findings flow through
  `findings_emitter.emit_finding`. No direct YAML writes to
  `.iocane/findings/`.
- **Allowed tools fence (set by spawn helper):**
  `Bash,Read,Write,Grep,Glob`. `Bash` is required to issue the
  capability grant at Step A-pre and to invoke `findings_emitter`
  (`uv run python ...`); `forbidden-tools.sh`, `rtk-enforce.sh`, and
  `capability-gate.sh` continue to gate it centrally. `Edit` is
  excluded -- the subprocess never mutates canonical artifacts.
- **One defect per Finding.** Related-but-distinct defects emit as
  separate findings, even when surfaced in the same review pass.
- **No halt.** The subprocess never raises a HARD verdict. Single-pass
  per architect attempt; termination and retry authority belong to the
  caller (io-architect Step I operator-gate), not to this subprocess.
