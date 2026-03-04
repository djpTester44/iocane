# Execution Plan & Roadmap

## 1. Active Checkpoints
[This section contains the high-level sequential milestones required to complete the PRD. Each Checkpoint (CP) must define the deliverable, not the atomic tasks. Mark as `[x]` when the entire CP is fully validated by `io-loop`.]

* [ ] **CP1: [Foundation/Setup]**
    * Deliverable: Scaffold the `src/core` configuration, define primary Pydantic domain models, and configure the `uv` environment.
* [ ] **CP2: [Core Component A]**
    * Deliverable: Implement the primary interface and logic for [Core Component], routing through `src/domain`.
* [ ] **CP3: [Integration / Component B]**
    * Deliverable: Implement the secondary services in `src/lib` and integrate with external dependencies defined in the PRD.
* [ ] **CP4: [Entrypoint & E2E Verification]**
    * Deliverable: Wire the entrypoint (`src/main.py` or `src/jobs`), finalize dependency injection, and execute full end-to-end tests.

## 2. Macro Milestones & Dependencies
[Track cross-cutting concerns, external API access approvals, or infrastructure provisioning states that block specific Checkpoints.]

* **Upstream Blocker 1:** [e.g., Awaiting staging database credentials. Blocks CP3.]
* **Upstream Blocker 2:** [e.g., Required `uv` package update for Polars integration. Blocks CP2.]

## 3. Remediation Backlog
[CRITICAL: This section is the primary state-driver for `/io-architect` and `/io-handoff`. Any technical debt, architectural shifts, or cleanup tasks discovered during the `io-loop` execution must be logged here. The pipeline will strictly halt sequential CP progress until active backlog items are resolved.]

**Tagging Rules:**
* `[DESIGN]` - Requires `/io-architect` to update `project-spec.md` and generate a new `.pyi` contract.
* `[REFACTOR]` - Requires `/io-architect` to modify existing `.pyi` contracts or architecture graphs.
* `[CLEANUP]` - Handled directly by `/io-handoff` to generate a refactoring task bundle for the `io-loop`.
* `[DEFERRED]` - Explicitly skipped by the pipeline until a later phase.

**Pending Items:**
* [ ] `[TAG]` [Description of the required remediation. e.g., Update the StateStore protocol to handle async connection drops.]
* [ ] `[TAG]` [Description of the required remediation.]

**Resolved Items:**
* [x] `[TAG]` [Description of completed remediation.]