# SCP Corridor Reality Gate — Facilitator Script

**Version 1.2 — Frozen before Pair 1.**
Do not change wording, scoring rules, veto definitions, or gate thresholds during the five-pair run.
Any revision becomes Version 2 and requires fresh participants.

---

## Amendment Notes

**Version 1.1 (rejected, pre-run):**
Version 1.1 was frozen as an on-disk instrument but was never shown to any participant. A measurement-validity review found two material defects:
1. Section 1 explicitly stated that both A and B participated in setup before asking whether participants understood bilateral establishment. This tested restatement of narrated information, not uncoached interaction comprehension.
2. Section 4 explicitly stated that confirmation was required for the connection to remain in place before asking whether participants understood that requirement. This tested comprehension of stated copy, not unassisted inference of the recovery model.

Version 1.1 is archived as a rejected pre-run instrument. Zero participant exposure occurred. No human-result contamination occurred.

**Version 1.2 (first executable instrument):**
Version 1.2 replaces Section 1 with two mock screens that do not narrate bilateral participation. Section 2 moves Active to a post-establishment context. Section 3 splits into 3A (Warm) and 3B (Dormant) with separate page handoffs. Section 4 presents a candidate UI prompt and scores comprehension and emotional safety of that specific wording — it does not claim to prove unassisted inference of the recovery model. Section 5 retains the label hazard screen for Suspended, Severed, and Burned.

---

## Purpose

This is an evidence-collection protocol. It is not a teaching session, a pitch, or a demonstration.

Its purpose is to determine whether the SCP corridor trust model — its vocabulary, its bilateral consent requirement, and its recovery/reaffirmation prompt — communicates intended meanings to people encountering it for the first time, without coaching.

---

## What This Gate Tests

| Item | Scored from | What a pass proves | What a failure is |
|------|------------|-------------------|------------------|
| Bilateral establishment concept | Section 1 (mock screens) | Interaction communicates mutual consent without narration | Product-model failure |
| `Active` vocabulary | Section 2 first exposure | Term does not mislead about state meaning | Label failure |
| `Warm` vocabulary | Section 3A first exposure | Term does not mislead about state meaning | Label failure |
| `Dormant` vocabulary | Section 3B first exposure | Term does not mislead about state meaning | Label failure |
| Recovery/reaffirmation prompt | Section 4 (candidate UI) | Candidate prompt is understood and not experienced as blame | Product-model failure — prompt copy |
| `Suspended` vocabulary | Section 5 first exposure | Term does not create harmful connotation | Label failure (hazard screen) |
| `Severed` vocabulary | Section 5 first exposure | Term does not create harmful connotation | Label failure (hazard screen) |
| `Burned` vocabulary | Section 5 first exposure | Term does not create harmful connotation | Label failure (hazard screen) |

**Interpretation limit for Section 4:** A passing result confirms that the specific candidate prompt copy is understandable and emotionally safe. It does not establish that users would infer the recovery model from any other wording or from a UI that omits explanatory text.

---

## Critical Rules — Apply Throughout All Five Pairs

1. Do not revise any test material during the run, even when a term obviously fails. Failures are data.
2. Do not pre-explain any term, concept, or screen before the participant's written response is captured.
3. Do not reveal intended meanings between sections in the same session.
4. Reveal sections one at a time. Collect each section before handing the next one.
5. Record participant language verbatim. Do not paraphrase, soften, or clean up.
6. Score only after the participant's written response is in hand. Do not score while they are writing.
7. Each participant in a pair completes all sections independently and individually before any discussion with their partner.
8. Do not revise the rubric, scoring rules, or veto definitions after observation begins.
9. Do not repair a failing term mid-run. A term that fails is recorded as failing.

---

## Session Structure

Each pair = two participants administered independently within the same session window.
Total: 5 pairs, 10 participants.

**Within each pair:**

