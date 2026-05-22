import random
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


@dataclass
class AgentProfile:
    name: str
    role: str
    hours: float
    capital: float
    friction_tolerance: float
    sacrifice_threshold: float


DOMAIN_PROFILES: Dict[str, List[AgentProfile]] = {
    "gaming": [
        AgentProfile("cynical_grinder", "Pragmatic Skeptic", 6.0, 80.0, 0.15, 0.75),
        AgentProfile("lore_enthusiast", "Core Lore Builder", 10.0, 120.0, 0.80, 0.50),
        AgentProfile("casual_clout", "Trend-Driven Casual", 3.0, 40.0, 0.70, 0.40),
        AgentProfile("whale", "High-Investment Whale", 8.0, 500.0, 0.60, 0.65),
    ],
    "film": [
        AgentProfile("cynical_exec", "Studio Executive", 8.0, 50000.0, 0.20, 0.80),
        AgentProfile("festival_prog", "Festival Programmer", 12.0, 5000.0, 0.85, 0.55),
        AgentProfile("tiktok_influencer", "Viral Amplifier", 3.0, 300.0, 0.75, 0.35),
        AgentProfile("narrative_theorist", "Deep Critic", 10.0, 1000.0, 0.60, 0.60),
    ],
    "saas": [
        AgentProfile("cynical_cfo", "Procurement Skeptic CFO", 6.0, 50000.0, 0.15, 0.85),
        AgentProfile("it_director", "Overworked IT Director", 8.0, 25000.0, 0.40, 0.70),
        AgentProfile("workflow_champion", "Internal Champion", 12.0, 5000.0, 0.85, 0.50),
        AgentProfile("procurement_blocker", "Procurement Committee", 4.0, 100000.0, 0.10, 0.90),
    ],
    "ai_creative_pipeline": [
        AgentProfile("vc_scout", "AI Startup Scout", 8.0, 200000.0, 0.80, 0.50),
        AgentProfile("skeptic_eng", "Senior Engineer Skeptic", 10.0, 5000.0, 0.25, 0.80),
        AgentProfile("indie_builder", "Solo Founder / Maker", 14.0, 3000.0, 0.90, 0.35),
        AgentProfile("creative_director", "Creative Director", 9.0, 8000.0, 0.70, 0.55),
    ]
}


class CulturalSandbox:
    def __init__(self, domain: str = "gaming", weeks: int = 5):
        self.domain = domain
        self.weeks = weeks
        # Deep copy so each run starts fresh
        self.agents = [
            AgentProfile(**asdict(a)) for a in DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["gaming"])
        ]

    def _agent_interaction(self, agent: AgentProfile, week: int) -> Dict:
        time_cost = random.uniform(0.5, 1.5) * (1 + week * 0.1)
        capital_cost = random.uniform(0.05, 0.25) * agent.capital

        result = {
            "agent": agent.name,
            "week": week,
            "engaged": False,
            "subverted": False,
            "sacrificed_competitor": False,
            "budget_remaining": agent.hours
        }

        if agent.hours >= time_cost and agent.capital >= capital_cost:
            if random.random() < agent.friction_tolerance:
                agent.hours -= time_cost
                agent.capital -= capital_cost
                result["engaged"] = True
                result["budget_remaining"] = agent.hours

                if random.random() > 0.45:
                    result["subverted"] = True

                if random.random() > agent.sacrifice_threshold:
                    result["sacrificed_competitor"] = True

        return result

    def run(self, concept: str, verbose: bool = True) -> Dict[str, Any]:
        all_interactions = []
        weekly_summary = []

        for week in range(1, self.weeks + 1):
            week_interactions = [self._agent_interaction(a, week) for a in self.agents]
            engaged = sum(1 for i in week_interactions if i["engaged"])
            subverted = sum(1 for i in week_interactions if i["subverted"])
            sacrifices = sum(1 for i in week_interactions if i["sacrificed_competitor"])

            weekly_summary.append({"week": week, "engaged": engaged, "subverted": subverted, "sacrifices": sacrifices})
            all_interactions.extend(week_interactions)

            if verbose:
                print(f"  Week {week}: engaged={engaged} subverted={subverted} sacrifices={sacrifices}")

        total_engagements = sum(1 for i in all_interactions if i["engaged"])
        total_subversions = sum(1 for i in all_interactions if i["subverted"])
        total_sacrifices = sum(1 for i in all_interactions if i["sacrificed_competitor"])

        viral_velocity = round(total_engagements / self.weeks, 2)
        memetic_drift = round(total_subversions / (total_engagements + 1), 3)
        budget_filtered_retention = round(total_sacrifices / (total_engagements + 1), 3)

        late_weeks = [w for w in weekly_summary if w["week"] >= 4]
        late_engagement = sum(w["engaged"] for w in late_weeks) / (len(late_weeks) * len(self.agents))
        retention_decay_slop = round(late_engagement, 3)

        budget_survived = sum(1 for a in self.agents if a.hours > 0) >= len(self.agents) * 0.5

        verdict = "HIT" if (
            viral_velocity > 4.0
            and memetic_drift > 0.4
            and retention_decay_slop > 0.3
        ) else "SLOP"

        return {
            "concept": concept,
            "domain": self.domain,
            "metrics": {
                "viral_velocity": viral_velocity,
                "memetic_drift": memetic_drift,
                "retention_decay_slop": retention_decay_slop,
                "budget_filtered_retention": budget_filtered_retention,
                "budget_survived": budget_survived,
                "verdict": verdict
            },
            "weekly_summary": weekly_summary
        }
