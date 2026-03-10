# [directory-name]/

**Layer:** [1-Foundation | 2-Utility | 3-Domain | 4-Entrypoint]
**Owns:** [One sentence — what this directory is responsible for. Observable behaviors only.]

**Public via:**
- `interfaces/[protocol].pyi` — [ProtocolName]

**Must NOT:**
- Import from `[higher-layer-path]/` (layer violation)
- Instantiate [CollaboratorName] — receive via `__init__` injection
- [Any other directory-specific constraint]

**Key files:**
- `[module].py` — [one-line description]
- `[module].py` — [one-line description]
