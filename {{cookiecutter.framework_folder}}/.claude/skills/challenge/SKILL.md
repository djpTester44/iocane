---
name: challenge
description: Adversarial stress-test of the current plan. Spawns an Opus sub-agent as Devil's Advocate to surface failure modes, unexamined assumptions, and the strongest argument against proceeding.
---

# CHALLENGE: Adversarial Plan Review

> **Purpose:** Surface what the plan gets wrong or ignores before the human approves it. Findings only -- no fixes, no rewrites.

## When to Use

- Before approving a CDD checkpoint plan (`/io-checkpoint` Step E)
- Before approving any ad-hoc plan produced in plan mode
- Whenever a plan feels "too clean" and you want to pressure-test it

## Execution

Spawn a single **Opus sub-agent** with the following brief:

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

## Output

Present the sub-agent's findings to the user verbatim, framed as input for their decision:

```
CHALLENGE COMPLETE. Review the findings above.

These are adversarial findings, not recommendations. Decide which (if any) warrant plan changes before approving.
```
