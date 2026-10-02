from typing import Dict, List, Optional, Protocol, TypeVar
from uuid import UUID

from domain.entities.lead import Lead
from domain.entities.rule import AssignmentRule
from domain.entities.sales_group import SalesGroup
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy
from domain.value_objects.group_id import GroupId


class Candidate(Protocol):
    """What the engine reads off an agent: an Advisor in production."""

    @property
    def id(self) -> AgentId: ...

    @property
    def group_id(self) -> Optional[GroupId]: ...

    @property
    def is_active(self) -> bool: ...


CandidateT = TypeVar("CandidateT", bound=Candidate)


class AssignmentEngine:
    """Picks the agent a lead goes to.

    Stateless on purpose: the rotation cursor lives on the rule, which is
    persisted. The previous engine kept it in memory, so every request got a
    fresh instance and round-robin always chose the same agent."""

    def select_agent(
        self,
        lead: Lead,
        rules: List[AssignmentRule],
        agents: List[CandidateT],
        groups: Dict[UUID, SalesGroup],
        loads: Dict[UUID, int],
    ) -> Optional[CandidateT]:
        for rule in self._ordered_rules(rules, lead):
            group = groups.get(rule.target_group_id) if rule.target_group_id else None
            candidates = self._candidates_for(rule, group, agents, groups, loads)
            if not candidates:
                # Cascade: an empty rule used to end the search and lose the lead.
                continue
            return self._apply_strategy(lead, rule, group, candidates, loads)
        return None

    @staticmethod
    def _ordered_rules(rules: List[AssignmentRule], lead: Lead) -> List[AssignmentRule]:
        applicable = [r for r in rules if r.is_active and r.matches(lead)]
        # The id breaks ties: without it, two rules of equal priority resolve
        # by whatever order the database returned them.
        return sorted(applicable, key=lambda r: (-r.priority, str(r.id)))

    def _candidates_for(
        self,
        rule: AssignmentRule,
        group: Optional[SalesGroup],
        agents: List[CandidateT],
        groups: Dict[UUID, SalesGroup],
        loads: Dict[UUID, int],
    ) -> List[CandidateT]:
        named = {str(aid) for aid in rule.target_agent_ids}
        in_group = (
            {str(a.id) for a in agents if a.group_id and a.group_id.value == group.id.value}
            if group
            else set()
        )
        if rule.agent_match_mode == AgentMatchMode.ONLY:
            selected_ids = in_group & named
        else:
            selected_ids = in_group | named

        return [
            agent
            for agent in agents
            if str(agent.id) in selected_ids and self._is_eligible(agent, groups, loads)
        ]

    @staticmethod
    def _is_eligible(
        agent: CandidateT,
        groups: Dict[UUID, SalesGroup],
        loads: Dict[UUID, int],
    ) -> bool:
        if not agent.is_active:
            return False

        own_group = groups.get(agent.group_id.value) if agent.group_id else None
        # No group means the rule reached this agent by naming it: there is no
        # group policy to apply, so being active is the whole test.
        if own_group is None:
            return True
        return own_group.is_active and own_group.has_capacity_for(loads.get(agent.id.value, 0))

    @staticmethod
    def _apply_strategy(
        lead: Lead,
        rule: AssignmentRule,
        group: Optional[SalesGroup],
        candidates: List[CandidateT],
        loads: Dict[UUID, int],
    ) -> CandidateT:
        strategy = rule.resolve_strategy(group)

        if strategy == AssignmentStrategy.ROUND_ROBIN:
            ordered = sorted(candidates, key=lambda a: str(a.id))
            selected = ordered[rule.advance_cursor(len(ordered))]
        elif strategy == AssignmentStrategy.DIRECT_AGENT:
            # The manager wrote target_agent_ids in that order on purpose.
            by_id = {str(a.id): a for a in candidates}
            selected = next(
                (by_id[str(aid)] for aid in rule.target_agent_ids if str(aid) in by_id),
                candidates[0],
            )
        else:
            # The id breaks ties so two equally loaded agents resolve the same
            # way on every run.
            selected = min(candidates, key=lambda a: (loads.get(a.id.value, 0), str(a.id)))

        # The engine only ever reaches agents of the lead's own organization,
        # so passing the lead's tenant satisfies the entity's cross-tenant
        # invariant without widening the engine's signature.
        lead.assign_to(selected.id, lead.tenant_id)
        return selected
