---
name: mental-models-extended
description: >
  The Mental Models Suite, extended by [STUDENT NAME(S)] — [DATE].
  Adds [MODEL NAME] to the original 7 models.
  AUTO-TRIGGERS on the same signals as mental-models, plus: [ADD YOUR NEW SIGNAL HERE].
---

# Mental Models Suite — Student Extension

This file extends the base mental-models skill with one new model.
The original 7 models and their triage entries are preserved below.
Your new model is marked with ★.

---

## TRIAGE PROTOCOL

> Copy the triage table from the base skill here, then add your new row marked ★.

| Signal | Model to Deploy |
|--------|----------------|
| "I don't understand why this keeps happening" / recurring failure | **5 Whys** |
| "I'm about to start a project / launch / ship something" | **Pre-Mortem** |
| "Should I do X or Y" / fork in the road / life decision | **Regret Minimization** |
| "What am I giving up" / time/money/energy tradeoff | **Opportunity Cost** |
| "What will happen if I do this" / policy decision / chain reactions | **Second-Order Thinking** |
| "Everyone says to do X but it feels wrong" / first principles violation | **First Principles** |
| "How do I guarantee success" / positive framing only | **Inversion** — flip it |
| ★ [YOUR TRIGGER SIGNAL HERE] | ★ **[YOUR MODEL NAME]** |
| Hard times / emotional overload / no clear signal | Run **Regret Minimization** first |

---

## ★ MODEL [NUMBER] — [YOUR MODEL NAME]

**Deploy when:** [Describe the exact situation this model handles. Be specific.
What signal or cognitive pattern should trigger this model?
What mistake does the user make WITHOUT this model?]

**Why this is different from existing models:**
[Briefly explain why none of the 7 existing models would handle this situation as well.
This is your justification for why the model needs to exist.]

**Execute this prompt:**

> [Write the prompt the AI should execute when this model is deployed.
> The prompt should be structured, push the user toward clarity, and
> resist vague or easy answers.
>
> Structure:
> 1. **[Step 1 name]:** [What to do + why]
> 2. **[Step 2 name]:** [What to do + why]
> 3. **[Step 3 name]:** [What to do + why]
> 4. **[Step 4 name]:** [What to do + why]
>
> End with: [One closing prompt or insight that crystallizes what the user should now see.]]

---

## OUTPUT FORMAT (extended)

Each model output follows this structure:
1. **Model deployed:** [name] — [one line on why this model fits]
2. **The framework in action:** [structured output per model's template]
3. **Key insight:** [one sentence — the thing the user probably wasn't seeing]
4. **Next move:** [one concrete action or offer to chain a second model]

---

## CHAINING RULES (extended)

> Copy the original chaining rules here, then add at least one new chain involving your model.

**New chains involving ★ [YOUR MODEL NAME]:**
- **[Your model] → [Another model]**: [One sentence on why this pairing is powerful]
- **[Another model] → [Your model]**: [One sentence on when to chain in this direction]

---

## NOTES

**Original 7 models** (full text): See the base skill at `.claude/skills/mental-models/mental-models.skill`
This extension file replaces only the triage table and adds one new model section.
All original model prompts remain unchanged and should be loaded from the base skill.
