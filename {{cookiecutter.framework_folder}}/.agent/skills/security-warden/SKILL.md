---
name: security-warden
description: Scans code for vulnerabilities and security antipatterns against OWASP Top 10 and common Python pitfalls. Use during code review, before releases, or when auditing existing code for security issues.
---

# Security Warden

Scan code for vulnerabilities and security antipatterns.

## Workflow

1. **Scan** - Review code against OWASP Top 10 and common Python pitfalls:
   - SQL Injection
   - Hardcoded API Keys
   - Unsafe `pickle` usage
   - Unsanitized inputs
   - Command injection
   - Path traversal

2. **Report** - Flag specific lines with severity levels

## Output Format

```markdown
## Security Scan Report

### Critical
- [file:line] - [vulnerability type] - [description]

### Warning
- [file:line] - [vulnerability type] - [description]

### Info
- [file:line] - [potential issue] - [description]
```

## Required Input

Caller MUST provide (do not fetch):

- `code`: Code to scan (paste content directly)
- `scope`: "full" | "owasp" | "python"

## References

- [OWASP Top 10](references/OWASP_TOP_10.md) - Common web vulnerabilities
- [Python Pitfalls](references/python_pitfalls.md) - Python-specific security issues