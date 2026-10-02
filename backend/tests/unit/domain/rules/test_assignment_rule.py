import uuid

import pytest

from domain.leads.lead import Lead
from domain.rules.assignment_rule import AssignmentRule
from domain.groups.sales_group import SalesGroup
from domain.exceptions import DomainException
from domain.value_objects.criterion import Criterion
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy, Operator

_TENANT = uuid.uuid4()
_GROUP = uuid.uuid4()


def _rule(**kwargs) -> AssignmentRule:
    defaults = {
        "tenant_id": _TENANT,
        "name": "Regla base",
        "target_group_id": _GROUP,
    }
    defaults.update(kwargs)
    return AssignmentRule.create(**defaults)


def _lead(score: int = 50, **kwargs) -> Lead:
    defaults = dict(
        tenant_id=_TENANT,
        source_id=uuid.uuid4(),
        first_name="Laura",
        last_name="Diaz",
        company="Globex",
        budget=1000,
        industry="Tech",
        score=score,
    )
    defaults.update(kwargs)
    return Lead.create(**defaults)


class TestScoreBand:
    def test_an_open_ended_rule_matches_anything_above_its_floor(self):
        rule = _rule(min_score=30)
        assert rule.matches_score(30) is True
        assert rule.matches_score(500) is True
        assert rule.matches_score(29) is False

    def test_a_band_is_inclusive_on_both_ends(self):
        """Bands are written as humans read them: "from 30 to 60" includes both."""
        rule = _rule(min_score=30, max_score=60)
        assert rule.matches_score(30) is True
        assert rule.matches_score(60) is True
        assert rule.matches_score(61) is False

    def test_an_inverted_band_is_rejected(self):
        with pytest.raises(DomainException) as exc:
            _rule(min_score=60, max_score=30)
        assert exc.value.error_code == "INVALID_SCORE_BAND"

    def test_a_single_point_band_is_allowed(self):
        rule = _rule(min_score=50, max_score=50)
        assert rule.matches_score(50) is True
        assert rule.matches_score(51) is False


class TestTargets:
    def test_a_rule_without_any_target_is_rejected(self):
        """Such a rule can never produce a candidate; it would fail silently."""
        with pytest.raises(DomainException) as exc:
            AssignmentRule.create(tenant_id=_TENANT, name="Vacía")
        assert exc.value.error_code == "RULE_WITHOUT_TARGET"

    def test_a_rule_orphaned_by_a_group_deletion_can_still_be_read_back(self):
        """Deleting a group nulls target_group_id by design, so storage holds
        rules with no target. If reading one raised, deleting a single group
        would break every ingestion for that organization."""
        rule = AssignmentRule.restore(tenant_id=_TENANT, name="Huérfana")

        assert rule.target_group_id is None
        assert rule.target_agent_ids == []

    def test_naming_agents_is_enough(self):
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="Directa", target_agent_ids=[uuid.uuid4()]
        )
        assert rule.target_group_id is None
        assert len(rule.target_agent_ids) == 1

    def test_the_default_match_mode_is_any(self):
        assert _rule().agent_match_mode == AgentMatchMode.ANY


class TestStrategyResolution:
    def test_a_rule_without_strategy_inherits_the_group(self):
        group = SalesGroup.create(
            tenant_id=_TENANT, name="Ventas", default_strategy=AssignmentStrategy.ROUND_ROBIN
        )
        assert _rule().resolve_strategy(group) == AssignmentStrategy.ROUND_ROBIN

    def test_the_rule_strategy_wins_over_the_group(self):
        group = SalesGroup.create(
            tenant_id=_TENANT, name="Ventas", default_strategy=AssignmentStrategy.ROUND_ROBIN
        )
        rule = _rule(strategy=AssignmentStrategy.LOWEST_LOAD)
        assert rule.resolve_strategy(group) == AssignmentStrategy.LOWEST_LOAD

    def test_without_a_group_the_fallback_is_lowest_load(self):
        """A rule that only names agents has no group to inherit from."""
        rule = AssignmentRule.create(
            tenant_id=_TENANT, name="Directa", target_agent_ids=[uuid.uuid4()]
        )
        assert rule.resolve_strategy(None) == AssignmentStrategy.LOWEST_LOAD


class TestMatches:
    """`matches` composes the band with the conditions; `matches_score`
    alone stays covered by TestScoreBand above."""

    def test_a_band_with_no_conditions_behaves_as_before(self):
        rule = _rule(min_score=30)
        assert rule.matches(_lead(score=50)) is True
        assert rule.matches(_lead(score=10)) is False

    def test_a_condition_the_lead_satisfies_applies(self):
        rule = _rule(
            min_score=30,
            conditions=[Criterion.create(field="industry", operator=Operator.EQUALS, value="Tech")],
        )
        assert rule.matches(_lead(score=50, industry="Tech")) is True

    def test_a_condition_the_lead_fails_blocks_it_even_inside_the_band(self):
        rule = _rule(
            min_score=30,
            conditions=[Criterion.create(field="industry", operator=Operator.EQUALS, value="Tech")],
        )
        assert rule.matches(_lead(score=50, industry="Retail")) is False

    def test_a_matching_condition_outside_the_band_does_not_apply(self):
        rule = _rule(
            min_score=80,
            conditions=[Criterion.create(field="industry", operator=Operator.EQUALS, value="Tech")],
        )
        assert rule.matches(_lead(score=50, industry="Tech")) is False


class TestRoundRobinCursor:
    def test_the_cursor_wraps_around(self):
        rule = _rule(rr_cursor=0)
        assert rule.advance_cursor(3) == 0
        assert rule.advance_cursor(3) == 1
        assert rule.advance_cursor(3) == 2
        assert rule.advance_cursor(3) == 0

    def test_the_cursor_survives_a_shrinking_pool(self):
        """An agent leaving the group must not push the cursor out of range."""
        rule = _rule(rr_cursor=7)
        assert rule.advance_cursor(3) == 1

    def test_advancing_over_an_empty_pool_is_rejected(self):
        rule = _rule()
        with pytest.raises(DomainException):
            rule.advance_cursor(0)
