---
name: io-adopt
description: Apply Iocane framework to an existing codebase with intelligent content migration and design extraction.
---

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load the planning rules: `view_file .claude/rules/planning.md`
> 2. Load the extraction tool: `.claude/scripts/extract_structure.py`

# WORKFLOW: ADOPT EXISTING REPOSITORY

**Objective:** Configure the Iocane harness for this project, then extract the structural skeleton and reverse-engineer the capabilities of the existing codebase to establish a foundational PRD.

**Context:**

* Scope: Brownfield repository integration. Harness files are assumed to be present (installed via `uvx` before this workflow runs).
* Output: configured harness (`pyproject.toml`, `CLAUDE.md`, `.iocane/`) + `plans/current-state.md` + draft `plans/PRD.md`.

**Procedure:**

### 1. HARNESS CONFIGURATION

#### 1a. Pre-flight gate

* **Check:** Verify `.claude/` exists in the repo root.
* **If missing:** Stop immediately. Output: "Harness not found. Run the iocane install command (`uvx ...`) to pull harness files before running `/io-adopt`." Do not proceed.
* **Check:** Verify `.claude/hooks/` contains `.sh` files.
* **Action:** Make all hooks executable: `bash -c "chmod +x .claude/hooks/*.sh"`

#### 1b. Detect project identity

* **Action:** Read the existing `pyproject.toml` (if present) to extract `[project].name` and `[project].description`.
* **Fallback:** If `pyproject.toml` is absent or fields are empty, read the first `#`-headed line of `README.md` for the project name, and the first non-header paragraph for the description.
* **Store:** Hold `PROJECT_NAME` and `PROJECT_DESCRIPTION` for use in steps 1c and 1d.

#### 1c. Merge pyproject.toml

* **If `pyproject.toml` is absent entirely:** Create it from `.claude/templates/pyproject.toml.template`, substituting `PROJECT_NAME` and `PROJECT_DESCRIPTION`. Skip the merge step.
* **If `pyproject.toml` exists:** Run the deterministic merge script:

  ```bash
  uv run .claude/scripts/merge_pyproject.py --write
  ```

  This script compares the existing file against harness-required config and applies only the missing pieces. It never removes or overwrites existing keys. List-type fields (`ruff select`, `ruff ignore`, dev packages) use union merge. Scalar divergences (e.g. project uses `line-length = 79`) are reported but left unchanged — surface these to the user for manual review after the workflow completes.

#### 1d. Write CLAUDE.md

* **Assumption:** `CLAUDE.md` is absent at this point -- the cookiecutter `pre_gen_project.py` hook archives any pre-existing `CLAUDE.md` to `OLD_CLAUDE.md` before the template is copied.
* **Action:** Run scaffold-claude-md.sh to write the harness-localized CLAUDE.md (unconditional overwrite per the Assumption above):

  ```bash
  bash .claude/scripts/scaffold-claude-md.sh \
    --name "$PROJECT_NAME" \
    --description "$PROJECT_DESCRIPTION"
  ```
* **Merge guidance:** If `OLD_CLAUDE.md` exists and contains project-specific content outside the `## System Context` section (custom rules, project-specific protocols, etc.), surface this in the Step 4 handoff for the user to manually merge. Do not attempt automated merging -- the judgment of what to preserve is the user's call.

#### 1e. Bootstrap directories

* **Action:** `mkdir -p .iocane plans plans/tasks`
* **Note:** Do not overwrite `.iocane/session-start-payload.json` if it already exists.

---

### 2. CURRENT STATE ANALYSIS (Token Protection)

