# OWASP Top 10 Quick Reference

## A01: Broken Access Control

- Missing authorization checks
- IDOR (Insecure Direct Object References)
- Privilege escalation

## A02: Cryptographic Failures

- Weak algorithms (MD5, SHA1 for passwords)
- Hardcoded secrets
- Missing encryption for sensitive data

## A03: Injection

- SQL Injection
- Command Injection
- LDAP Injection
- XSS (Cross-Site Scripting)

## A04: Insecure Design

- Missing threat modeling
- Lack of input validation
- Business logic flaws

## A05: Security Misconfiguration

- Default credentials
- Verbose error messages
- Unnecessary features enabled

## A06: Vulnerable Components

- Outdated dependencies
- Known CVEs
- Unmaintained libraries

## A07: Authentication Failures

- Weak passwords allowed
- Missing brute-force protection
- Session fixation

## A08: Data Integrity Failures

- Unsafe deserialization (`pickle`, `yaml.load`)
- Missing integrity checks
- Unsigned updates

## A09: Logging Failures

- Missing security event logging
- Sensitive data in logs
- Log injection

## A10: SSRF (Server-Side Request Forgery)

- Unvalidated URLs
- Internal network access
- Cloud metadata exposure