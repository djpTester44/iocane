---
name: code-navigation
description: Efficiently finding, querying, and reading code without token waste.
---

# Code Navigation Skill

This skill defines the optimal way to explore the codebase. You should use this skill whenever you need to:
- Find where a function, class, or variable is defined.
- Trace the source of an error in a traceback.
- Understand how a specific feature is implemented.
- Inspect file contents for review or modification.

## 1. The Golden Rule: "Search, Locate, Read"

The most common mistake is to "Read" before you "Locate". You must follow this sequence:

### Step 1: SEARCH (Find Candidates)
**Do not** guess file paths. Use search tools to find the right files.

-   **I have a unique string** (e.g., `ValueError: invalid_mode`, `def process_batch`):
    -   Use `grep_search` with the string.
    -   *Why?* It's fast, cheap, and precise.

-   **I have a concept** (e.g., "retry logic", "user authentication"):
    -   Use `codebase_search` with the concept concept.
    -   *Why?* It finds semantic matches even if keywords differ.

### Step 2: LOCATE (Get Coordinates)
**Do not** read the whole file to find a function.

-   **I have a file path** (e.g., `src/models/creative.py`):
    -   Use `view_file_outline` on the file.
    -   *Action*: Read the outline. Find the definition you need. Note the `StartLine` and `EndLine`.

### Step 3: READ (Surgical Extraction)
**Do not** dump 500 lines when you need 50.

-   **I have the coordinates**:
    -   Use `view_file` with `StartLine` and `EndLine`.
    -   *OR* use `view_code_item` if you have the symbol name.

---

## 2. Examples

### Good Pattern: Fixing a Bug
1.  **User**: "Fix the `validate_matrix` function in `src/models/creative.py`."
2.  **Agent**: `view_file_outline(AbsolutePath=".../src/models/creative.py")`
3.  **Output**: `validate_matrix` is on lines 45-60.
4.  **Agent**: `view_file(AbsolutePath=".../src/models/creative.py", StartLine=45, EndLine=60)`
5.  **Agent**: *Reads code, plans fix.*

### Bad Pattern: The "Panic Read"
1.  **User**: "Fix `validate_matrix` in `src/models/creative.py`."
2.  **Agent**: `view_file(AbsolutePath=".../src/models/creative.py")` -> **VIOLATION**
    -   *Critique*: You read the whole file without checking where the function is. This wastes tokens.

### Good Pattern: Investigating an Error
1.  **User**: "Where is `InvalidModeError` raised?"
2.  **Agent**: `grep_search(Query="InvalidModeError", ...)`
3.  **Output**: Found in `src/lib/errors.py` line 20 and `src/models/router.py` line 88.
4.  **Agent**: `view_file(AbsolutePath=".../src/models/router.py", StartLine=80, EndLine=100)`

---

## 3. Self-Correction Checklist

Before calling `view_file`:
1.  [ ] Did I try `view_file_outline` first?
2.  [ ] Do I know the specific lines I need?
3.  [ ] Is this file small enough (< 50 lines) to read entirely?

If you answer **NO** to any of these, **STOP**. Use a search or outline tool first.