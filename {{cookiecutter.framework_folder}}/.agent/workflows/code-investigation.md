---
description: Investigating code, finding definitions, or understanding errors.
---

# Code Investigation Workflow

Use this workflow whenever you need to:
- Find a class, function, or variable definition.
- Investigate an error message or traceback.
- Understand how a feature is implemented.
- "Look around" the codebase.

## Step 1: Search (The "Wide Net")
**Goal**: Identify *which* files are relevant without reading them.
- **If you have a unique string (error message, specific ID, obscure function name):**
  - Run `grep_search` with the string.
- **If you have a concept ("retry logic", "user authentication"):**
  - Run `codebase_search` with the concept.

2.  **Step 2: Locate (The "Map")**
    **Goal**: Get line numbers for the specific symbol/code you need.
    - **If you have a file path from Step 1:**
      - Run `view_file_outline` on the file. Find the `ClassName` or `function_name`. Note `StartLine` and `EndLine`.

3.  **Step 3: Assessment (The "Landscape")**
    **Goal**: Understand upstream/downstream impact before diving in.
    - **Action**: Run `uv run lint-imports` to check contract compliance.
    - **Visual Exploration**: Run `uv run import-linter explore <package>` (e.g. `lib`) to explore the interactive dependency graph in your browser.
    - **Insight**: identify "Who calls me?" and "Who do I call?".

## Step 3: Contextualize (The "Anchor Check")
**Goal**: Understand the *intent* of the code before reading the implementation.
- **Action:** Check `plans/project-spec.md` for the corresponding **CRC Card** or **Sequence Diagram**.
- **Reason:** This prevents misinterpreting implementation details as requirements.

## Step 4: Read (The "Targeted Look")
**Goal**: Read *only* the relevant code to verify or understand.
- **Action:** Run `view_code_item` (if it's a function/class) or `view_file` with specific ranges.

## Anti-Patterns (Forbidden)
- Running `view_file` on a file > 50 lines without arguments.
- Reading a file to "find" a string (use `grep_search` instead).
- Assuming implementation is correct without checking the Design Anchor in `project-spec.md`.