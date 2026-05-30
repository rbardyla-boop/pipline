# Lesson 5 — Evidence, Data, and the Hidden Snowball

**Mental models**: Second-Order Thinking (main) + Pre-Mortem (extension)  
**Duration**: 45 min main lesson + 20 min extension (or split across two periods)  
**Core question (the Caitlin leap prompt)**:  
"If adding skills gives agents a +15 percentage point boost today, what happens in six months? In two years? In ten years?"

---

## Part 1: Main Lesson (45 min)

### Opening — The Bold 8-Minute Move

Hand students **Figure 1** (SkillsBench bar chart) and tell them one number:

> "MUSE-Autoskill: 68.40% with skills. Without skills: 53.19%. That's a +15 point lift.
> Self-created skills hit 87.94% on the tasks they were built for.
> Skills transferred to a completely different agent still delivered +10.51pp."

Say nothing about implications. Then:

> "You just saw skills make agents dramatically better *right now*.
> What happens next? Not the first thing — the *second* thing. And then the third."

8 minutes. Let them talk. They will surface:
- Skills compound → agents get better at *making* skills
- Skill marketplaces emerge
- Old skills become baggage
- Someone has to govern the growing library
- The gap between teams *with* skill libraries and those without becomes unbridgeable

Do not confirm or redirect. Write every answer on the board. That list is the lesson.

---

### The Data (10 min)

Present Table 2 directly. Keep the framing simple:

| Agent | Without Skills | With Human Skills | Lift |
|---|---|---|---|
| Codex | 52.11% | 67.28% | +15.17pp |
| Hermes | 47.89% | 61.21% | +13.33pp |
| MUSE-Autoskill | 53.19% | 68.40% | **+15.21pp** |

MUSE self-created skills on 35 tasks where it succeeded: **87.94%** — surpassing the human-skill ceiling.  
MUSE skills injected into Hermes: **+10.51pp**, closing 79% of the gap to Hermes-with-human-skills.

**Teacher framing**: "Skills gave agents a +15 point accuracy boost. That's going from a C to an A.
And the skills one agent made were good enough to dramatically improve a completely different agent.
Now run the Second-Order map."

---

### Second-Order Mapping Activity (20 min)

Assign groups. Each group gets one first-order fact:

- Group A: "Skills raise accuracy +15pp"
- Group B: "Skills transfer between agents with almost no loss"
- Group C: "Self-created skills can outperform human-written ones on home tasks"
- Group D: "Skills reduce token cost on subsequent runs" *(see Table 6 in the paper)*

**Task**: Draw the consequence chain. Three levels deep. Both paths (this gets deployed / this stays in research).

**Then answer**: "Is this mostly good, mostly dangerous, or both?  
What one rule should we add to the skill lifecycle *right now* to steer the good outcome?"

Each group presents 90 seconds. Record their rules on a shared board.

---

### The Five Second-Order Implications (Teacher Reference — Deploy as Students Surface Them)

Use this to confirm and deepen what students generate. Don't lead with it.

**1. Compounding capabilities (the snowball)**
- First order: One skill saves time and raises accuracy on one task.
- Second order: Every skill makes the *next* skill easier because the agent has better building blocks and richer memory.
- Third order: Agents generate skills that generate skills → capability growth that isn't linear.
- Leap prompt: "If one skill gives +15pp, what happens when an agent has 100 self-reinforcing skills?"

**2. Skill marketplaces and network effects**
- Skills are now portable, testable assets (MUSE proves cross-agent transfer works).
- Second order: A "SkillHub" emerges — buy, sell, fork, audit skills.
- Third order: Best skills spread instantly across millions of agents → winner-take-most dynamics, but also rapid collective intelligence.
- Real-world analogy for students: Spotify playlists, but for thinking tools. The best mental model wins the world in days.

**3. Skill debt (the dark side)**
- First order: We ship lots of skills fast.
- Second order: Some skills become outdated, overly specific, or quietly buggy (the paper documents hvac-control dropping from 80% → 20%).
- Third order: The skill bank becomes a messy attic of half-working assumptions that slow agents down or cause silent failures.
- This leads directly into the Extension (Part 2).

**4. Governance and ownership**
- Who decides which skills are promoted, merged, or retired?
- Who owns a skill an agent created?
- Second order: We need version control, testing standards, and audit trails — essentially Git + unit tests + reputation systems for AI capabilities.
- Bold leap: "If skills are the source code of intelligence, skill governance is the new constitutional law for AI."

**5. Economic and societal ripples**
- Cost curves bend downward: generated skills are cheaper than human skills after ~3 reuses.
- Second order: Advanced AI capabilities become dramatically cheaper → anyone with good mental models can bootstrap powerful agents.
- Third order: Entire industries and curricula shift from "learn facts" to "learn how to evolve reusable thinking tools."

