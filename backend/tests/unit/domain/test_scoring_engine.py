import uuid
from typing import Any

from domain.entities.lead import Lead
from domain.entities.rule import ScoringRule
from domain.services.scoring_engine import ScoringEngine
from domain.value_objects.enums import Operator

_TENANT = uuid.uuid4()


def _lead(**overrides: Any) -> Lead:
    base = dict(
        tenant_id=_TENANT, first_name="Ana", last_name="Diaz", email="ana@x.test",
        company="Acme", budget=1000, industry="tech",
    )
    base.update(overrides)
    return Lead.create(**base)


def _rule(name: str, field: str, operator: Operator, value: Any, delta: int,
          priority: int = 0, is_active: bool = True) -> ScoringRule:
    return ScoringRule.create(
        tenant_id=_TENANT, name=name, field=field, operator=operator,
        value=value, score_delta=delta, priority=priority, is_active=is_active,
    )


def test_only_matching_rules_land_in_the_breakdown():
    lead = _lead()
    rules = [
        _rule("Tech", "industry", Operator.EQUALS, "tech", 30),
        _rule("Retail", "industry", Operator.EQUALS, "retail", 50),
    ]

    breakdown = ScoringEngine().evaluate(lead, rules)

    assert breakdown.total == 30
    assert [a.name for a in breakdown.applied] == ["Tech"]
    assert int(lead.score) == 30


def test_the_count_reflects_applied_rules_not_consulted_ones():
    """applied_rules_count used to report every rule fetched from storage."""
    lead = _lead()
    rules = [_rule(f"R{i}", "industry", Operator.EQUALS, "retail", 10) for i in range(5)]

    breakdown = ScoringEngine().evaluate(lead, rules)

    assert breakdown.total == 0
    assert len(breakdown.applied) == 0


def test_an_inactive_rule_never_applies():
    lead = _lead()
    rules = [_rule("Off", "industry", Operator.EQUALS, "tech", 30, is_active=False)]

    breakdown = ScoringEngine().evaluate(lead, rules)

    assert breakdown.total == 0
    assert int(lead.score) == 0


def test_the_breakdown_follows_priority_order():
    lead = _lead()
    rules = [
        _rule("Low", "industry", Operator.EQUALS, "tech", 5, priority=1),
        _rule("High", "company", Operator.CONTAINS, "cm", 7, priority=99),
    ]

    breakdown = ScoringEngine().evaluate(lead, rules)

    assert [a.name for a in breakdown.applied] == ["High", "Low"]
    assert breakdown.total == 12


def test_penalties_subtract():
    lead = _lead()
    rules = [_rule("Small budget", "budget", Operator.LESS_THAN, 5000, -20)]

    breakdown = ScoringEngine().evaluate(lead, rules)

    assert breakdown.total == -20
    assert int(lead.score) == -20
