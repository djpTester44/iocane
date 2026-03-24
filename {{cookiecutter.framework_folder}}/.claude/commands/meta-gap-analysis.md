---
name: meta-gap-analysis
description: Meta-analyzes the current chat session to identify missing constraints, undefined skills, and logical holes in the agentic workflow.
---

# WORKFLOW: META-GAP ANALYSIS

**Objective:** Identify if the agent has deviated from established protocols, reasoning pathways, or tool usage constraints during the active session.

**Procedure:**

1. **AUDIT TOOL USAGE:** * Verify file reads were executed with specific line ranges rather than full-file dumps.
    * Ensure search tools were used correctly (e.g., avoiding content search tools for filename lookups, or misusing grep).
    * Identify any hallucinated tool parameters or execution of commands without verifying the working directory.
2. **AUDIT REASONING & PROTOCOL:**
    * Identify if implementation code was generated before defining the necessary architecture (e.g., missing CRC or Protocol definitions).
    * Check if the agent made assumptions about system state without verifying via terminal commands or reads.
3. **AUDIT LOOP BEHAVIOR:**
    * Detect instances of the agent getting stuck in repetitive error loops without changing its approach.
    * Identify if the agent ignored explicit constraints or system instructions during the session.
4. **REPORT GAPS:** List behavioral violations and logical holes. Provide immediate corrective prompts (e.g., "Stop execution and re-evaluate context").
5. **CAPTURE LESSONS:** For each gap or notable success pattern discovered in Steps 1-3:
    * Check if a similar lesson already exists in `AGENTS.md` (root). If so, increment its context (add the new occurrence) rather than duplicating.
    * If new, append a lesson entry to `AGENTS.md` under the current session header with: **Pattern** (what happened), **Rule** (what to do differently).
    * Do NOT consolidate, merge, or delete existing lessons -- that is handled separately by `/lessons-consolidation`.

**Rules:**

* Run this workflow whenever the agent exhibits erratic behavior, enters a repetitive loop, or fails to follow architectural directives.