* **Constraint:** You are strictly forbidden from reading full legacy source files in bulk, with two exceptions: (1) files under 200 lines may be read in full, and (2) files matching entrypoint patterns (`main.py`, `app.py`, `cli.py`, `__main__.py`, `manage.py`, `wsgi.py`, `asgi.py`, `server.py`) may be read in full regardless of length. All other files require `extract_structure.py` or targeted line-range reads.
* **Action:** Run `uv run python .claude/scripts/extract_structure.py <dir>` to map the existing classes, function signatures, and data structures.
* **Action:** Create `plans/current-state.md` using the template `.claude/templates/current-state.md`.
* **Goal:** Capture the raw capabilities and data structures of the legacy code efficiently.

#### Step 2a: CONFIG INVENTORY

* **Action:** Glob for `**/*.toml`, `**/*.yaml`, `**/*.yml`, `**/*.json`, `**/*.env*` excluding `.venv/`, `node_modules/`, `.git/`.
* **Action:** Add a `## Configuration Sources` section to `plans/current-state.md` listing each file with a one-line purpose description.

#### Step 2b: WIRING SNAPSHOT

* **Action:** Identify entrypoint files using the pattern list from the token protection constraint above (`main.py`, `app.py`, `cli.py`, `__main__.py`, `manage.py`, `wsgi.py`, `asgi.py`, `server.py`).
* **Action:** Read each entrypoint and catalog: (a) concrete class instantiations, (b) global/module-level mutable state, (c) service-locator patterns.
* **Action:** Add a `## Wiring Snapshot` section to `plans/current-state.md`.
* **Note:** This is descriptive inventory only — Protocols do not exist yet in brownfield repos.

### 3. PRD SYNTHESIS

Dual-source: if the brownfield repo already had a PRD (archived to `OLD_plans/PRD.md` by the `pre_gen_project.py` hook), it is the primary source of intent. Current-state findings augment it via a dedicated reconciliation section. If no archived PRD exists, the current-state analysis becomes the sole source.

**Rule for both branches:** Set `**Clarified:** False` in the new PRD header. Any carryover clarification status from an archived PRD is stale; `/io-clarify` will re-validate.

#### Branch A: `OLD_plans/PRD.md` present (carryover path)

* **Action:** Copy `OLD_plans/PRD.md` verbatim to `plans/PRD.md` as the primary source of intent. Do not rewrite or reshape the user's prose.
* **Action:** Force `**Clarified:** False` in the header (overwrite any existing value).
* **Action:** Append a `## Current State Reconciliation` section at the end of `plans/PRD.md`. This section reports findings from `plans/current-state.md` that relate to the PRD's content -- specifically:
  * Capabilities the PRD describes for which the code shows no evidence.
  * Capabilities the code implements that the PRD is silent on.
  * Domain models, data structures, or config sources observable in the code that the PRD does not reference.
* **Scope:** Keep the reconciliation section gentle and observational. Do not edit or rewrite the carryover PRD content. `/io-clarify` is the correct workflow for resolving divergences with the human.
* **Format note:** The carryover PRD may be in an older format or structure than `.claude/templates/PRD.md`. This is acceptable at this stage. `/io-clarify` normalizes against the current template as part of its work.

#### Branch B: `OLD_plans/PRD.md` absent (reverse-engineer path)

* **Action:** Read `.claude/templates/PRD.md`.
* **Action:** Create `plans/PRD.md` by mapping `plans/current-state.md` into the Iocane-compliant PRD format.
* **Guidance:**
  * Map "Capabilities" -> "User Stories"
  * Map "Data Structures" -> "Domain Models"
  * Map "File Inventory" -> "Constraints"
* **Rule:** Set `**Clarified:** False` in the new PRD header.

#### Future extension point

Other archived plan artifacts (e.g., `OLD_plans/backlog.md`, `OLD_plans/plan.md`, `OLD_plans/seams.md`, `OLD_plans/roadmap.md`) are currently NOT consumed by `/io-adopt`. They remain in the archive for manual reference. If automated consumption of any such artifact is added later, the correct location is this step -- add a new sub-branch for each artifact alongside Branch A and Branch B.

### 4. CATALOG SEEDING

