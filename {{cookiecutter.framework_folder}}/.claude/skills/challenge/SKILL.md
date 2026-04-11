---
name: challenge
description: Adversarial stress-test of the current plan. Spawns two Opus sub-agents as Devil's Advocates -- one broad, one targeted -- to surface failure modes, unexamined assumptions, and the strongest argument against proceeding.
---

# CHALLENGE: Adversarial Plan Review

> **Purpose:** Surface what the plan gets wrong or ignores before the human approves it. Findings only -- no fixes, no rewrites.

## When to Use

- Before approving a CDD checkpoint plan (`/io-checkpoint` Step E)
- Before approving any ad-hoc plan produced in plan mode
- Whenever a plan feels "too clean" and you want to pressure-test it

## Execution

Spawn two **Opus sub-agents** in parallel with the briefs below. The broad scan explores freely with no directional priming; the targeted scan applies specific failure-category lenses. Present both outputs.

### Broad scan

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

### Targeted scan

```
You are a Devil's Advocate reviewing a plan. Your job is to find what breaks, not to help. You are FORBIDDEN from suggesting improvements, alternative designs, or rewrites. You surface problems -- the human decides what to do about them.

Read the plan from the current conversation context.

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

## Output

Present both sub-agents' findings to the user, labeled by scan type:

```
--- BROAD SCAN ---
[broad scan findings]

--- TARGETED SCAN ---
[targeted scan findings]

CHALLENGE COMPLETE. Two independent adversarial reviews above.

These are adversarial findings from different angles, not recommendations. Decide which (if any) warrant plan changes before approving.
```
