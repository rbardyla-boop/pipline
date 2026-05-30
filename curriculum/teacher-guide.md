# Teacher Guide — Mental Models × MUSE Curriculum

This guide tells you *how* to run the mental-models skill in class, where the
"Caitlin leap" moments are, and what to do when students get stuck or go sideways.

---

## The Opening Gambit (Use This on Day 1)

Before any lecture, put this on the projector:

```
name: mental-models
description: >
  A suite of 7 battle-tested mental model frameworks for high-stakes thinking.
  AUTO-TRIGGERS when the user describes a hard decision, recurring problem,
  stuck situation, or uses phrases like: "I don't know what to do",
  "I keep running into this", "should I", "I'm stuck"...

TRIAGE PROTOCOL:
  Signal: "I keep failing at this"  → Deploy 5 Whys
  Signal: "Should I do X or Y"     → Deploy Regret Minimization
  Signal: "About to launch"         → Deploy Pre-Mortem
  Signal: "Everyone does it this way" → Deploy First Principles
```

Ask: **"What is this? Who wrote it? What problem does it solve? What's missing?"**

Do not explain anything. Let them argue for 8 minutes. Write every answer on the board.
Then reveal: this is a real AI skill, and today we're going to figure out what it means
for AI to have skills — and what it would take for an AI to get better at having them.

---

## Invoking the Skill in Class

### Setup (5 minutes before class)

Option A — Claude Code (best):
```bash
unzip .claude/skills/mental-models/mental-models.skill -d /tmp/mm-skill
# Then in Claude Code, paste the SKILL.md as context
```

Option B — Any Claude interface:
1. Open claude.ai or Claude app
2. Start a new conversation
3. Paste the full contents of SKILL.md as your first message, prefixed with:
   "You are now operating with the following skill loaded. Follow its triage protocol exactly:"
4. The skill is now active — present any scenario and it auto-deploys the right model

Option C — Paper prototype (no tech needed):
Print SKILL.md. Students use it manually: read the triage table, select a model,
execute the template on paper. Just as effective for most lessons.

---

## Lesson-by-Lesson Facilitation Notes

### Lesson 1: What Is an AI Agent? — INVERSION

**Deploy**: Inversion (Model 2)

**Scenario prompt for the class** (type this into active skill):
> "We are designing an AI assistant to help students complete multi-day projects.
> How would we guarantee it is completely useless?"

Expected student output (via Inversion model):
- Forget everything after each session → need memory
- Redo the same work every time → need reusable skills
- Never check if its outputs are correct → need evaluation
- Can't share what it learned → need management/transfer

**The leap**: Students just reconstructed the 4 gaps the MUSE paper identifies (§1 Introduction)
without reading a word of it. Point this out explicitly: "You just reverse-engineered a
research paper from first principles."

**If students get stuck**: Ask "What would a terrible intern do on Day 2 of a project?"
That usually unlocks it.

---

### Lesson 2: Skills as Superpowers — FIRST PRINCIPLES

**Deploy**: First Principles (Model 1)

**Scenario prompt**:
> "Everyone calls things like ChatGPT prompts 'instructions' or 'prompts'. 
> I keep calling this a 'skill'. Break down what's actually different — 
> strip away the jargon and get to the atoms."

Expected output (via First Principles model):
- A prompt is ephemeral; a skill is stored and retrieved
- A prompt has no tests; a skill can be validated
- A prompt has no memory; a skill can accumulate lessons
- A prompt is for one person; a skill is transferable

**Activity after the model runs**: Ask students to rate the mental-models skill itself.
"Is this a prompt or a skill? Which atoms does it have? Which is it missing?"
Answer: it has structure + reusability, but is missing tests and `.memory.md`.
That gap IS the transition to Lesson 3.

**Teacher note**: Some students will insist "it's just a fancy prompt."
Push them with: "If it's just a prompt, why does it have a triage protocol?
What would you have to add to make it undeniably a skill?"

---

### Lesson 3: The Skill Lifecycle — PRE-MORTEM

**Deploy**: Pre-Mortem (Model 7)

**Scenario prompt**:
> "It is one year from today. The mental-models skill has completely failed.
> No agent uses it. No student learned from it. It was abandoned.
> Work backwards: what went wrong?"

Expected failure scenarios students generate:
1. It was never tested — bad outputs weren't caught
2. Nobody kept notes about what worked — memory was lost
3. New versions overwrote old ones without merging — management failure
4. It couldn't be used by different AI systems — no transfer
5. Nobody kept improving it — no refinement loop

**The leap**: Draw the MUSE lifecycle on the board as students call out failures.
Each failure mode maps exactly to one missing lifecycle stage. By the end,
students have drawn the MUSE architecture from a failure post-mortem.

