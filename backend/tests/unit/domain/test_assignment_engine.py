import uuid
from typing import Dict, List, Optional

import pytest

from domain.advisors.advisor import Advisor
from domain.entities.lead import Lead
from domain.entities.rule import AssignmentRule
from domain.entities.sales_group import SalesGroup
from domain.services.assignment_engine import AssignmentEngine
from domain.value_objects.criterion import Criterion
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentMatchMode, AgentRole, AssignmentStrategy, LeadStatus, Operator
from domain.value_objects.group_id import GroupId
from domain.value_objects.tenant_id import TenantId

_TENANT = uuid.uuid4()


def _lead(score: int) -> Lead:
    # Score is a frozen value object (domain/value_objects/score.py), so it
    # cannot be mutated in place after construction; pass the score in.
    # QUALIFIED because the engine now hands off to Lead.assign_to, which
    # only a qualified (or previously unassigned) lead may enter.
    return Lead.create(
        tenant_id=_TENANT,
        source_id=uuid.uuid4(),
        first_name="Laura",
        last_name="Diaz",
        email="laura@example.com",
        company="Globex",
        budget=1000,
        industry="Tech",
        score=score,
        status=LeadStatus.QUALIFIED,
    )


def _agent(name: str, group_id: Optional[uuid.UUID] = None, active: bool = True) -> Advisor:
    return Advisor(
        AgentId(), TenantId(_TENANT), name, AgentRole.AGENT, active, 1,
        GroupId(group_id) if group_id else None,
    )


def _group(capacity: Optional[int] = None, active: bool = True,
           strategy: AssignmentStrategy = AssignmentStrategy.LOWEST_LOAD) -> SalesGroup:
    return SalesGroup.create(
        tenant_id=_TENANT, name="Ventas", capacity_per_agent=capacity,
        is_active=active, default_strategy=strategy,
    )


def _index(groups: List[SalesGroup]) -> Dict[uuid.UUID, SalesGroup]:
    return {g.id.value: g for g in groups}


class TestRuleSelection:
    def test_the_highest_priority_rule_wins(self):
        """Priority, not score: two rules can cover the same band on purpose."""
        group_a, group_b = _group(), _group()
        ana = _agent("Ana", group_a.id.value)
        beto = _agent("Beto", group_b.id.value)
        low = AssignmentRule.create(
            tenant_id=_TENANT, name="Baja", target_group_id=group_a.id.value, priority=1
        )
        high = AssignmentRule.create(
            tenant_id=_TENANT, name="Alta", target_group_id=group_b.id.value, priority=9
        )

        chosen = AssignmentEngine().select_agent(
            _lead(50), [low, high], [ana, beto], _index([group_a, group_b]), {}
        )
        assert chosen is beto

    def test_a_rule_outside_the_band_is_skipped(self):
        group = _group()
        ana = _agent("Ana", group.id.value)
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="Alta gama", target_group_id=group.id.value,
            min_score=80,
        )
        assert AssignmentEngine().select_agent(
            _lead(20), [rule], [ana], _index([group]), {}
        ) is None

    def test_an_inactive_rule_is_ignored(self):
        group = _group()
        ana = _agent("Ana", group.id.value)
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="Apagada", target_group_id=group.id.value,
            is_active=False,
        )
        assert AssignmentEngine().select_agent(
            _lead(50), [rule], [ana], _index([group]), {}
        ) is None

    def test_the_engine_cascades_to_the_next_rule(self):
        """The core fix: an empty rule used to end the search, losing the lead."""
        empty_group, staffed_group = _group(), _group()
        beto = _agent("Beto", staffed_group.id.value)
        first = AssignmentRule.create(
            tenant_id=_TENANT, name="Sin gente", target_group_id=empty_group.id.value,
            priority=9,
        )
        second = AssignmentRule.create(
            tenant_id=_TENANT, name="Con gente", target_group_id=staffed_group.id.value,
            priority=1,
        )

        chosen = AssignmentEngine().select_agent(
            _lead(50), [first, second], [beto], _index([empty_group, staffed_group]), {}
        )
        assert chosen is beto


class TestCandidateFiltering:
    def test_an_inactive_agent_is_excluded(self):
        group = _group()
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="R", target_group_id=group.id.value
        )
        ana = _agent("Ana", group.id.value, active=False)
        assert AssignmentEngine().select_agent(
            _lead(50), [rule], [ana], _index([group]), {}
        ) is None

    def test_an_inactive_group_receives_nothing(self):
        group = _group(active=False)
        ana = _agent("Ana", group.id.value)
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="R", target_group_id=group.id.value
        )
        assert AssignmentEngine().select_agent(
            _lead(50), [rule], [ana], _index([group]), {}
        ) is None

    def test_an_agent_at_capacity_is_excluded(self):
        group = _group(capacity=2)
        ana, beto = _agent("Ana", group.id.value), _agent("Beto", group.id.value)
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="R", target_group_id=group.id.value
        )
        loads = {ana.id.value: 2, beto.id.value: 0}

        chosen = AssignmentEngine().select_agent(
            _lead(50), [rule], [ana, beto], _index([group]), loads
        )
        assert chosen is beto

    def test_everyone_at_capacity_falls_through(self):
        group = _group(capacity=1)
        ana = _agent("Ana", group.id.value)
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="R", target_group_id=group.id.value
        )
        assert AssignmentEngine().select_agent(
            _lead(50), [rule], [ana], _index([group]), {ana.id.value: 1}
        ) is None


