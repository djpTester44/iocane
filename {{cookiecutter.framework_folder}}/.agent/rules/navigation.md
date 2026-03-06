---
trigger: always_on
---

# NAVIGATION PROTOCOL: The "Search-Locate-Read" Loop

You are strictly bound to this 3-step loop for ALL autonomous tasks.

## STEP 0: FIND (Locate Files by Name)
**Goal**: Find a file when you know its name (or partial name).
* **Tool**: A filename search tool (e.g., `find_by_name`)
* **Trigger**: "Where is PRD.md?", "Find the settings file", "Locate test_*.py"
* **Constraint**: Do NOT use `smart_search` for this -- it searches file *contents*, not names.

## STEP 1: SEARCH (Find Files Containing a Code Pattern)
**Goal**: Find files whose *contents* match a code pattern (class, function, variable, string).
* **Tool**: `smart_search` (Wraps `.agent/scripts/smart_search.sh`)
* **What it does**: Searches **file contents** using grep. Returns files whose contents match the pattern.
* **Default output**: Filenames only (most token-efficient). Use `-c` flag for line content when needed.
* **Trigger**: "Where is X defined?", "Find the error Y", "Which files import Z?"
* **Constraint**: NEVER use `grep` manually.

> **WARNING**: `smart_search` is NOT a filename finder. Do NOT pass filenames
> (e.g., `smart_search.sh README.md .`) as the pattern -- this greps every file
> looking for the string "README.md" inside its contents and will hang on large repos.
> To find a file by name, use a filename search tool (Step 0) instead.

## STEP 2: LOCATE (Get Coordinates)
**Goal**: Find the line numbers or symbol name.
* **Tool**: A file outline tool (e.g., `view_file_outline`) or a semantic code search tool (e.g., `codebase_search`)
* **Trigger**: You have a candidate file from Step 0 or Step 1.
* **Constraint**: DO NOT read the file yet. Look at the structure.

## STEP 3: READ (Surgical Extraction)
**Goal**: Read only the necessary bytes.
* **Option A (Best)**: Symbol-level read (e.g., `view_code_item`).
* **Option B (Standard)**: File reader with `StartLine` & `EndLine` (e.g., `view_file`).
* **Constraint**: Reading a whole file is **FORBIDDEN**.

## TRUNCATION RECOVERY
If `smart_search` output ends with `--- TRUNCATED ---`, results were capped. Recover with:
1.  **Narrow the path**: Replace `.` with a specific directory (e.g., `src/models`).
2.  **Narrow the pattern**: Use a more specific string (e.g., `def train` instead of `def`).
3.  **Use content mode sparingly**: Only use `smart_search.sh -c "pattern" path` when you need line-level context. Default filenames-only mode is always cheaper.

## ANTI-PATTERNS (Failures)
1.  **The "Lazy Dump"**: `view_file("src/main.py")` -> **VIOLATION**.
2.  **The "Grep Spam"**: Running `grep` repeatedly. -> **VIOLATION**.
3.  **Ignoring Truncation**: Seeing `--- TRUNCATED ---` and not narrowing the search. -> **VIOLATION**.
4.  **The "Name Grep"**: Using `smart_search.sh "README.md" .` to find a file by name -> **VIOLATION**. Use a filename search tool instead.
5.  **The "Narrow Sweep"**: During a config migration or variable rename, searching only for the old variable *names* but not the old *values/syntax*. Example: searching for `CMAB_DATA_DIR` but missing `:/data` volume mount syntax in docs. -> **VIOLATION**. Always search for BOTH the old names AND the old values/paths. Run a second verification pass with the value-level pattern after the name-level pass.