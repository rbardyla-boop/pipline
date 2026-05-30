---
name: skill-debt-prevention
description: >
  A meta-skill that audits, governs, and protects the skill bank from slow degradation.
  Unlike other mental models (which are deployed on external situations), this skill is
  deployed ON OTHER SKILLS. It runs before a skill is promoted, periodically during its
  lifetime, and before a skill is pruned.
  AUTO-TRIGGERS when: a new skill is about to be registered, a skill's performance is
  declining, a merge decision is pending, a prune decision is pending, or an agent asks
  "is my skill bank healthy?"
  This is a second-order skill — it exists to make all first-order skills work better
  over a longer horizon.
inputs:
  - skill_candidate: a new SKILL.md package under consideration for registration
  - skill_under_review: an existing skill with declining metrics
  - bank_state: a list of all skills with usage and performance history
  - merge_candidates: two or more skills under consideration for consolidation
outputs:
  - registration_verdict: APPROVE / CONDITIONAL / REJECT with specific conditions
  - health_report: per-skill drift scores, quarantine recommendations, prune candidates
  - merge_recommendation: merged SKILL.md draft or rejection with reason
  - lifecycle_rule_proposals: suggested updates to the skill bank governance policy
---

# Skill Debt Prevention (Meta-Skill)

## What makes this skill different

Every other skill in this library applies a thinking framework to an *external* situation.
This skill applies a governance framework to *other skills*.

It is the immune system of the skill bank. It does not solve tasks — it protects the
infrastructure that solves tasks. Without it, skill debt accumulates silently until
the bank is full of outdated, narrow, or conflicting skills that degrade performance
even as the collection grows.

This skill should be one of the first skills in any serious skill bank.
It is also the most appropriate capstone extension for students who want to build
infrastructure, not just content.

---

## Triage Protocol

| Trigger | Execute |
|---|---|
| "Should we register this skill?" / new skill candidate ready | **Pre-Registration Audit** |
| "This skill is underperforming" / drift detected | **Skill Health Review** |
| "These two skills seem to overlap" / merge candidate | **Merge or Generalize** |
| "Should we remove this skill?" / prune candidate | **Sunset Protocol** |
| "How healthy is the whole bank?" / periodic audit | **Full Bank Audit** |

---

## PROCEDURE 1 — Pre-Registration Audit

*Run before any skill enters the bank. A skill that passes creates a debt-of-confidence.
A skill that fails now saves 10× the cleanup cost later.*

> Execute this checklist against the candidate SKILL.md:
>
> **Generalization test** (mandatory):
> 1. Identify the task or trajectory the skill was created from.
> 2. Name two *different* tasks or contexts where this skill should also apply.
> 3. Does the skill's procedure work on those two contexts, or does it bake in
>    assumptions specific to the origin task?
>    - If it bakes in assumptions: the skill must be generalized before registration.
>      Flag the specific lines in SKILL.md that encode the narrow assumption.
>    - If it generalizes cleanly: proceed.
>
> **Pre-Mortem** (mandatory):
> "Assume this skill fails or causes harm 6–12 months from now. Why?"
> List every plausible failure mode. For each one:
> - Is this failure mode visible before it causes harm? (If not: add a detection mechanism)
> - Does the existing test suite catch it? (If not: require new tests before registration)
>
> **Overlap check** (mandatory):
> Search the skill bank for skills with >30% semantic overlap.
> - If an overlapping skill exists: escalate to Procedure 3 (Merge or Generalize).
> - If none: proceed.
>
> **Verdict**: APPROVE / CONDITIONAL (list required changes) / REJECT (list reason)
>
> Conditional skills enter a 72-hour probation period: 3 additional test runs
> in varied environments before full registration.

---

## PROCEDURE 2 — Skill Health Review

*Run when a skill's metrics drop, when it hasn't been used in 30+ days, or on
a scheduled re-validation trigger. Every skill in the bank should have a
re-validation trigger date set at registration.*

