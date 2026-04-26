---
name: artifact-evaluator
description: >-
  Semantic-evaluator methodology for io-architect's canonical artifact set.
  Use when running design / CDT / CT evaluator subprocesses against
  component-contracts.yaml, seams.yaml, symbols.yaml, or test-plan.yaml.
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
  The architect reads them, revises the artifact set, and re-runs the
  upstream gate. Iteration is bounded by the caller (io-architect Step H
  enforces a 5-cycle ceiling).

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

Findings are written via `harness/scripts/findings_emitter.py` --
**never** by writing YAML directly. The emitter centralizes the
filename pattern, sequence disambiguation, and Pydantic round-trip
validation; bypassing it produces unparseable artifacts and breaks the
architect's read path.

```python
from pathlib import Path
import sys

sys.path.insert(0, ".claude/scripts")

from findings_emitter import emit_finding
from schemas import (
    Finding,
    FindingContext,
    FindingDiagnosis,
    FindingRemediation,
    FindingRole,
    RootCauseLayer,
)

finding = Finding(
    role=FindingRole.EVALUATOR_DESIGN,  # or EVALUATOR_CDT / EVALUATOR_CT
    context=FindingContext(cp_id="CP-XX"),
    defect_kind="<slug from rubric reference>",
    affected_artifacts=["plans/<file>.yaml"],
    diagnosis=FindingDiagnosis(
        what="<concrete defect>",
        where="<artifact path + locator>",
        why="<specific reasoning, never the empty string>",
    ),
    remediation=FindingRemediation(
        root_cause_layer=RootCauseLayer.YAML_CONTRACT,
        fix_steps=["<actionable edit>"],
        re_entry_commands=["/io-architect"],
    ),
)
path = emit_finding(finding, repo_root=Path.cwd())
```

The schema enforces:

- `defect_kind` is in the allowed set for the role (rubric drift fails
  loudly at construction).
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
