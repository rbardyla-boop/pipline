---
name: muse-curriculum
description: >
  Complete teaching system for "AI Agents That Learn and Evolve" — a 6-lesson
  high school curriculum (grades 9-12) built around the MUSE-Autoskill paper
  (Lin et al., ByteDance/RIT, May 2026).
  AUTO-TRIGGERS when a teacher or curriculum designer says: "I'm teaching AI agents",
  "I need a lesson on skills", "help me run the capstone", "how do I assess this",
  "a student is stuck on X", or needs any component of this course deployed on demand.
  The curriculum itself is a MUSE-managed skill: it was created from a successful
  teaching pattern, has memory of what works, and is designed to be extended by students.
inputs:
  - request: "lesson N" | "capstone" | "assess <submission>" | "student stuck on <concept>" | "slide outline for lesson N"
outputs:
  - Lesson content, facilitation prompts, student activities, assessment criteria, or diagnostic guidance
---

# MUSE-Autoskill Curriculum Skill

## Triage Protocol

| Input | Deploy |
|---|---|
| "lesson 1" / "agents" / "what is an agent" | **Lesson 1** — Inversion + agent requirements |
| "lesson 2" / "skills" / "superpowers" | **Lesson 2** — First Principles + skill anatomy |
| "lesson 3" / "lifecycle" / "stages" | **Lesson 3** — Pre-Mortem + MUSE 5 stages |
| "lesson 4" / "architecture" / "how MUSE works" | **Lesson 4** — 5 Whys + MUSE internals |
| "lesson 5" / "data" / "evidence" / "SkillsBench" | **Lesson 5** — Second-Order Thinking + results |
| "lesson 6" / "ethics" / "future" / "ownership" | **Lesson 6** — Regret Minimization + limits |
| "capstone" / "project" / "extend the skill" | **Capstone** — Opportunity Cost + lifecycle execution |
| "assess" / "grade" / "rubric" | **Assessment** — rubric + exemplar prompts |
| "student stuck" / "misconception" / "confused about" | **Diagnostic** — identify gap, deploy targeted clue |
| "slide" / "presentation" / "deck outline" | **Slides** — one-page outline per lesson |

---

## Lesson 1 — What Is an AI Agent?

**Mental model**: Inversion  
**Duration**: 45–60 min  
**Core teaching point**: Agents loop Plan → Act → Observe. LLMs alone are not enough.

### Opening (8 min)
Hand students the raw SKILL.md from this package (starter-skill/SKILL.md).  
Ask: "What is this? What problem does it solve? What's missing?"  
Do not explain. Write every answer on the board.

### Main Activity (25 min)
**Inversion prompt to run live**:
> "Design an AI assistant for students. How would you guarantee it is completely useless
> after one week? List every design choice that guarantees failure."

Collect failure modes. Map them to requirements:
- "Forgets everything" → needs persistent memory
- "Redoes the same work" → needs reusable skills  
- "Never checks its output" → needs evaluation
- "Can't be shared" → needs management/transfer

These are the four gaps in the MUSE paper §1. Students derived them.

### Close (10 min)
Reveal: "You just reconstructed the first two pages of a 2026 AI research paper.
That's not a coincidence — it means you're thinking like researchers."

### Slide outline
1. Title: "What makes an AI agent different from a chatbot?"
2. The ReAct loop diagram (Plan → Act → Observe)
3. "8-minute mystery" — SKILL.md on projector
4. Inversion results (class-generated list)
5. "You just wrote the intro to a ByteDance paper"

---

## Lesson 2 — Skills as Superpowers

**Mental model**: First Principles  
**Duration**: 45–60 min  
**Core teaching points**: Skills = packaged reusable know-how. Static, isolated skills are weak.

### Activity: Skill Dissection (20 min)
Students read the mental-models SKILL.md in pairs.  
Ask: "Using First Principles — what are the atoms? What is a skill, stripped of all jargon?"

Expected atom list:
- A name and description (so it can be found)
- A trigger condition (so it knows when to activate)
- A procedure (so it can be executed)
- A test (so it can be validated)
- A memory slot (so it can improve)

### Activity: Skill Marketplace (20 min)
Teams write a 1-page "skill spec" for a real school task (summarizing articles, debugging Python, planning an essay).  
Judge: Which specs are reusable? Which are too specific? Why?

### Close
"A skill without tests is a rumor. A skill without memory is amnesia.
Which of your marketplace skills would fail in six months, and why?"

---

## Lesson 3 — The Skill Lifecycle

**Mental model**: Pre-Mortem  
**Duration**: 50–60 min  
**Core teaching point**: The 5-stage MUSE lifecycle (Creation, Memory, Management, Evaluation, Refinement)

### The Pre-Mortem (25 min)
**Prompt to run live**:
> "It is one year from today. The mental-models skill has completely failed.
> No one uses it. It was abandoned. Work backwards: what went wrong?"

As students call out failure modes, draw the lifecycle on the board.  
Each failure = one missing lifecycle stage:
- "No one remembered what worked" → Memory
- "Tests were never written" → Evaluation
- "Couldn't be used by other systems" → Management/Transfer
- "Nobody fixed the bad outputs" → Refinement
- "It was made once and frozen" → Creation was never re-triggered

