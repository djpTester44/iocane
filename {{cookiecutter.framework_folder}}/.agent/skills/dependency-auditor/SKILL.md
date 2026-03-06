---
name: dependency-auditor
description: Audits project dependencies for issues, outdated packages, unused imports, and known vulnerabilities. Use when reviewing project health, before releases, or when investigating dependency-related issues.
---

# Dependency Auditor

Audit project dependencies for issues and vulnerabilities.

## Workflow

1. **Locate** dependency files (`pyproject.toml`, `requirements.txt`, or `uv.lock`) in the project
2. **Analyze** dependencies:
   - List all direct dependencies with versions
   - Identify outdated packages (compare to latest)
   - Flag unused dependencies (not imported anywhere)
   - Check for known vulnerabilities (CVEs)
3. **Report** findings in a structured markdown audit

## Output Format

```markdown
## Dependency Audit Report

### Outdated Packages
| Package | Current | Latest | Risk |
|---------|---------|--------|------|
| [name] | [ver] | [ver] | [Low/Med/High] |

### Unused Packages
- [package_name]: Not imported in codebase

### Vulnerabilities
- **[CVE-XXXX-XXXX]** ([Severity]): [package] - [description]

### Recommendations
- [ ] Update [package] to [version]
- [ ] Remove unused [package]
- [ ] Address [CVE] in [package]
```

## Required Input

Caller MUST provide:

- `project_root`: Path to project root (skill will locate dependency files)

## Tool Strategy

- `read_file`: pyproject.toml, requirements.txt (small files, read fully)
- `grep_search`: Pattern `^import |^from .* import` to find package usage
- Do NOT use `list_code_usages` (searching for import statements, not symbol references)

## Constraints

- Do NOT modify any files (report only)