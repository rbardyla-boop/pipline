---
name: mental-model-survivorship-bias
description: >
  Detects when a conclusion is being drawn only from visible successes while
  ignoring the silent majority that failed. Critical for AI/ML reasoning,
  product decisions, and "do what worked for them" advice.
---

# Survivorship Bias

## When to use
- "Everyone who succeeded did X, so I should do X"
- "Our best-performing models all have Y in common"
- "This approach worked — let's scale it"
- "Here's what the top students/companies/products did"
- Evaluating any pattern drawn from a filtered, non-random sample

## Why this model fills a gap in the original 7
None of the original models address the distortion introduced by *what you're not seeing*.
First Principles questions assumptions but doesn't specifically target invisible data.
This model is specifically about the missing negative cases that weren't observed.

## Execute this prompt

> Before acting on this pattern, we need to find the graves.
>
> Structure:
> 1. **Who got filtered out?** What samples, cases, or attempts are absent from the dataset
>    you're reasoning from? Why are they absent? (Failure? Irrelevance? Deliberate selection?)
> 2. **What would the full picture look like?** If you included all the cases that didn't make
>    it into your sample, how would the pattern change?
> 3. **Is the mechanism real?** Even if X correlates with success in your sample,
>    is there a causal reason X leads to success — or did both X and success have a common cause?
> 4. **Decision revision:** Given the full picture, does the original recommendation still hold?
>    If yes, why is it robust? If not, what changes?
>
> End with: "The conclusion holds / does not hold once you account for [the filtered cases].
> The real pattern is: [revised insight]."

## Capstone notes for students
This model is particularly powerful paired with Lesson 5 (SkillsBench evidence).
Ask: of the 51 tasks MUSE was evaluated on, which ones were excluded? Why?
What would the results look like if the failed tasks were included differently?