**Visual**: Draw this on the board live as failures emerge:

```
Failure: "no tests"         → EVALUATION stage
Failure: "lost lessons"     → MEMORY stage  
Failure: "version chaos"    → MANAGEMENT stage
Failure: "can't transfer"   → cross-agent portability
Failure: "never improved"   → REFINEMENT stage
Failure: "never packaged"   → CREATION stage
```

---

### Lesson 4: How MUSE Works — 5 WHYS

**Deploy**: 5 Whys (Model 3)

**Scenario prompt**:
> "An AI agent keeps failing when it works on projects that take more than one session.
> Every time it starts fresh, it makes the same mistakes. Why does this keep happening?"

Walk through the 5 Why chain with the class (write on board):
1. Why? → It forgets what it did before
2. Why? → No long-term memory between sessions
3. Why? → It treats each conversation as isolated
4. Why? → No persistent skill storage linked to what worked
5. Why? → Skills are treated as disposable one-off outputs, not lifecycle-managed assets

**Root cause**: "Agents have no skill lifecycle. Every run starts from zero."

**Then**: Read aloud the Figure 3 description from the paper (the end-to-end flow diagram).
Ask: "Which stage in this diagram fixes which Why?"

**Teacher note**: The 5 Whys chain is deliberately the same chain MUSE's introduction
makes in its "Limits of AutoSkill" paragraph (§1). Students who see this connection
are ready for the architecture deep-dive.

---

### Lesson 5: Evidence & Data — SECOND-ORDER THINKING

**Deploy**: Second-Order Thinking (Model 4)

**Present the result**: MUSE-Autoskill achieved 68.40% accuracy vs 53.19% without skills.
Skills gave a +15.21 percentage point lift. Self-created skills beat human-written ones
on their home tasks (87.94%). Skills transferred to a different agent with almost no loss.

**Scenario prompt**:
> "Skills boosted AI agent accuracy by 15 points. Skills transfer between agents.
> Skills created by AI can outperform skills written by humans. Map what happens next — 
> first, second, and third order consequences."

Expected output (via Second-Order Thinking):

Path A — This gets widely deployed:
- First order: Agents get dramatically more capable at specific domains
- Second order: Skills become shared assets; skill marketplaces emerge; companies compete on skill libraries, not just models
- Third order: Who owns a skill an agent created? What happens when a skill encodes a bias? How do you audit a skill that has been refined 400 times by different agents?

Path B — This doesn't get adopted:
- First order: Each team reinvents the wheel in isolation
- Second order: The capability gap between teams with skill libraries and without becomes unbridgeable
- Third order: AI development consolidates to a few players who have the skill infrastructure

**Discussion**: Which path are we on? What can individuals in this class do to influence it?

---

### Lesson 6: Ethics & Future — REGRET MINIMIZATION

**Deploy**: Regret Minimization (Model 5)

**Scenario prompt**:
> "You are 80 years old. The year is 2026 and AI skill systems just became viable.
> Looking back from 2080, what decisions made in 2026–2030 about how to build,
> share, and govern AI skills do you most wish someone had made differently?"

This is intentionally open-ended. Let students drive. Common answers:
- "I wish we had built public skill libraries instead of corporate silos"
- "I wish we had required human review before any skill could be used at scale"
- "I wish we had studied skill failure modes before deploying skill refinement loops"
- "I wish we had taught this in schools earlier" (yes, they often say this)

**Debate trigger** (if time allows): "An agent refined a skill 400 times across different
users. The original human author is unrecognizable in version 400. Who owns it?"

**Bridge to capstone**: "You now have the tools to not just understand this system —
you can contribute to it. The capstone is your chance to actually improve a real skill,
and leave a record of what you learned so the next agent — or student — doesn't start from zero."

---

## General Facilitation Principles

**Never give away the leap.** If a student is about to connect Pre-Mortem failure modes
to MUSE lifecycle stages, let them. It takes 30 more seconds and they'll remember it forever.

**Use the skill live, not as a demo.** When you invoke the mental-models skill in class,
let students see the output appear in real time. Ask "Would you change anything about
how it handled that? What would a better version do?" That IS the refinement loop.

**Track student insights as `.memory.md` entries.** When a student says something sharp
("the triage protocol is like the planning stage in MUSE"), write it on the board and
announce you're going to add it to the skill's memory file. This makes the lifecycle tangible.

**The skill is wrong sometimes.** Good. When the triage protocol deploys the wrong model,
ask the class to diagnose it: "Why did it choose First Principles here? What should it have
chosen? How would you fix the triage table?" That is real skill refinement.