* **Goal:** Author a draft `catalog.toml` enumerating the bounded contexts this project spans. Consumed by `validate_crc_budget.py` (component-contract `domain_concerns` distinct-citation count enforcing the `MAX_DOMAIN_CONCERNS` cap per `decisions.md` D-13).
* **Placement rationale (per `decisions.md` D-16):** This step runs AFTER Step 3 PRD synthesis because `nfr_axes` entries are sourced from PRD NFR content; the other three categories (`data_stores`, `external_systems`, `user_surfaces`) draw from `plans/current-state.md` (already on disk after Step 2). Both inputs must exist before catalog seeding can populate all four categories.

#### Step 4a: REVIEW KIND ENUMS

* **Action:** Read `.claude/catalog-kinds.toml` to learn the allowed `kind` values per category. The merged validation set is `.claude/catalog-kinds.toml` defaults UNIONED with `./catalog-kinds.local.toml` (project-additive extension; optional, gitignored). Entry-level `kind` validation runs at Step 4c against the merged set.

* **Note:** If a kind value needed for this project is absent from harness defaults, add it to `./catalog-kinds.local.toml` (do NOT edit `.claude/catalog-kinds.toml`; that file is harness-shipped and propagates to every consumer). Use the scaffold at `.claude/templates/catalog-kinds.local.toml`.

#### Step 4b: SEED `catalog.toml`

* **Action:** Read `.claude/templates/catalog.toml` for the file shape.
* **Action:** Create `catalog.toml` at the repo root, populated from the four input sources below. Use typed entry names (lowercase, identifier-safe) that match the project's domain language.

  | Category | Source | Inference protocol |
  |---|---|---|
  | `data_stores` | `plans/current-state.md` Configuration Sources section | Connection strings, ORM URLs, DB driver imports → infer `kind` by URL scheme (`postgres://` → `relational_db`, `mongodb://` → `document_db`, `redis://` → `cache` or `key_value_store`, etc.). Name from config key or domain meaning ("primary_db", "session_cache"). |
  | `external_systems` | `plans/current-state.md` Wiring Snapshot section | API client instantiations (`Stripe(...)`, `boto3.client('s3')`, `httpx` clients to named hosts, etc.) → infer `kind` by client class or service host. Set `trust_boundary` per the Rule below (defaults to `false` at `/io-adopt` time -- no roadmap exists yet to mirror). |
  | `user_surfaces` | `plans/current-state.md` Wiring Snapshot section | Entrypoint patterns (`cli.py` → `cli`, FastAPI/Flask app entrypoint → `web_app` or `api`, admin route group → `admin_console`). |
  | `nfr_axes` | `plans/PRD.md` Non-Functional Requirements section | NFR axes named in PRD prose (latency budgets, throughput targets, durability tiers, security boundaries, etc.) → one entry per distinct axis. |

* **Rule for `external_systems.trust_boundary`:** The flag is a forward-looking structured-index mirror of the roadmap's Trust Edges section. The roadmap (`plans/roadmap.md`) remains authoritative; the flag is a structured-index optimization for the Phase 1 roadmap-tier trust-edge gate (`validate_trust_edge_chain.py`) and is NOT itself the source of truth for adversarial-edge declarations. The general rule: set `trust_boundary = true` when the entry's name resolves to the owning component (or backing service) of a `TE-NN` entry written in the same workflow run; otherwise set `false`. **At `/io-adopt` time, no roadmap exists yet (it is authored later by `/io-specify`), so all entries default to `false` here.** Per `decisions.md` D-03 + 00-framework-adoption.md §4.5 row 4, Phase 3 implementation MUST NOT compete with the Phase 1 roadmap-tier gate; the flag never substitutes for the roadmap declaration. Entries are flipped to `true` post-`/io-specify` -- either by the agent at `/io-specify` Step F (the parity step that re-populates `external_systems` once roadmap TEs exist) or by operator review -- on entries the roadmap declares as trust edges.

