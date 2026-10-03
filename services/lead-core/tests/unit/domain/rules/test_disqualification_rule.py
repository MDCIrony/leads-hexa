import uuid
from typing import Any

import pytest

from domain.rules.disqualification_rule import DisqualificationRule
from domain.leads.lead import Lead
from domain.exceptions import DomainException
from domain.services.viability_engine import ViabilityEngine
from domain.value_objects.criterion import Criterion
from domain.value_objects.enums import Operator

_TENANT = uuid.uuid4()


def _lead(**overrides: Any) -> Lead:
    base = dict(
        tenant_id=_TENANT, source_id=uuid.uuid4(), first_name="Ana", last_name="Diaz",
        company="Acme", budget=1000, industry="tech",
    )
    base.update(overrides)
    return Lead.create(**base)


def _rule(
    name: str = "R",
    field: str = "phone",
    operator: Operator = Operator.IS_EMPTY,
    value: Any = None,
    priority: int = 0,
    is_active: bool = True,
    rule_id: Any = None,
) -> DisqualificationRule:
    return DisqualificationRule.create(
        tenant_id=_TENANT, name=name, priority=priority, is_active=is_active, rule_id=rule_id,
        conditions=[Criterion.create(field=field, operator=operator, value=value)],
    )


def _no_contact_rule(name: str = "Sin forma de contactar") -> DisqualificationRule:
    """Two conditions ANDed: what makes case 1 of the phase come out right."""
    return DisqualificationRule.create(
        tenant_id=_TENANT,
        name=name,
        conditions=[
            Criterion.create(field="phone", operator=Operator.IS_EMPTY),
            Criterion.create(field="email", operator=Operator.IS_EMPTY),
        ],
    )


class TestCreate:
    def test_a_rule_with_no_conditions_is_rejected(self):
        with pytest.raises(DomainException) as exc:
            DisqualificationRule.create(tenant_id=_TENANT, name="R", conditions=[])
        assert exc.value.error_code == "INVALID_RULE_CONDITIONS"

    def test_a_rule_without_a_name_is_rejected(self):
        for blank in ("", "   "):
            with pytest.raises(DomainException) as exc:
                _rule(name=blank)
            assert exc.value.error_code == "INVALID_RULE_NAME"

    def test_a_rule_with_one_satisfied_condition_matches(self):
        assert _rule().matches(_lead()) is True


class TestViabilityEngine:
    def test_no_rules_returns_none(self):
        assert ViabilityEngine().evaluate(_lead(), []) is None

    def test_an_inactive_rule_that_would_match_is_ignored(self):
        rule = _rule(is_active=False)
        assert ViabilityEngine().evaluate(_lead(), [rule]) is None

    def test_two_matching_rules_returns_the_higher_priority_one(self):
        low = _rule(name="Low", priority=1)
        high = _rule(name="High", priority=9)
        assert ViabilityEngine().evaluate(_lead(), [low, high]) is high

    def test_two_matching_rules_with_the_same_priority_break_ties_by_id(self):
        """Stable regardless of input order: the id, not the list position,
        decides the winner."""
        first = _rule(name="First", rule_id=uuid.UUID(int=1))
        second = _rule(name="Second", rule_id=uuid.UUID(int=2))

        assert ViabilityEngine().evaluate(_lead(), [second, first]) is first
        assert ViabilityEngine().evaluate(_lead(), [first, second]) is first


class TestNoPhoneNoEmailDisqualifies:
    """The case that names the phase: phone-or-email is enough, both-missing
    is not. Written as one rule with two conditions — two separate rules
    would get Ana and Beto wrong."""

    def test_only_email_is_not_disqualified(self):
        ana = _lead(first_name="Ana", email="ana@empresa.com", phone=None)
        assert ViabilityEngine().evaluate(ana, [_no_contact_rule()]) is None

    def test_only_phone_is_not_disqualified(self):
        beto = _lead(first_name="Beto", phone="600123456", email=None)
        assert ViabilityEngine().evaluate(beto, [_no_contact_rule()]) is None

    def test_neither_phone_nor_email_is_disqualified(self):
        carla = _lead(first_name="Carla", phone=None, email=None)
        rule = _no_contact_rule()
        assert ViabilityEngine().evaluate(carla, [rule]) is rule
