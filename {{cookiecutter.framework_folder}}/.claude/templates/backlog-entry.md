# Backlog Entry Template

Canonical format for BL entries in `plans/backlog.md`. Three variants exist depending on
the producer. Field order is load-bearing -- parsers use regex on field names.

---

## Standard entry (from triage drain or manual creation)

```markdown
- [ ] **BL-NNN** [TAG] Short description
  - Severity: HIGH | MEDIUM | LOW
  - Component: ComponentName
  - Files: path/to/file.py, path/to/other.py
  - Detail: What the issue is and what to fix
  - Contract impact: None | description of CRC/Protocol change needed
  - Source: CP-NN /io-review YYYY-MM-DD | Split from BL-NNN | gap-analysis YYYY-MM-DD
```

## CI sidecar entry (from ci-sidecar.sh)

```markdown
- [ ] [CI-REGRESSION] tests/path/test_file.py::test_name -- new failure after wave merge
  - Source: ci-sidecar post-wave
  - Pre-wave commit: <sha>
  - Post-wave commit: <sha>
  - Error: <error message>
```

```markdown
- [ ] [CI-COLLECTION-ERROR] tests/path/test_file.py -- new collection error after wave merge
  - Source: ci-sidecar post-wave
  - Pre-wave commit: <sha>
  - Post-wave commit: <sha>
  - Error: <error message>
```

CI entries get `**BL-NNN**` stamped by `assign-backlog-ids.sh` after write. They
intentionally omit Severity/Component/Detail -- triage enriches these fields during
classification.

---

## Annotation fields (appended by triage or downstream workflows)

```markdown
  - Routed: CP-NNRN (YYYY-MM-DD)
    - '/io-checkpoint ...' | '/io-architect ...'
  - Blocked: BL-NNN
  - Triaged: YYYY-MM-DD (reason)
  - Split: BL-NNN, BL-NNN
```

Rules:
- One `Routed:` annotation per item, with exactly one prompt line
- Prompts wrapped in single quotes, copy-pasteable
- `Blocked:` references the BL-ID of the prerequisite item
- `Split:` only appears on `[x]` items (the original that was split)

---

## Parser contract

Field regexes used by `backlog_parser.py`, `auto_checkpoint.py`, and `auto_architect.py`:
- BL anchor: `\*\*(BL-\d{3})\*\*`
- Tag: `\[(CLEANUP|TEST|DESIGN|REFACTOR|DEFERRED|CI-REGRESSION|CI-COLLECTION-ERROR|CI-EXTERNAL)\]`
- Severity: `^\s+-\s+Severity:\s+(\w+)`
- Routed: `^\s+-\s+Routed:\s+(CP-\d+R\d+)`
- Blocked: `^\s+-\s+Blocked:`
- Prompt: line containing `/io-checkpoint` or `/io-architect`
