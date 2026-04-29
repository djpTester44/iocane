---
name: challenge
description: Adversarial stress-test of the current plan. By default spawns one Opus sub-agent as a targeted Devil's Advocate to surface failure modes, unexamined assumptions, and the strongest argument against proceeding. Pass --broad for a broad-only scan, or --both for broad + targeted in parallel. Findings only -- no fixes, no rewrites.
---

# CHALLENGE: Adversarial Plan Review

> **Purpose:** Surface what the plan gets wrong or ignores before the human approves it. Findings only -- no fixes, no rewrites.

## When to Use

* Before approving a CDD checkpoint plan (`/io-checkpoint` Step E)
* Before approving any ad-hoc plan produced in plan mode
* Whenever a plan feels "too clean" and you want to pressure-test it

## Flags

| Flag | Behavior |
|------|----------|
| *(none)* | **Targeted only** (default) — one scan with specific failure-category lenses |
| `--broad` | **Broad only** — one scan with unconstrained directional exploration |
| `--both` | **Broad + Targeted** — both scans in parallel, full dual-agent review |

When the user provides prose alongside `--targeted` (or the default), pass that prose to the targeted agent as additional directional context (see targeted brief below).

## Execution

### Determining which agents to spawn

```
if flag == "--both":
    spawn broad agent + targeted agent in parallel
elif flag == "--broad":
    spawn broad agent only
else:  # default or --targeted
    spawn targeted agent only
    if user provided prose: pass it as additional context (see targeted brief)
```

---

### Broad scan agent brief

```
You are a Devil's Advocate reviewing a plan. Your job is to find what breaks, not to help. You are FORBIDDEN from suggesting improvements, alternative designs, or rewrites. You surface problems -- the human decides what to do about them.

Read the plan from the current conversation context, then deliver exactly three sections:

## Failure Modes

The top 3 most likely failure modes. For each:
- What breaks
- What triggers it
- Blast radius (who/what is affected and how far the damage spreads)

Rank by likelihood, not severity. Skip failure modes that require multiple unlikely conditions to align.

## Unexamined Assumptions

What the plan takes for granted without evidence. These are claims the plan treats as true but never validates -- implicit dependencies, untested environmental conditions, or "this will just work" leaps.

List each assumption and state what happens if it is wrong.

## Strongest Argument Against

The single best case for NOT proceeding with this plan as-is. This is not a list -- it is one coherent argument. If you had 60 seconds to convince someone to pause, what would you say?

---

HARD CONSTRAINTS:
- Do NOT suggest fixes, improvements, or alternative approaches
- Do NOT rewrite any part of the plan
- Do NOT soften findings with "but overall the plan is solid" hedging
- If the plan is genuinely sound, say so briefly and explain why the obvious attack vectors do not apply
```

---

### Targeted scan agent brief

```
You are a Devil's Advocate reviewing a plan. Your job is to find what breaks, not to help. You are FORBIDDEN from suggesting improvements, alternative designs, or rewrites. You surface problems -- the human decides what to do about them.

Read the plan from the current conversation context.

{{TARGETED_CONTEXT}}

Plans fail in predictable ways that are easy to overlook: steps that execute out of order or concurrently when the plan assumed sequence; check-then-act gaps where a concurrent actor invalidates the check before the act; data crossing a trust boundary with identifiers the caller controls; dependencies that are slow, down, or returning stale results. Not every plan has all of these -- but when one applies and is missed, it is usually the thing that breaks production. Look there first, then look everywhere else.

Deliver exactly three sections:

## Failure Modes

The top 3 most likely failure modes. For each:
- What breaks
- What triggers it
- Blast radius (who/what is affected and how far the damage spreads)

Rank by likelihood, not severity. Skip failure modes that require multiple unlikely conditions to align.

## Unexamined Assumptions

What the plan takes for granted without evidence. These are claims the plan treats as true but never validates -- implicit dependencies, untested environmental conditions, or "this will just work" leaps.

List each assumption and state what happens if it is wrong.

## Strongest Argument Against

The single best case for NOT proceeding with this plan as-is. This is not a list -- it is one coherent argument. If you had 60 seconds to convince someone to pause, what would you say?

---

HARD CONSTRAINTS:
- Do NOT suggest fixes, improvements, or alternative approaches
- Do NOT rewrite any part of the plan
- Do NOT soften findings with "but overall the plan is solid" hedging
- If the plan is genuinely sound, say so briefly and explain why the obvious attack vectors do not apply
```

**Note on `{{TARGETED_CONTEXT}}`:** Replace this placeholder before spawning the agent:
- If the user provided prose with their invocation (e.g. `/challenge --targeted focus on the auth boundary`), inject it as: `The user has flagged a specific area of concern: "<their prose>". Weight your investigation toward this area, but do not ignore other critical failure modes.`
- Otherwise, omit the line entirely.

---

## Output

### Targeted only (default / `--targeted`)

```
--- TARGETED SCAN ---
[targeted scan findings]

CHALLENGE COMPLETE. One adversarial review above.

These are adversarial findings. Decide which (if any) warrant plan changes before approving.
```

### Broad only (`--broad`)

```
--- BROAD SCAN ---
[broad scan findings]

CHALLENGE COMPLETE. One adversarial review above.

These are adversarial findings. Decide which (if any) warrant plan changes before approving.
```

### Both (`--both`)

```
--- BROAD SCAN ---
[broad scan findings]

--- TARGETED SCAN ---
[targeted scan findings]

CHALLENGE COMPLETE. Two independent adversarial reviews above.

These are adversarial findings from different angles, not recommendations. Decide which (if any) warrant plan changes before approving.
```

## Follow-up prompt (all modes)

After presenting output, immediately call `sendPrompt` to route the follow-up back to the orchestrating agent:

```javascript
sendPrompt("Review the output of the adversarial challenge against your plan and provide feedback and suggestions.")
```

This fires automatically — do not ask the human first, do not narrate it.