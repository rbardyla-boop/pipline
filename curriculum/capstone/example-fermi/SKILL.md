---
name: mental-models-fermi
description: >
  Reference implementation of the capstone extension pattern.
  Adds MODEL 8: Fermi Estimation to the Mental Models Suite.
  Shows teachers what a complete, graded-A capstone looks like.
  Students should NOT copy this — it is here for teacher reference only.
---

# Mental Models Suite — Fermi Estimation Extension (Reference)

---

## TRIAGE PROTOCOL (extended)

| Signal | Model to Deploy |
|--------|----------------|
| "I don't understand why this keeps happening" | **5 Whys** |
| "I'm about to start / launch / ship" | **Pre-Mortem** |
| "Should I do X or Y" / life decision | **Regret Minimization** |
| "What am I giving up" / tradeoff | **Opportunity Cost** |
| "What will happen if I do this" / chain reactions | **Second-Order Thinking** |
| "Everyone says to do X but it feels wrong" | **First Principles** |
| "How do I guarantee success" | **Inversion** |
| ★ "How big is this problem?" / "Is it worth solving?" / "How many...?" / "What order of magnitude...?" / scope uncertainty before committing effort | ★ **Fermi Estimation** |
| Hard times / overload | **Regret Minimization** first |

---

## ★ MODEL 8 — FERMI ESTIMATION

**Deploy when:** The user is uncertain about the scale of a problem before deciding
whether to invest effort in it. Common signals: "How many X are there?", "Is this
a big deal or a small deal?", "How long would this take?", "Is it even worth trying?"
The user is about to commit resources based on gut feeling rather than an order-of-magnitude check.

**Why this is different from existing models:**
Existing models handle *how to decide* and *how to avoid failure* — but none of them
handle *whether the problem is worth the resources*. A Pre-Mortem assumes you're committed.
Opportunity Cost assumes you know the scale. Fermi Estimation answers scale questions
before commitment, preventing both over-investment in tiny problems and under-investment in big ones.

**Execute this prompt:**

> We're going to estimate the scale of this before committing anything.
> Precise numbers aren't the goal — order of magnitude is.
> Being wrong by 2x is fine. Being wrong by 100x is what we're trying to avoid.
>
> Structure:
> 1. **Anchor**: What one fact do we know for certain that touches this problem?
>    (A number, a rate, a time, a count — something real we can start from.)
> 2. **Chain**: Build a multiplication chain from the anchor to the answer.
>    Each step should be a rough estimate. Show the math, even if it's ugly.
> 3. **Sanity check**: Does the answer feel right? What would have to be true
>    for it to be 10x bigger? 10x smaller? Are either of those plausible?
> 4. **Decision threshold**: Given this estimate, is the problem big enough to
>    justify the effort being considered? What does this change about the plan?
>
> End with: "Your estimate is [X]. You could be off by a factor of [Y].
> At the low end it's [X/Y] — still worth it? At the high end it's [X×Y] — still tractable?"

---

## CHAINING RULES (extended)

Strong chains involving ★ Fermi Estimation:
- **Fermi → Opportunity Cost**: estimate scale first, then evaluate what you're giving up relative to it
- **Fermi → Pre-Mortem**: once you know the scale, the failure modes become concrete
- **Fermi → Second-Order Thinking**: "If there are 10M users affected, what does the second-order look like?"

Never chain:
- **Fermi → Regret Minimization**: Fermi is pre-commitment and quantitative; Regret Min is post-analysis and emotional. Going from numbers to feelings usually muddies both.

---

## OUTPUT FORMAT

1. **Model deployed:** Fermi Estimation — [one line on why scale uncertainty was the issue]
2. **The framework in action:** [Anchor → chain → sanity check → decision threshold]
3. **Key insight:** [The number that surprised them, or the threshold that changed the decision]
4. **Next move:** [One action, or offer to chain into Opportunity Cost or Pre-Mortem]
