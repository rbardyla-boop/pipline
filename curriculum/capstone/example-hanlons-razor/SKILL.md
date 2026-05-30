---
name: mental-model-hanlons-razor
description: >
  "Never attribute to malice what can be adequately explained by ignorance, error,
  or incompetence." Deploy when the user is interpreting a bad outcome as deliberate
  or adversarial — especially in debugging, team conflict, or AI failure analysis.
---

# Hanlon's Razor

## When to use
- "Why did it do that? Is it broken on purpose?"
- "They must have known this was wrong"
- "The model is actively trying to confuse me"
- Debugging unexpected behavior
- Interpreting an AI system's failure
- Resolving interpersonal or team friction
- Evaluating AI safety risks ("alignment vs. misalignment")

## Why this model fills a gap in the original 7
The original models handle reasoning about decisions and consequences, but none explicitly
address attribution error — the tendency to assign intent to what is actually noise,
bugs, or knowledge gaps. In AI debugging and safety discussions, this distinction is
load-bearing: a model that "fails" is rarely malicious; it's almost always undertrained,
out-of-distribution, or receiving a prompt it wasn't designed for.

## Execute this prompt

> Before concluding this was deliberate or adversarial, work through the explanation ladder:
>
> 1. **Error hypothesis**: Could this outcome be explained by a simple mistake?
>    What specific bug, gap, or edge case would produce exactly this behavior?
> 2. **Ignorance hypothesis**: Could this be explained by missing information?
>    What would the actor (human or AI) have needed to know to behave differently?
> 3. **Incompetence hypothesis**: Could this be explained by inadequate capability?
>    What skill or training would have prevented this?
> 4. **Intent hypothesis** (only if all three above fail): Only after exhausting
>    the above — is there evidence of deliberate action? What specific behavior
>    is inconsistent with error/ignorance/incompetence and requires intent to explain?
>
> End with: "The most parsimonious explanation is [error/ignorance/incompetence/intent].
> The action this suggests is [investigate the bug / provide information / improve capability / escalate]."

## AI-specific application (important for this curriculum)
When discussing MUSE's failure cases (the 13 tasks where it underperformed):
- Not: "The model was trying to game the benchmark"
- Yes: "The verifier penalized methodology choices that weren't specified in the task"

This is Hanlon's Razor applied to AI evaluation. Students who internalize this
become dramatically better at debugging and AI safety reasoning.

## Chaining
- **Hanlon's Razor → 5 Whys**: Once you've established it's an error/ignorance problem, trace to root cause
- **Hanlon's Razor → Second-Order Thinking**: "If we assume error not malice, what does our response look like second-order?"
