---
description: Generate or refresh the evaluator-facing architectural walkthrough (docs/current-state-walkthrough.md).
---

**Objective:** Generate or update `docs/current-state-walkthrough.md` -- a deep, evaluator-facing architectural summary of the service with code references, Mermaid diagrams, and configuration details.

**When to Use:** After completing a major milestone (checkpoint group), adding significant new capabilities, or when preparing for external review / investor presentation.

**Output File:** `docs/current-state-walkthrough.md`

---

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load the walkthrough template: `view_file .agent/templates/walkthrough.md`
> 2. Run the context generator:
>
> ```bash
> // turbo
> uv run rtk python .agent/scripts/generate_walkthrough_context.py
> ```
>
> 1. Load the existing walkthrough (if it exists): `view_file docs/current-state-walkthrough.md`

## Procedure

### 1. GATHER CONTEXT

Read the context generator output (JSON). It provides:

- **protocols**: All Protocol names, their `.pyi` files, and target implementations
- **settings_keys**: Key configuration values from `settings.yaml`
- **layers**: Architectural layer mapping from `import-linter` config
- **src_structure**: AST-extracted class/function skeletons per source file

Additionally, read these source documents for narrative content:

- `plans/PRD.md` -- Algorithmic definitions and requirements
- `plans/project-spec.md` -- CRC cards and sequence diagrams (Section 6+)
- `settings.yaml` -- Live configuration values

> **[TIP] Token Efficiency:**
> The context generator extracts the structured facts. You only need to read PRD and project-spec for the *narrative* -- the "why" behind the architecture. Do NOT re-read source files that the context generator already summarized.

### 2. GENERATE THE WALKTHROUGH

Follow the template structure in `.agent/templates/walkthrough.md`. For each section:

1. **Read the SOURCE hint** in the template comment to know which documents to reference.
2. **Follow the INSTRUCTIONS** in the template comment for what to include.
3. **Generate rich content** with:
   - Tables comparing component variants (e.g., model types, backend options)
   - Mermaid diagrams for data flow, pipeline stages, and system architecture
   - `file:///` URIs with line ranges pointing to specific code (use `view_file_outline` to get line numbers)
   - Pseudocode for critical algorithms (router logic, selection mechanisms)
4. **Preserve `<!-- manual -->` blocks** if updating an existing walkthrough. These contain hand-written competitive positioning or nuanced explanations that should not be overwritten.

### 3. INJECT CODE REFERENCES

For every component mentioned in the walkthrough:

- Use `view_file_outline` on the implementation file to get accurate line ranges.
- Format as `[ComponentName](file:///absolute/path/to/file.py#L{start}-L{end})`.
- Do NOT use stale line numbers from previous versions -- always re-verify with outline.

### 4. GENERATE SYSTEM DIAGRAM

Build a Mermaid `graph TB` diagram using the context generator's `protocols` and `layers` data:

- Group components by architectural layer (from `import-linter` config).
- Show dependency arrows between components.
- Include all Protocol implementations from the Interface Registry.

### 5. VERIFY

After generating:

1. **Link Check:** Verify that all `file:///` URIs point to existing files:

   ```bash
   // turbo
   .agent/scripts/smart_search.sh -c "file:///" docs/current-state-walkthrough.md
   ```

2. **Diff Review:** If updating an existing walkthrough, present the diff to the user before finalizing.

---

## Constraints

- **Audience is external.** Write for a technical evaluator who has never seen the codebase, not for an internal developer.
- **No internal jargon.** Explain checkpoint names, protocol names, and configuration keys in plain language.
- **No TODO items.** This document describes what IS, not what WILL BE. Future capabilities belong in the PRD.
- **Preserve manual blocks.** Content between `<!-- manual -->` and `<!-- /manual -->` markers is hand-written and must survive regeneration.
- **Version stamp.** Include the PRD version and generation date in the document header.

---

## Document Permissions

| Document | Permission |
|----------|-----------|
| `docs/current-state-walkthrough.md` | Auto-generate (user review of diff for updates) |
| `.agent/templates/walkthrough.md` | Read-only during generation |
