# Layer Directory Map

Canonical mapping from layer number to `src/` root directory. All component
`file:` paths must be rooted under the directory registered for their layer.

| Layer | Name        | `src/` root   | Purpose                                              |
|-------|-------------|---------------|------------------------------------------------------|
| 1     | Foundation  | `src/core/`   | Config, constants, global types, primitives          |
| 2     | Utility     | `src/lib/`    | Stateless clients, adapters, external integration    |
| 3     | Domain      | `src/domain/` | Business logic, orchestrators; receives L1/L2 via DI |
| 4     | Entrypoint  | `src/jobs/`   | Composition roots; wires L2/L3 collaborators via DI  |

**Default: flat file under the layer root.** A single-file component belongs
directly under its layer root — `src/domain/pipeline_parser.py`, not
`src/domain/pipeline_parser/pipeline_parser.py`. One-directory-per-component
is always wrong when only one file lives in it.

**Sub-directories only for coherent sub-packages.** Create a sub-directory
under a layer root only when multiple related files form a coherent module
(e.g. `src/domain/connectors/` housing `postgres.py`, `s3.py`, `kafka.py`).
A top-level `src/<name>/` directory that is not one of the four roots above
is always wrong.

---

## Import-linter consequence

`compose_importlinter_contracts.py` derives each component's package from
`parts[1]` of its `file:` path. A component at Layer 3 filed under
`src/auth/service.py` produces package `auth` — a peer sibling, not a member
of `domain`. This generates spurious independence contracts and breaks the
layer-hierarchy contract. Components must live under their layer root so
`parts[1]` resolves to the correct package.