### Visual: Draw MUSE Figure 2 live (20 min)
Use student-generated failure modes as the building blocks.  
They are not copying a diagram — they drew it from its failure cases.

---

## Lesson 4 — How MUSE Works

**Mental model**: 5 Whys  
**Duration**: 45–60 min  
**Core teaching point**: MUSE architecture — skill_create, sandbox, evaluator, refiner, memory layers

### The 5 Whys Chain (15 min)
**Prompt**:
> "An AI agent fails on any project taking more than one session. Same mistakes every time. Why?"

Chain:
1. It forgets between sessions
2. No persistent memory linked to what it did
3. Skills are discarded after each run
4. No structured creation → storage → retrieval loop
5. Root: skills are treated as disposable outputs, not lifecycle-managed assets

### Architecture Trace (25 min)
Read MUSE Figure 3 description aloud. Ask students:
"Which component in this diagram fixes which Why in our chain?"

Skill Creator → Why 5 (creates and stores)
Skill Bank → Why 3 (retrieves instead of recreating)
Evaluator → Why 2 (validates before storage)
Memory → Why 1 (persists lessons across sessions)

### Creative Leap
"If you could add one component to this architecture that isn't there, what would it be?"
Record all suggestions. Some students propose things that appear in the MUSE paper's future work section.

---

## Lesson 5 — Evidence and Data

**Mental model**: Second-Order Thinking  
**Duration**: 45 min  
**Core teaching point**: SkillsBench results. +15pp lift. Cross-agent transfer. Self-created > human-written on home tasks.

### Data Presentation (10 min)
Show Table 2 from the paper (simplified):
- Without skills: 47–53% accuracy
- With human skills: 61–67%
- MUSE with self-created skills: 68.4% (87.94% on tasks where it succeeds)
- Skills transferred to different agent: +10.51pp, closes 79% of the gap

"Skills gave agents a +15 point accuracy boost. That's going from a C to an A."

### Second-Order Mapping (25 min)
**Prompt to run live**:
> "MUSE skills boosted accuracy 15pp. Skills transfer between agents. Self-created skills
> beat human-written ones on their home tasks. Map the consequences: first order, second
> order, third order. For both paths: this gets deployed vs. this stays in research."

Expected second-order outputs students generate:
- Skill marketplaces (trade skills like open-source libraries)
- Skill debt (inherited skills that nobody understands anymore)
- Skill security (a poisoned skill propagates across all agents using it)
- Skill inequality (teams with skill libraries vs. without)

### Discussion
"Which of these second-order effects do you think is most likely? Most dangerous?
What would you build first if you were on the MUSE team in 2027?"

---

## Lesson 6 — Ethics and Future

**Mental model**: Regret Minimization  
**Duration**: 45–60 min  
**Core teaching point**: Limitations. Ownership. Safety. What we should decide now.

### Regret Minimization (25 min)
**Prompt**:
> "You are 80 years old looking back from 2080. AI skill systems became widely deployed
> starting in 2026. What decisions made between 2026 and 2030 do you most wish had gone
> differently? What would the 80-year-old you want the 2026 you to do right now?"

This is intentionally open. Let students lead. Common themes:
- Public skill libraries vs. corporate silos
- Human review requirements before scale deployment
- Skill auditing and provenance tracking
- Teaching this in schools (they often say this unprompted)

### Debate Trigger
"An agent refined a skill 400 times across different users over 3 years.
The original human author is unrecognizable in version 400. Who owns it?
Should it be patentable? Should it be public domain?"

### Capstone Bridge
"You now understand this system well enough to contribute to it.
The capstone is your chance to leave something behind — a skill that outlives this class."

---

## Capstone — Build and Extend a Skill

**Mental model**: Opportunity Cost  
**Duration**: 2–3 class periods + homework  
See capstone/guide.md for complete instructions.

### Teacher notes
The Opportunity Cost analysis is not optional. It forces students to justify their choice
of mental model before building. The most common capstone failure is building something
the student thought was interesting rather than something that fills a real gap.

Strong capstone signal: student can articulate why the 7 existing models don't cover
their chosen situation, and why their model handles it better than any of them.

---

## Assessment — Diagnostic and Grading

### Misconception map

| Misconception | Likely source | Targeted clue to give |
|---|---|---|
| "A skill is just a prompt" | Never saw tests or memory | Show the starter-skill template. Ask: "If it's just a prompt, why does it need this?" |
| "MUSE replaces human skill writing" | Heard "self-created > human" out of context | Show Table 2 footnote: human skills still needed; MUSE excels on its own tasks |
| "Memory means the AI remembers the conversation" | Confused short-term/long-term/skill-level | Draw the 3 memory tiers; ask which one survives a reboot |
| "A skill that passes tests is a good skill" | Stopped at Evaluation | Ask: "What if the tests are wrong?" → Refinement loop, .memory.md |
| "The Pre-Mortem is pessimistic" | Surface reading | "What does a doctor do before surgery? Is that pessimism?" |

### Capstone grading rubric
See capstone/guide.md §Grading Rubric (weighted: SKILL.md 25%, tests 20%, memory 20%, demo 20%, Opportunity Cost 15%)

### Reflection prompt (all lessons)
"What was the one intuitive leap you made about how agents should improve?
Not what you memorized — what you figured out yourself."