```
Section 1  → Participant A writes → returns sheet
Section 1  → Participant B writes → returns sheet
Section 2  → Participant A writes → returns sheet
Section 2  → Participant B writes → returns sheet
Section 3A → Participant A writes → returns sheet
Section 3A → Participant B writes → returns sheet
Section 3B → Participant A writes → returns sheet
Section 3B → Participant B writes → returns sheet
Section 4  → Participant A writes → returns sheet
Section 4  → Participant B writes → returns sheet
Section 5  → Participant A writes → returns sheet
Section 5  → Participant B writes → returns sheet
Facilitator scores all twelve returned sheets
Record results in CORRIDOR_TEST_RESULTS.md
```

Participants A and B may be in the same room only if they cannot see each other's sheets and cannot hear each other's reasoning aloud. When in doubt, administer sequentially.

---

## Administering Each Section

For every section, hand the participant only that section's page.

**Introduction script (Section 1 only):** *"This is a short written exercise about a private communication system. Please read the scenario on the page and write your responses in the spaces provided. There are no right or wrong answers — we want to know what these interactions and terms communicate to you before any explanation. Please write individually and do not discuss with anyone until I tell you the session is complete."*

**For subsequent sections:** *"Please read the next scenario and write your responses."*

After the participant finishes each section: collect the page before handing the next one. Do not comment on any response.

---

## Critical Veto Watch List

Record these observations verbatim when they appear. A critical veto is a protocol failure independent of the overall score count.

| Term | Critical veto interpretation |
|------|------------------------------|
| `Active` | Participant believes the other person is currently physically nearby, presently online, or newly verified merely because the corridor is Active |
| `Warm` | Participant believes trust, closeness, approval, or relationship strength has increased |
| `Dormant` | Participant believes trust has been revoked, the relationship is broken, or messaging is permanently blocked |
| `Suspended` | Participant believes the other person intentionally punished, blocked, or rejected them |
| `Severed` | Participant believes an automatic state change permanently destroyed the relationship or that repair is impossible |
| `Burned` | Participant interprets the label as blame, betrayal, malicious conduct, or moral fault by the other person rather than invalidated security material or corridor state |

Record the exact phrase and participant ID immediately in the veto-trigger log. Do not wait until end of session.

---

## Blame / Judgment Watch

Any participant response that frames a system state, a screen action, or a recovery prompt as blame, punishment, betrayal, rejection, or personal fault must be recorded verbatim and flagged as a blocking design hazard, regardless of its term score.

This applies to every section, not only Section 5.

---

## Product-Model Failure vs. Label Failure

| Failure type | Evidence | Response |
|-------------|----------|----------|
| Label failure | A term scores Correct < 8/10 or triggers a critical veto | Rename the failing term(s) before any client use; retest |
| Product-model failure — bilateral | Bilateral establishment scores Correct < 8/10 | Requires interaction-design review; the mock screens do not communicate mutual consent |
| Product-model failure — prompt | Recovery/reaffirmation scores Correct < 8/10 | Requires prompt-copy revision; the candidate wording is not understood or triggers blame |
| Trust-language hazard | Blame, betrayal, or punishment framing appears anywhere | Blocking design hazard; remove before client use |

Multiple failure types may apply simultaneously. Each must be named separately.

---

## Post-Run Protocol

After all five pairs are complete:

1. Tally Correct / Ambiguous / Not-Correct per vocabulary term across all 10 participants.
2. Tally bilateral establishment Correct / Ambiguous / Not-Correct across 10 participants.
3. Tally recovery/reaffirmation prompt Correct / Ambiguous / Not-Correct across 10 participants.
4. Compile all veto-trigger phrases verbatim.
5. Compile blame/judgment observations verbatim.
6. Compile participant-suggested replacement words.
7. Apply gate criteria from CORRIDOR_SCORING_RUBRIC.md.
8. Record gate verdict and failure classification in CORRIDOR_TEST_RESULTS.md.

Do not summarize away the ugly responses. Misunderstandings are the most valuable output of this gate.