* **Rule:** Mark `catalog.toml` as a DRAFT in this step's output. The operator must review it before `/io-clarify`. Inferred names, descriptions, and especially `trust_boundary` flags benefit from human judgment about domain language and adversarial-edge classification.

#### Step 4c: VALIDATE

* **Action:** Run the catalog parser to confirm the seeded file parses cleanly against the schema + kind enums:

  ```bash
  uv run python -c "
  import sys; sys.path.insert(0, '.claude/scripts')
  from catalog_parser import load_catalog
  c = load_catalog('catalog.toml')
  print(f'data_stores: {len(c.data_stores)}, external_systems: {len(c.external_systems)}, user_surfaces: {len(c.user_surfaces)}, nfr_axes: {len(c.nfr_axes)}')
  "
  ```

* **Goal:** Confirm round-trip parses; no kind-outside-enum errors; entry names match dict keys.

* **Failure mode:** If validation fails, fix the catalog entries (or extend `./catalog-kinds.local.toml` if the offending kind is project-specific) and re-run before proceeding to Step 5.

### 5. HANDOFF

* **Stop:** Explicitly ask the user to review `plans/PRD.md` AND the archived artifacts before running `/io-clarify`.

* **Archive review (prescriptive, non-blocking):** List the archives created by the `pre_gen_project.py` hook that warrant human review. For each archive present in the repo, name it explicitly and propose how to merge:

  * **`OLD_CLAUDE.md`** (if present) -- diff against the newly-written `CLAUDE.md`. Carry over anything outside the `## System Context` section that represents project-specific rules, protocols, or conventions the user wants to preserve. The System Context section itself should NOT be carried over -- it is replaced by the harness template.
  * **`OLD_AGENTS.md`** (if present) -- review for lessons that are still relevant. Many entries may now be enforced by harness hooks (check `.claude/hooks/` and `.claude/rules/` before carrying forward). Append only lessons that remain undocumented in the harness to the new `AGENTS.md`.
  * **`OLD_plans/`** (if present) -- at minimum check for files beyond `PRD.md` (e.g., `backlog.md`, `roadmap.md`, design notes, diagrams). `/io-adopt` currently only consumes `OLD_plans/PRD.md`; other files are candidates for manual migration if their content is still relevant.

* **Output:**

  ```
  Harness configured and legacy extraction complete.

  Draft PRD created at plans/PRD.md.
    Source: [OLD_plans/PRD.md carryover + current-state reconciliation]  -- if Branch A
            [reverse-engineered from plans/current-state.md]              -- if Branch B

  Draft catalog created at catalog.toml.
    Sources: plans/current-state.md (data_stores, external_systems, user_surfaces)
             plans/PRD.md NFRs (nfr_axes)
    NOTE: external_systems.trust_boundary defaults to false on every entry; the
          roadmap-tier trust-edge gate (validate_trust_edge_chain.py) remains the
          source of truth for adversarial-edge declarations. Flip true ONLY on
          entries the roadmap explicitly declares as trust edges.

  Archived artifacts for review:
    - OLD_CLAUDE.md    (diff against CLAUDE.md; preserve non-System-Context content)
    - OLD_AGENTS.md    (review lessons; skip ones now enforced by hooks/rules)
    - OLD_plans/       (check for files beyond PRD.md worth manual migration)

  REVIEW REQUIRED. Do not proceed until:
    1. plans/PRD.md is approved.
    2. catalog.toml is reviewed (entry names + descriptions + trust_boundary flags).
    3. Archives have been reviewed and anything worth merging has been merged.

  Next: /io-clarify to resolve ambiguities, then /io-init for macro-architecture.
  ```

**Safety Rules:**

* Never delete existing legacy files without approval.
* Do not hallucinate requirements not found in the extracted code skeleton.
* Never overwrite existing `pyproject.toml` sections — append only.
* Never overwrite `.iocane/session-start-payload.json` if it already exists.
