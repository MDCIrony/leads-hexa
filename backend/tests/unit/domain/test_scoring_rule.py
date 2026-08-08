import uuid
from decimal import Decimal
from typing import Any, Optional

import pytest

from domain.entities.lead import Lead
from domain.entities.rule import ScoringRule
from domain.exceptions import DomainException
from domain.value_objects.enums import Operator

_TENANT = uuid.uuid4()


def _lead(**overrides: Any) -> Lead:
    base = dict(
        tenant_id=_TENANT, first_name="Ana", last_name="Diaz", email="ana@x.test",
        company="Acme", budget=1000, industry="tech",
    )
    base.update(overrides)
    return Lead.create(**base)


def _rule(field: str, operator: Operator, value: Any, delta: int = 10) -> ScoringRule:
    return ScoringRule.create(
        tenant_id=_TENANT, name="R", field=field, operator=operator,
        value=value, score_delta=delta,
    )


class TestOperators:
    def test_equals_matches_across_string_and_number(self):
        assert _rule("budget", Operator.EQUALS, "1000").matches(_lead()) is True

    def test_not_equals_applies_the_same_coercion_as_equals(self):
        """Both may not be true for the same pair; that was the old bug."""
        lead = _lead()
        equals = _rule("budget", Operator.EQUALS, "1000").matches(lead)
        not_equals = _rule("budget", Operator.NOT_EQUALS, "1000").matches(lead)
        assert equals is True
        assert not_equals is False

    def test_numeric_comparison_keeps_decimal_precision(self):
        lead = _lead(budget=Decimal("0.30"))
        assert _rule("budget", Operator.GREATER_THAN, Decimal("0.10")).matches(lead) is True
        assert _rule("budget", Operator.LESS_THAN, Decimal("0.10")).matches(lead) is False

    def test_in_works_with_a_real_list(self):
        assert _rule("industry", Operator.IN, ["tech", "finance"]).matches(_lead()) is True
        assert _rule("industry", Operator.IN, ["retail"]).matches(_lead()) is False

    def test_contains_looks_inside_a_string(self):
        assert _rule("company", Operator.CONTAINS, "cm").matches(_lead()) is True


class TestMissingField:
    def test_a_missing_field_is_false_for_positive_operators(self):
        lead = _lead()
        assert _rule("custom_attributes.absent", Operator.EQUALS, "x").matches(lead) is False
        assert _rule("custom_attributes.absent", Operator.GREATER_THAN, 1).matches(lead) is False

    def test_a_missing_field_is_true_for_not_equals(self):
        """A lead with no 'campaign' genuinely does not equal 'summer'."""
        lead = _lead()
        assert _rule("custom_attributes.absent", Operator.NOT_EQUALS, "x").matches(lead) is True


class TestAllowedFields:
    def test_a_field_outside_the_allow_list_is_rejected(self):
        """Free reflection let a rule read tenant_id or hashed internals."""
        with pytest.raises(DomainException) as exc:
            _rule("tenant_id", Operator.EQUALS, str(_TENANT))
        assert exc.value.error_code == "FIELD_NOT_SCORABLE"

    def test_custom_attributes_are_always_allowed(self):
        rule = _rule("custom_attributes.employee_count", Operator.GREATER_THAN, 10)
        assert rule.matches(_lead(custom_attributes={"employee_count": 50})) is True


class TestRuleState:
    def test_a_rule_carries_its_organization_and_defaults(self):
        rule = _rule("industry", Operator.EQUALS, "tech")
        assert rule.tenant_id == _TENANT
        assert rule.priority == 0
        assert rule.is_active is True

    def test_the_in_operator_demands_a_list(self):
        with pytest.raises(DomainException) as exc:
            _rule("industry", Operator.IN, "tech")
        assert exc.value.error_code == "INVALID_RULE_VALUE"
