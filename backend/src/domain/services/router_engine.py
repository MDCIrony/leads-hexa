from typing import List, Optional
from domain.entities.lead import Lead
from domain.entities.rule import RoutingRule
from domain.entities.agent import Agent
from domain.value_objects.enums import AssignmentStrategy

class RouterEngine:
    def __init__(self) -> None:
        self._rr_indices: dict[str, int] = {}

    def select_agent(
        self,
        lead: Lead,
        routing_rules: List[RoutingRule],
        available_agents: List[Agent]
    ) -> Optional[Agent]:
        sorted_rules = sorted(routing_rules, key=lambda r: r.min_score, reverse=True)
        matching_rule: Optional[RoutingRule] = None
        for rule in sorted_rules:
            if lead.score.value >= rule.min_score:
                matching_rule = rule
                break

        if not matching_rule:
            return None

        eligible_agents = [
            agent for agent in available_agents
            if agent.is_active and agent.team == matching_rule.target_team
        ]

        if matching_rule.target_agent_ids:
            target_ids_str = [str(aid) for aid in matching_rule.target_agent_ids]
            eligible_agents = [
                agent for agent in eligible_agents
                if str(agent.id.value) in target_ids_str or str(agent.id) in target_ids_str
            ]

        if not eligible_agents:
            return None

        strategy = matching_rule.assignment_strategy
        if strategy == AssignmentStrategy.LOWEST_LOAD:
            selected = min(eligible_agents, key=lambda a: a.active_leads_count)
        elif strategy == AssignmentStrategy.ROUND_ROBIN:
            rule_key = str(matching_rule.id)
            idx = self._rr_indices.get(rule_key, 0) % len(eligible_agents)
            selected = eligible_agents[idx]
            self._rr_indices[rule_key] = idx + 1
        elif strategy == AssignmentStrategy.DIRECT_AGENT:
            selected = eligible_agents[0]
        else:
            selected = eligible_agents[0]

        lead.assign_to_agent(selected.id)
        return selected