---

### Close (5 min)

Connect to the capstone:

> "The skill you build in the capstone will itself be subject to all five of these second-order forces.
> It will compound with other skills. It could end up in a skill marketplace. It could become skill debt.
> Someone will have to govern it.
>
> The `.memory.md` and the test scenarios you write aren't homework. They're your contribution
> to making sure that second-order story goes well."

---

## Part 2: Extension — Preventing Skill Debt (20 min or separate period)

### The Minimal Clue (give students only this)

> "Here is one real MUSE-generated skill that *regressed*: hvac-control dropped from 80% → 20%.
> It worked perfectly once on a single successful run, but failed in fresh environments because
> it baked in assumptions from that one trajectory.
>
> If skills are supposed to compound and make agents better forever… why do they sometimes make
> things *worse* over time?
>
> What is the smallest change to the MUSE lifecycle that would prevent this kind of rot at scale?"

Let them wrestle for 10 minutes. They will independently surface:
- Tests need to run on multiple environments, not just the one where the skill was created
- Skills need a "drift score" — does it keep working?
- Old skills need a sunset mechanism
- There should be a meta-skill watching the library

---

### What Skill Debt Actually Is (2 min)

Skill debt is the slow accumulation of:
- Skills with hidden assumptions that only worked once
- Outdated or overly narrow skills
- Redundant or conflicting skills
- Skills that pass original tests but quietly degrade performance elsewhere

From the MUSE paper's own evidence:
- Generated skills were 2.2× longer than human skills, encoding highly specific procedures
- One clear regression case: hvac-control
- MUSE has merging + pruning, but they are *reactive* — triggered after failure, not preventive

---

### Six Prevention Strategies (Teacher Reference — Confirm as Students Surface Them)

**1. Pre-Mortem at creation (Inversion + Pre-Mortem combined)**  
Before any skill is registered, run a pre-mortem: "Assume this skill fails or causes harm in 6–12 months. Why?"  
→ Surfaces trajectory-specific assumptions *before* the skill enters the bank.

**2. Mandatory cross-task generalization test**  
Test any new skill on 2–3 held-out tasks immediately. Only register if it improves or holds.  
→ Directly attacks the single-trajectory problem the paper identifies.

**3. Living memory + performance scorecard**  
`.memory.md` auto-appends usage metrics: success rate over time, latency, regressions triggered, drift score.  
Skills that drop below a threshold are flagged for refinement or pruning.

**4. Generalization refinement during merging**  
When a new skill overlaps >30% with an existing one, the Refiner must produce one broader skill that subsumes both — not just append.  
The merged skill must prove it is strictly better on a validation set.

**5. Deprecation and sunset protocol**  
Every skill has an "expected lifespan" or "re-validation trigger" (e.g., after 10 uses or 30 days).  
Unused or low-performing skills enter quarantine — still available, heavily penalized in retrieval.  
After quarantine: pruned unless a strong agent or human advocate revives them with new evidence.

**6. Skill Debt Prevention as a first-class meta-skill**  
Make "Skill Debt Prevention" itself a skill in the library — with its own SKILL.md, tests, and memory.  
This meta-skill audits the entire bank, suggests merges, and proposes lifecycle rule updates.  
→ See `capstone/example-debt-prevention/SKILL.md` for the reference implementation.

---

### Capstone Tie-In (Required Extension to Deliverables)

Students must add one section to their capstone SKILL.md:

```markdown
## Debt Prevention & Long-Term Health

### Pre-mortem result
[One scenario you ran: "Assume this skill fails in 6 months. Why?"]

### Generalization tests
[Two situations outside your home task where this model should also work — and your evidence]

### Re-validation trigger
[When should this skill be automatically re-evaluated? After how many uses? What drift threshold?]

### Governance note
[One rule you'd propose for a SkillHub that would prevent debt for skills like yours]
```

And one entry in `.memory.md`:

> "What surprised me about how fragile a 'good' skill can be."

---

## Teacher Notes

**Why both halves belong in one lesson**:  
The Second-Order main lesson establishes that skills compound — including their failures.
Skill Debt Prevention is what happens when students take that seriously. The connection is structural:
you cannot teach one honestly without the other.

**The recursive payoff**:  
Students who complete Part 2 will notice that their own capstone skill is now governed by the system
they just designed. The debt-prevention logic they wrote in class is implemented in the capstone
deliverable they produce. The curriculum is self-reinforcing at every level.

**Linking to Lesson 6**:  
The governance questions from Part 1 (who owns an agent-created skill?) and the sunset protocol
from Part 2 (who decides when a skill dies?) are the direct bridge into Lesson 6's
Regret Minimization prompt about 2040.
