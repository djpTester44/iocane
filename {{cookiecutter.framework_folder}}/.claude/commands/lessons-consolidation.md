---
name: lessons-consolidation
description: Analyze `AGENTS.md` for maturity progression, duplication, and generalizable patterns.
---

# WORKFLOW: LESSONS CONSOLIDATION

**Objective:** Analyze `AGENTS.md` for maturity progression, duplication, and generalizable patterns.

**When to Use:** Periodically (e.g., every 3-5 sessions) or when `AGENTS.md` exceeds ~30 entries.

---

## Procedure

### 1. LOAD CONTEXT
- Read `AGENTS.md` (root)
- Read `.github/instructions/AGENTS.instructions.md` (constitution rules)
- Skim `.claude/scripts/check_*.py` for existing automated gates

### 2. CLUSTER ANALYSIS
Group lessons by **root cause**. Common clusters:
- **Navigation** (file reading, search patterns)
- **Design-Code Sync** (CRC, Protocol, spec drift)
- **Testing Discipline** (TDD, regression verification)
- **Documentation Hygiene** (backlog, progress, README)
- **DI / Architecture** (dependency injection, layer violations)

For each cluster with 2+ entries:
- Flag as **Consolidation Candidate** -- assess whether or not to merge into a single, sharper rule
- Identify if a cluster's rule could be expressed as a `check_*.py` gate script

### 3. MATURITY ASSESSMENT
Tag each lesson with its current stage:

| Stage | Meaning | Action |
|-------|---------|--------|
| `observe` | Single occurrence, no rule yet | Keep as-is |
| `pattern` | 2+ occurrences, cluster identified | Merge into single rule |
| `rule` | Codified in `AGENTS.md` or instructions | Check if automatable |
| `gate` | Enforced by a script (`check_*.py`) | Archive from AGENTS.md |

### 4. GENERALIZABILITY SCAN
For each lesson/rule, assess:
- **Project-specific?** References project specific types, files, or architecture (keep in `AGENTS.md`)
- **Generalizable?** Applies to any Python project using this agent framework (flag for extraction)

Output a table:

| Lesson | Stage | Cluster | Generalizable? | Action |
|--------|-------|---------|:--------------:|--------|
| L1 | rule | Navigation | Yes | Extract to template |
| L5 | rule | Design-Code Sync | Yes | Extract to template |

### 5. PROPOSE CHANGES
Present to user for approval:
1. **Merges:** Which lessons to consolidate (show before/after)
2. **Promotions:** Which rules are ready for `.github/instructions/` or `check_*.py`
3. **Extractions:** Which patterns are generalizable (candidate for a shared agent template)
4. **Archives:** Which lessons are now covered by existing gates and can be removed

**Do NOT apply changes without user confirmation.**

---

## Output Format

```markdown
## Consolidation Report - [DATE]

### Clusters Found
- [Cluster Name]: L1, L5, L12 -- [summary]

### Promotion Candidates
- [Lesson] -> [Target] (instruction file or gate script)

### Generalizable Patterns
- [Pattern] -- applies to any [context]

### Proposed AGENTS.md (diff)
[Show the rewritten file or diff]
```

---

## Constraints
- NEVER delete lessons without user approval
- NEVER modify `.github/instructions/` files without user approval
- Treat `AGENTS.md` as append-only until consolidation is approved
