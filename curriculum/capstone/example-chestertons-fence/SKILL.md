---
name: mental-model-chestertons-fence
description: >
  "Do not remove a fence until you understand why it was built."
  Deploy when someone is about to delete, simplify, or refactor something
  without fully understanding its original purpose. Critical for system design,
  code refactoring, and AI skill pruning decisions.
---

# Chesterton's Fence

## When to use
- "This rule/feature/constraint seems pointless — let's remove it"
- "Why do we still have this? It was probably left in by mistake"
- "The old way was needlessly complicated, let's simplify"
- Refactoring legacy code
- Deciding whether to prune a skill from the Skill Bank (MUSE context)
- Changing a policy, rule, or process that "nobody uses"

## Why this model fills a gap in the original 7
The original models are almost entirely forward-looking (what should I do next?).
Chesterton's Fence is explicitly backward-looking: it demands you understand the history
before you act. This is the model that prevents "bold" refactoring from being reckless.
In the MUSE context, it's the model that governs skill pruning and management.

## Execute this prompt

> Before removing or changing this, answer the history question:
>
> 1. **Who put it here, and when?** What was the context — the constraints,
>    the failures they were preventing, the goal they were pursuing?
> 2. **What failure does it prevent?** What bad thing happens if this isn't here?
>    Can you describe a specific scenario — not "probably something bad" but a named, concrete event?
> 3. **Has the underlying condition changed?** Is the thing this was built to prevent
>    no longer possible? Has the system changed in a way that makes this obsolete?
>    What evidence would convince you the original reason no longer applies?
> 4. **Cost of being wrong**: If you remove it and the original reason still applies,
>    what breaks? Is that reversible?
>
> Verdict: Only proceed with removal if you can answer questions 1 and 2 concretely,
> and if question 3 has a clear affirmative answer backed by evidence.
> "I don't know why it's here" is not clearance to remove it. It is a mandate to find out.

## Direct MUSE connection
The MUSE skill bank has a "forget" operation (prune skills that consistently fail or are unused).
Chesterton's Fence is the model that should govern every prune decision:
- Why was this skill created? What task was it solving?
- Is that task gone, or just temporarily absent?
- What happens if the task reappears and the skill has been pruned?

This makes it uniquely teachable in this curriculum's context.

## Chaining
- **Chesterton's Fence → Opportunity Cost**: Once you understand why the fence exists, evaluate the cost of keeping it vs. removing it with full information
- **Chesterton's Fence → Pre-Mortem**: "We removed it anyway. What went wrong 6 months later?"
