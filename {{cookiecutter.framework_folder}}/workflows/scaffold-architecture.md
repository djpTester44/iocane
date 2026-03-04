---
description: Onboard project to use import-linter for architectural enforcement.
---

> **[CRITICAL] CONTEXT LOADING**
> Load: `plans/project-spec.md` (to read Layer Mapping)

# WORKFLOW: SCAFFOLD ARCHITECTURE (import-linter)

**Objective:** Onboard a project to use `import-linter` for architectural enforcement.

**Context:**
* Target: `pyproject.toml`
* Tool: `import-linter`

**Procedure:**

1.  **IDENTIFY LAYERS:**
    * **Action:** Read `plans/project-spec.md` (Section: Architecture Layer Mapping).
    * **Logic:** Identify the actual physical directories for:
        * Layer 1: Foundation
        * Layer 2: Utility
        * Layer 3: Domain
        * Layer 4: Entrypoint

2.  **GENERATE CONFIG:**
    * Add `[tool.importlinter]` section to `pyproject.toml`.
    * **Define Layers:** Create a "Iocane Layered Architecture" contract using the specific directory names found in Step 1.
    * **Pattern:**
    ```toml
    [tool.importlinter]
    root_packages = ["src"]

    [[tool.importlinter.contracts]]
    name = "Iocane Layered Architecture"
    type = "layers"
    layers = [
        "src.[Entrypoint_Dir]",
        "src.[Domain_Dir]",
        "src.[Utility_Dir]",
        "src.[Foundation_Dir]"
    ]
    ```

3.  **VERIFY:**
    * Run `uv run lint-imports`.
    * If failures exist, either fix them or add them to `ignore_imports` with a technical debt tracking comment.

4.  **OUTPUT:**
    * "Architecture enforcement configured in pyproject.toml."