> **Performance scorecard** — retrieve from `.memory.md` and usage logs:
> - Current success rate vs. success rate at registration
> - Average performance delta (does using this skill help, hurt, or do nothing?)
> - Number of regressions triggered by this skill in the last 30 days
> - Drift score: success rate decline per 10 uses
>
> **Drift diagnosis** — if drift score > threshold:
> 1. Which task types is the skill failing on that it previously passed?
> 2. Has the environment changed (new API, different data format, updated requirements)?
> 3. Has the skill been used outside its intended domain? (If yes: the domain boundary
>    needs to be made explicit in SKILL.md, not just in `.memory.md`.)
>
> **Verdict**:
> - Healthy: no action needed; update `.memory.md` with review date and findings
> - Drifting: trigger Procedure 1 Generalization Test on current version; update skill if it fails
> - Severely degraded: enter quarantine (Procedure 4)

---

## PROCEDURE 3 — Merge or Generalize

*Run when two or more skills overlap, or when a new skill duplicates existing functionality.
The goal is not to keep both and let them compete — it is to produce one skill that is
strictly better than either.*

> **Overlap analysis**:
> 1. State precisely what each skill does that the other does not.
> 2. State precisely what they share.
> 3. Is the overlap accidental (same task approached differently) or intentional (different abstraction levels)?
>
> **Generalization prompt**:
> "Write a new skill that subsumes both. It must:
> - Pass all tests from both originals
> - Handle at least one task that neither original handles alone
> - Have a tighter, more precise trigger condition than either
> - Be shorter or equal length to the longer of the two originals"
>
> **Verdict**:
> - If a valid merged skill can be produced: register it; archive (do not delete) both originals
> - If merger would produce a skill too broad to be reliable: keep both; add explicit boundary
>   documentation to each so they don't compete at retrieval time
> - If one is strictly better: deprecate the weaker; update `.memory.md` with reason

---

## PROCEDURE 4 — Sunset Protocol

*Every skill has a lifespan. The question is not whether to prune — it is when and how.*

> **Quarantine conditions** (any one of these triggers quarantine):
> - Success rate below 50% for 10 consecutive uses
> - Zero uses in 90 days while similar skills are active
> - Drift score indicates consistent regression regardless of domain
> - Two failed re-validation cycles
>
> **Quarantine state**:
> - Skill remains available for retrieval but is penalized heavily in ranking
> - Duration: 14 days
> - During quarantine: one revival attempt is permitted (human or strong agent advocate
>   must provide new evidence that the skill fills a real gap)
>
> **Sunset conditions** (any one of these triggers pruning):
> - Quarantine period expired with no revival
> - Confirmed replacement skill is active and validated
> - Original use case is confirmed obsolete
>
> **Pruning is not deletion**: archived skills move to a cold store with their `.memory.md`
> intact. If the original task type resurfaces, the archived skill is the starting point
> for the new version — not a blank SKILL.md.

---

## PROCEDURE 5 — Full Bank Audit

*Run periodically (suggested: every 50 new skill registrations or monthly).*

> Generate a health report covering:
> - Total skills: active / quarantine / archived
> - Average drift score across active skills
> - Top 5 skills by usage (these are load-bearing; prioritize for re-validation)
> - Top 5 skills by regression incidents (candidates for Procedure 2)
> - Merge candidates: any pairs with >40% semantic overlap not yet flagged
> - Lifecycle rule proposals: any patterns in failures that suggest a systemic change
>   to registration, merging, or pruning policy
>
> Output the report as a structured `.memory.md` append entry with date, findings,
> and specific action items. Route high-priority items to human review.

---

## Chaining

- **Debt Prevention → Pre-Mortem**: Use Pre-Mortem at creation (Procedure 1) and during health review
- **Debt Prevention → Survivorship Bias**: When evaluating a skill's success rate, ask: "Are we seeing all the failure cases, or only the cases where the skill was invoked?"
- **Debt Prevention → Chesterton's Fence**: Before every pruning decision, run Chesterton's Fence: "Why was this skill built? Is that reason gone?"
- **Debt Prevention → Map/Territory**: The performance scorecard is a map; the real health of the skill bank is the territory

---

## Why this is the right capstone choice for infrastructure-minded students

Most capstone skills improve *what agents can do*.
This skill improves *how reliably agents can keep doing things*.

The students who build this are not writing content — they are designing governance.
They are the ones who, in a real organization, would be trusted to steward the
skill library after the class ends.

The hardest part of this capstone is Procedure 4 (Sunset Protocol). Students typically
want to keep everything. The discipline of designing a principled deletion system — one
that is fair, reversible, and documented — is the highest-level thinking in this curriculum.
