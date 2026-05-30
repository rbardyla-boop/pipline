# Capstone Project Guide — Extend the Mental-Models Skill

**Duration**: 2–3 class periods + homework  
**Deliverable**: A new mental model added to the Mental Models Suite, walked through the full MUSE lifecycle  
**Presentation**: 5 minutes per team + Q&A

---

## The Assignment

The mental-models skill currently has 7 models. It is missing some. Your job is to
add one more — and to do it the right way: the MUSE way.

You are not writing a prompt. You are authoring a lifecycle-managed skill artifact.
When you're done, a different AI agent (or a future student) should be able to pick
up your work and immediately benefit from it, without starting from scratch.

---

## Step 0: Choose Your Model (Opportunity Cost Analysis)

Before you write a single line, use the Opportunity Cost model from the skill itself.

**Run this prompt on the class's live skill instance**:
> "I'm deciding which mental model to add to the Mental Models Suite.
> My options are [your top 3 ideas]. Map what I'm giving up by choosing each one,
> what the highest-value use of my effort is, and which choice compounds most over time."

You must document your reasoning. The Opportunity Cost analysis is a required deliverable.

**Good candidates for new models** (choose one, or propose your own):

| Model | When to deploy | Why it's missing |
|---|---|---|
| Fermi Estimation | "How big is this problem? Is it worth solving?" | Scope uncertainty |
| Survivorship Bias | "Everyone who succeeded did X, so I should too" | Hidden failures |
| Hanlon's Razor | "Why did this go wrong — malice or mistake?" | Attribution errors |
| The Map Is Not The Territory | "My model of reality is not reality" | Overconfidence in plans |
| Chesterton's Fence | "Should we remove this rule/feature?" | Premature deletion |
| Parkinson's Law | "Why does every project expand to fill available time?" | Deadline reasoning |

---

## The MUSE Lifecycle Checklist (Your Deliverable)

Complete each stage. Each stage has a required artifact.

### Stage 1: Creation

**Deliverable**: `starter-skill/SKILL.md` — filled in with your new model

Requirements:
- [ ] Detection signal added to the Triage Protocol table
- [ ] Model section written following the existing format (When/Deploy/Execute/Structure)
- [ ] Output format section updated to include your model

**The creation test**: Give your model a scenario. Does it produce a useful,
structured output? If not, revise before moving to Stage 2.

---

### Stage 2: Evaluation

**Deliverable**: `starter-skill/tests/scenarios.md` — 3 test scenarios

For each scenario, document:
- The input situation (signal phrase + context)
- Which model the triage protocol should select (and why)
- The expected output structure (not the full answer — the structure)
- Pass/fail: did your model produce the right structure?

Requirements:
- [ ] At least 3 test scenarios
- [ ] At least 1 scenario where your model is the RIGHT choice
- [ ] At least 1 scenario where a DIFFERENT model is the right choice (test that triage doesn't over-trigger your model)
- [ ] Pass/fail verdict documented for each

**Why this matters**: MUSE only registers a skill into the bank if tests pass.
You're doing the same thing. A skill that deploys in the wrong situation
is worse than no skill at all.

---

### Stage 3: Memory

**Deliverable**: `starter-skill/.memory.md` — what you learned building and testing this model

Requirements:
- [ ] At least 2 "lessons learned" entries (things that surprised you, failure modes you found, quirks of your model)
- [ ] At least 1 "improvement idea" (something you'd change if you had more time)
- [ ] At least 1 entry about when NOT to use your model (edge cases, false triggers)

**Why this matters**: The MUSE paper introduces skill-level memory specifically
because agents were re-deriving the same lessons from scratch every time.
Your `.memory.md` means the next person who uses this skill doesn't repeat your mistakes.

---

### Stage 4: Management (Integration)

**Deliverable**: Updated triage table in `SKILL.md`

Your new model must be:
- [ ] Added to the Detection Map at the top of SKILL.md
- [ ] Integrated into the Chaining Rules section (which models pair well with yours?)
- [ ] Added to the Output Format section

---

### Stage 5: Refinement (Presentation)

**Deliverable**: 5-minute live demo

Demo script (you must hit all 4 beats):
1. **The gap** (30 sec): "The skill was missing this model because..."
2. **The model** (2 min): Run your model live on a real scenario. Show the output.
3. **The memory** (1 min): Read one entry from your `.memory.md` — something you learned that a future user needs to know.
4. **The second-order question** (1 min 30 sec): "If every AI agent had this model, what changes? What breaks?"

---

## Grading Rubric

| Component | Points | What earns full credit |
|---|---|---|
| Opportunity Cost analysis | 15 | Concrete comparison of 3 options; clear reasoning for choice |
| SKILL.md — model quality | 25 | Triage signal is precise; template is actionable; output format is consistent with existing models |
| Tests — 3 scenarios | 20 | All 3 pass; negative test (no false-trigger) included |
| `.memory.md` — depth | 20 | Specific lessons, not generic; failure modes documented; improvement ideas are concrete |
| Live demo | 20 | All 4 beats hit; model runs live; second-order question is genuinely insightful |

---

## What "Done" Actually Looks Like

A complete capstone submission is a folder you could hand to a MUSE-Autoskill agent
and it would immediately know:
- What the skill does (SKILL.md)
- When to use it (triage entry)
- How to evaluate it (scenarios.md)
- What traps to avoid (.memory.md)

If a future student can use your work without re-doing your thinking, you've done it right.
If they have to figure out the same things you figured out, your `.memory.md` failed.

---

## Reflection Question (Required, Written)

Submit 1 paragraph answering:

> "The MUSE paper argues that treating skills as 'long-lived, evolving assets'
> rather than 'one-off outputs' is a fundamental shift in AI design.
> Describe one place in your life — not AI — where treating something as a
> lifecycle-managed asset instead of a one-off effort would change your outcomes."

There is no wrong answer. There is an unthoughtful answer.
