---
name: mental-model-map-territory
description: >
  "The map is not the territory." Deploy when someone is confusing their model
  of a system with the system itself — especially in AI/ML contexts where the
  benchmark, the training distribution, and the evaluation metric are proxies
  for reality, not reality itself.
---

# Map Is Not the Territory

## When to use
- "The model scores 95% on the benchmark, so it understands X"
- "The tests all pass, so the code is correct"
- "We optimized the metric, so the goal is achieved"
- "Our mental model of this system is accurate"
- Discussing AI evaluation, benchmark gaming, Goodhart's Law
- Any time a proxy is being treated as the thing it represents

## Why this model fills a gap in the original 7
The existing models improve decisions and reasoning, but none of them specifically
address the structural gap between a representation and the thing it represents.
This is THE foundational problem in ML: the model learns a map (the training distribution)
and we deploy it on territory (the real world). When those diverge, everything breaks.

## Execute this prompt

> Before trusting this result, find the gap between the map and the territory:
>
> 1. **What is the map?** What representation, model, metric, benchmark, or test
>    are we using as a proxy for reality? Be specific: what does it measure, and how?
> 2. **What is the territory?** What is the actual reality we care about?
>    What would perfect measurement look like if the map didn't exist?
> 3. **Where does the map distort the territory?**
>    - What does the map omit entirely?
>    - What does the map over-represent?
>    - Under what conditions does the map most diverge from the territory?
> 4. **What am I deciding based on the map, not the territory?**
>    What would change about my decision if I had direct access to the territory?
>
> End with: "The map says [X]. The territory may actually be [Y] because [specific distortion].
> The decision changes / doesn't change because [reason]."

## Direct MUSE connection — use in Lesson 5
SkillsBench is a map. The territory is real-world agent performance.
Specific distortions to discuss:
- Tasks run in Docker containers — not identical to real deployment
- 51 tasks — not representative of all possible tasks
- 5 runs averaged — variance from environment errors excluded
- Verifier uses file checks — misses qualitative output dimensions

Students who understand this are not dismissing the evidence.
They are reading it correctly — with appropriate calibration.
This is what scientific literacy looks like.

## Chaining
- **Map/Territory → Survivorship Bias**: "Which part of the territory is systematically missing from your map?"
- **Map/Territory → Fermi Estimation**: "Given the distortions in the map, estimate what the territory looks like"
- **Map/Territory → Second-Order Thinking**: "We optimized the map. Second order: the territory drifts away from the map we optimized for"