class TestMatchMode:
    def test_any_adds_the_named_agent_from_another_group(self):
        """The old engine intersected always, silently dropping this person."""
        group, other = _group(), _group()
        ana = _agent("Ana", group.id.value)
        beto = _agent("Beto", other.id.value)
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="R", target_group_id=group.id.value,
            target_agent_ids=[beto.id.value], agent_match_mode=AgentMatchMode.ANY,
            strategy=AssignmentStrategy.LOWEST_LOAD,
        )

        chosen = AssignmentEngine().select_agent(
            _lead(50), [rule], [ana, beto], _index([group, other]), {ana.id.value: 5}
        )
        assert chosen is beto

    def test_only_intersects_group_and_named_agents(self):
        group = _group()
        ana, beto = _agent("Ana", group.id.value), _agent("Beto", group.id.value)
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="R", target_group_id=group.id.value,
            target_agent_ids=[beto.id.value], agent_match_mode=AgentMatchMode.ONLY,
        )

        chosen = AssignmentEngine().select_agent(
            _lead(50), [rule], [ana, beto], _index([group]), {}
        )
        assert chosen is beto


class TestStrategies:
    def test_lowest_load_picks_the_least_busy(self):
        group = _group(strategy=AssignmentStrategy.LOWEST_LOAD)
        ana, beto = _agent("Ana", group.id.value), _agent("Beto", group.id.value)
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="R", target_group_id=group.id.value
        )
        loads = {ana.id.value: 7, beto.id.value: 2}

        chosen = AssignmentEngine().select_agent(
            _lead(50), [rule], [ana, beto], _index([group]), loads
        )
        assert chosen is beto

    def test_round_robin_rotates_and_persists_its_cursor(self):
        """The cursor lives on the rule, so rotation survives a new request."""
        group = _group(strategy=AssignmentStrategy.ROUND_ROBIN)
        ana, beto = _agent("Ana", group.id.value), _agent("Beto", group.id.value)
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="R", target_group_id=group.id.value
        )
        engine = AssignmentEngine()
        pool, groups = [ana, beto], _index([group])

        first = engine.select_agent(_lead(50), [rule], pool, groups, {})
        second = AssignmentEngine().select_agent(_lead(50), [rule], pool, groups, {})

        assert {first.name, second.name} == {"Ana", "Beto"}
        assert rule.rr_cursor == 2

    def test_the_assigned_lead_changes_status(self):
        group = _group()
        ana = _agent("Ana", group.id.value)
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="R", target_group_id=group.id.value
        )
        lead = _lead(50)

        AssignmentEngine().select_agent(lead, [rule], [ana], _index([group]), {})
        assert lead.assigned_agent_id.value == ana.id.value


class TestConditions:
    def test_the_lead_of_that_channel_goes_to_the_conditioned_rule(self):
        """Same band, two candidates: priority — not proximity in the list —
        is what makes the more specific rule win deterministically."""
        group_a, group_b = _group(), _group()
        ana = _agent("Ana", group_a.id.value)
        beto = _agent("Beto", group_b.id.value)
        general = AssignmentRule.create(
            tenant_id=_TENANT, name="General", target_group_id=group_a.id.value, priority=1,
        )
        referrals = AssignmentRule.create(
            tenant_id=_TENANT, name="Referidos", target_group_id=group_b.id.value, priority=9,
            conditions=[
                Criterion.create(field="custom_attributes.channel", operator=Operator.EQUALS, value="referral")
            ],
        )
        lead = _lead(50)
        lead.custom_attributes["channel"] = "referral"

        chosen = AssignmentEngine().select_agent(
            lead, [general, referrals], [ana, beto], _index([group_a, group_b]), {}
        )
        assert chosen is beto

    def test_no_matching_condition_leaves_the_lead_without_a_candidate(self):
        group = _group()
        ana = _agent("Ana", group.id.value)
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="Solo referidos", target_group_id=group.id.value,
            conditions=[
                Criterion.create(field="custom_attributes.channel", operator=Operator.EQUALS, value="referral")
            ],
        )
        lead = _lead(50)
        lead.custom_attributes["channel"] = "organic"

        assert AssignmentEngine().select_agent(
            lead, [rule], [ana], _index([group]), {}
        ) is None
