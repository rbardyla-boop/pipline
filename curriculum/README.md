# AI Agents That Learn and Evolve — Curriculum Integration Guide

**Subject**: Computer Science / AI Literacy  
**Grades**: 9–12  
**Periods**: 6–8 × 45–60 min + capstone  
**Source paper**: MUSE-Autoskill (Lin et al., ByteDance / RIT, May 2026)

---

## The Central Thesis

This curriculum ships with a real, working AI skill: the **Mental Models Suite**
(`.claude/skills/mental-models/mental-models.skill`).

Every lesson deploys that skill as both a *thinking tool* and a *living specimen*.
Students don't read about self-improving AI — they use a live example of one,
inspect its internals, and improve it as their capstone project.

By the final lesson, students understand MUSE-Autoskill not because they memorized
a paper, but because they walked the full skill lifecycle themselves.

---

## The Meta-Lesson (Read This First)

The mental-models skill instantiates every MUSE principle in one file students can hold:

| MUSE Lifecycle Stage | What it looks like in `mental-models.skill` |
|---|---|
| **Creation** | Synthesized from pattern-recognition across domains; packaged as SKILL.md + triage protocol |
| **Memory** | Missing — but `.memory.md` is exactly what it needs (students will add it) |
| **Management** | Catalog entry: name, description, trigger conditions — already done |
| **Evaluation** | Each model is testable: give it a scenario, grade the output quality |
| **Refinement** | Students improve the triage map and add new models in the capstone |

This is the "bold clue" move: hand students one artifact, let them reconstruct the
entire MUSE architecture from it. The paper is the answer key, not the lesson.

---

## Lesson Map

| # | Title | Core Concept | Mental Model Deployed | The Caitlin Leap |
|---|---|---|---|---|
| 1 | What Is an AI Agent? | Agents loop: Plan → Act → Observe | **Inversion** | Guarantee failure → discover every requirement agents must fill |
| 2 | Skills as Superpowers | Skills = packaged reusable know-how | **First Principles** | Inspect the artifact; rebuild "skill" from atoms |
| 3 | The Skill Lifecycle | Five MUSE stages | **Pre-Mortem** | "Your skill is dead." — failure modes map exactly to lifecycle gaps |
| 4 | How MUSE Works | Architecture + memory layers | **5 Whys** | "Why do agents fail on long projects?" → traces to: no lifecycle |
| 5 | Evidence & Data | SkillsBench: +15 pp lift | **Second-Order Thinking** | "+15pp. Then what happens next? And after that?" |
| 6 | Ethics & Future | Limits, ownership, safety | **Regret Minimization** | 2040 vantage point: what do we wish we had built? |
| C | Capstone | Build and demo a real skill | **Opportunity Cost** | Why THIS skill over every other? Commit. Execute the full lifecycle. |

---

## Quick Start for Teachers

1. **Extract the skill**: `unzip .claude/skills/mental-models/mental-models.skill -d /tmp/mm-skill`
2. **Read** `/tmp/mm-skill/mental-models/SKILL.md` — this is the specimen
3. **Invoke it**: paste the SKILL.md contents into a Claude system prompt, then present student scenarios
4. **The opening gambit** (Lesson 1): show students the raw SKILL.md before any explanation. Ask: "What IS this? What problem does it solve? What's missing?"

See [teacher-guide.md](teacher-guide.md) for full facilitation notes and classroom prompts.

---

## Files in This Directory

```
curriculum/
├── README.md              ← you are here: overview + lesson map
├── teacher-guide.md       ← facilitation notes, prompts, leap moments
└── capstone/
    ├── guide.md           ← full capstone instructions + MUSE lifecycle checklist
    └── starter-skill/     ← student template: add a new mental model
        ├── SKILL.md
        ├── .memory.md
        └── tests/
            └── scenarios.md
```

---

## How Mental Models Connect to MUSE (The Deeper Link)

The mental-models skill has a **triage protocol** — a decision tree that reads the situation
and selects the right model to invoke. This is structurally identical to MUSE's planning stage:

```
Mental Models Triage          MUSE Agent Loop
────────────────────────      ──────────────────────────
Detect situation type    →    Planning: decompose & choose skill
Select appropriate model →    Retrieval: query skill bank
Execute model template   →    Action: invoke skill via ReAct
Offer to chain models    →    Observation: refine and re-plan
```

Students who see this parallel have understood the deepest point of the paper:
**good thinking IS the skill lifecycle, and the skill lifecycle IS good thinking.**
