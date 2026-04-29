---
name: artifact-evaluator
description: >-
  Semantic-evaluator methodology for io-architect's canonical artifact set.
  Use when running design / CDT / CT evaluator subprocesses against
  component-contracts.yaml, seams.yaml, or symbols.yaml.
  Carries the verdict-vs-observation discipline, the finding-emission
  contract, and the OBSERVATION-only halt rule shared by every rubric.
  Per-rubric reasoning categories live in references/<rubric>-eval-rubric.md.
  Do NOT use for impl-evaluator (dispatch-agents.sh path; emits .eval.json,
  not findings).
---

# Artifact Evaluator

Apply a rubric to io-architect's canonical artifacts and emit OBSERVATION
findings against any defects detected. The architect reads emitted findings
and revises; this evaluator never halts and never modifies artifacts.

## Verdict vs Observation

The evaluator's verdict surface is binary at the artifact-set level:

- **PASS** -- no findings emitted; printed to stdout. The architect proceeds.
- **OBSERVATION** -- one or more findings emitted to `.iocane/findings/`.
  Single-pass per architect attempt (R2-narrow): the architect halts at
  Step I with findings + canonical artifacts surfaced; the operator
  triages and decides next action. Each re-attempt is a fresh
  /io-architect invocation, not an auto-loop (D-04 clause-5 option a).

OBSERVATION is the only escalation the evaluator authors. There is no
HARD verdict, no halt-the-pipeline path, no architect-bypass channel.
The evaluator is a sensor, not a gate.

## Rubric Dispatch

The caller invokes this skill against a specific rubric:

| Rubric | Reference file | Substage |
|---|---|---|
| design | `references/design-eval-rubric.md` | A4 (built) |
| cdt | `references/cdt-eval-rubric.md` | A5 (planned) |
| ct | `references/ct-eval-rubric.md` | A6 (planned) |

Read the rubric reference for the dispatched rubric. Each rubric lists
its reasoning categories; each category names the `defect_kind` slug
the corresponding finding must carry.

## Finding Emission Contract

Findings are emitted via the `findings_emitter` CLI -- **never** by
writing finding YAML directly to `.iocane/findings/`. The CLI
centralizes the canonical filename pattern (`<role>-<UTC
YYYYMMDDTHHMMSS>-<NNN>.yaml`), sequence disambiguation, and Pydantic
schema validation; bypassing it produces unparseable artifacts and
breaks the architect's read path.

### Emission workflow per finding

1. Author the Finding payload as YAML at a transient path (e.g.,
   `.iocane/findings/.tmp-finding-payload.yaml`) via the Write tool.
   The payload is a single Finding -- one defect per emission.

2. Invoke the emitter CLI:

   ```bash
   uv run python -m findings_emitter --from-yaml <path-to-payload>
   ```

   On success, the CLI prints the absolute path of the written
   canonical findings file on stdout. On failure (payload schema
   error, filesystem error), exit-1 with stderr context.

3. The `validate-yaml.sh` PostToolUse hook independently validates
   the written `.iocane/findings/<role>-<ts>-<seq>.yaml` against
   `FindingFile.model_validate`. The hook is defense-in-depth on the
   emitter's own validation.

### Payload schema (single Finding YAML)

```yaml
role: evaluator_design          # or evaluator_cdt / evaluator_ct
context:
  cp_id: CP-XX
defect_kind: <slug from rubric reference>
affected_artifacts:
  - plans/<file>.yaml
diagnosis:
  what: <concrete defect>
  where: <artifact path + locator>
  why: <specific reasoning, never the empty string>
remediation:
  root_cause_layer: yaml_contract
  fix_steps:
    - <actionable edit>
  re_entry_commands:
    - /io-architect
```

The schema enforces:

- `defect_kind` is in the allowed set for the role (rubric drift fails
  loudly at validation).
- `diagnosis.why` is non-empty for semantic roles (an empty value
  strips the human remediator's only context for the call).
- One Finding per FindingFile -- one observable defect per emission.
  Related-but-distinct defects emit separately, even when surfaced in
  the same review pass.

## Halt Rule

The evaluator never halts. Every code path that ends the subprocess
ends in **exit 0** -- whether findings were emitted or not. The
caller's iteration bound is the only termination authority.

A non-zero exit from this subprocess is a bug, not a verdict. It
means the evaluator crashed mid-emission and the artifact set's
review state is unknown.

## Stdout Discipline

The subprocess prints a single summary line at exit:

```
PASS    -- 0 findings emitted
OBSERVATION -- N findings emitted; first at <path>
```

Per-finding stdout chatter is noise. The findings file is the
authoritative record; stdout signals only the count and the first
path so the caller can grep for follow-on action.
