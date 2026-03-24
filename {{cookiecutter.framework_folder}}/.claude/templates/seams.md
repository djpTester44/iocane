# Integration Seams

> **Purpose:** Agent reference during planning and review workflows. Describes the
> construction-time DI wiring and external terminals for each component. Complements
> CRC cards (`plans/project-spec.md`) and Protocol interfaces (`interfaces/*.pyi`).

---

## Schema Legend

| Field | Definition |
|-------|------------|
| **Receives (DI)** | Dependencies injected at construction time via `__init__` parameters. These must exist before the component can be instantiated. |
| **External terminal** | A system **outside the application boundary** that this component directly owns a connection to — meaning it holds and manages the connection lifecycle (open, use, pool, close). Examples: a database session, an S3 client, an HTTP client to Vault. This is distinct from calling other internal components. Layer 3 (Domain) components have no external terminals because they receive pre-wired Layer 2 clients via DI — they invoke those clients at runtime but do not own the underlying connections. |
| **Key failure modes** | Observable failure signals at this component's boundary — exception types raised, silent failures, or cascade behavior. Used by `/io-checkpoint` for CT assertion design and `/io-review` for error-handling verification. |
| **Backlog refs** | Active structural issues from `plans/backlog.md`. Not populated in compiled task files by `/io-plan-batch` (backlog remediation is a separate workflow concern). |

---

## Layer 1 — Foundation

---

## Layer 2 — Utility

---

## Layer 3 — Domain

---

## Missing Connectivity Test Seams

| CT ID | Seam | Status |
|-------|------|--------|
