# Test Scenarios — [YOUR MODEL NAME]

**Skill**: mental-models-extended  
**Tester**: [Student name(s)]  
**Date**: [Date]

---

## Why Tests Matter

The MUSE paper only registers a skill into the Skill Bank *if its tests pass*.
A skill that deploys in the wrong situation — or produces wrong outputs — is
worse than no skill: it gives false confidence.

Your job: write 3 scenarios that would tell you whether your model is working.

---

## Scenario 1 — POSITIVE TEST (Your model should trigger)

**Signal phrase**: "[Write the exact phrasing a user might say that should trigger YOUR model]"

**Full context**:
> [Write 2–3 sentences describing the situation. Make it realistic — something
> a high school student, a manager, or someone making a real decision might actually face.]

**Expected triage result**: [YOUR MODEL NAME]

**Why this model and not another**:
> [One sentence: what makes this situation specifically suited to your model,
> and why the closest alternative model would be worse here.]

**Expected output structure** (not the full answer — just the shape):
- Step 1 should produce: [describe what kind of output]
- Step 2 should produce: [describe what kind of output]
- Step 3 should produce: [describe what kind of output]
- Key insight should be: [describe the class of insight, not the specific answer]

**Test result**: [ ] PASS / [ ] FAIL  
**Notes**: [What actually happened when you ran this? What was surprising?]

---

## Scenario 2 — NEGATIVE TEST (Your model should NOT trigger)

This test verifies that your model doesn't over-trigger on situations that
belong to a different model. Over-triggering is a real failure mode — it means
your triage signal is too broad.

**Signal phrase**: "[Write a phrase that SOUNDS like it could trigger your model but actually belongs to a different one]"

**Full context**:
> [2–3 sentence situation that seems related to your model but where an existing model handles it better.]

**Expected triage result**: [DIFFERENT MODEL — specify which one]

**Why NOT your model**:
> [One sentence: what makes this situation belong to the other model instead.]

**Test result**: [ ] PASS (triage correctly chose the other model)  / [ ] FAIL (your model triggered when it shouldn't have)  
**Notes**:

---

## Scenario 3 — EDGE CASE TEST (Your model is the right choice, but it's not obvious)

This is the hardest test. Pick a situation where:
- The user's phrasing doesn't obviously match your trigger signal
- But your model is genuinely the best fit
- Another model might seem more appropriate at first glance

**Signal phrase**: "[Subtle or indirect phrasing that your model should catch]"

**Full context**:
> [2–3 sentences. Make this harder than Scenario 1.]

**Expected triage result**: [YOUR MODEL NAME]

**Why this is tricky**:
> [One sentence: what makes this hard for the triage protocol to get right.]

**What the triage protocol needs to detect**:
> [One sentence: what underlying pattern (not just the surface phrasing) your
> triage entry needs to be sensitive to in order to catch this case.]

**Test result**: [ ] PASS / [ ] FAIL  
**Notes**:

---

## Overall Test Summary

| Scenario | Expected | Got | Result |
|---|---|---|---|
| 1 — Positive | [Your model] | [What happened] | PASS / FAIL |
| 2 — Negative | [Other model] | [What happened] | PASS / FAIL |
| 3 — Edge case | [Your model] | [What happened] | PASS / FAIL |

**Overall verdict**: [ ] All pass — skill is ready for the bank  
**Refinements triggered by test failures**: [List any changes you made to SKILL.md as a result of testing]
