import uuid
from decimal import Decimal
from typing import Any

import pytest

from domain.entities.lead import Lead
from domain.exceptions import DomainException
from domain.value_objects.criterion import Criterion, all_match
from domain.value_objects.enums import Operator

_TENANT = uuid.uuid4()


def _lead(**overrides: Any) -> Lead:
    base = dict(
        tenant_id=_TENANT, source_id=uuid.uuid4(), first_name="Ana", last_name="Diaz", email="ana@x.test",
        company="Acme", budget=1000, industry="tech",
    )
    base.update(overrides)
    return Lead.create(**base)


def _criterion(field: str, operator: Operator, value: Any = None) -> Criterion:
    return Criterion.create(field=field, operator=operator, value=value)


class TestOperators:
    def test_equals_matches_across_string_and_number(self):
        assert _criterion("budget", Operator.EQUALS, "1000").matches(_lead()) is True

    def test_not_equals_applies_the_same_coercion_as_equals(self):
        """Both may not be true for the same pair; that was the old bug."""
        lead = _lead()
        equals = _criterion("budget", Operator.EQUALS, "1000").matches(lead)
        not_equals = _criterion("budget", Operator.NOT_EQUALS, "1000").matches(lead)
        assert equals is True
        assert not_equals is False

    def test_numeric_comparison_keeps_decimal_precision(self):
        lead = _lead(budget=Decimal("0.30"))
        assert _criterion("budget", Operator.GREATER_THAN, Decimal("0.10")).matches(lead) is True
        assert _criterion("budget", Operator.LESS_THAN, Decimal("0.10")).matches(lead) is False

    def test_in_works_with_a_real_list(self):
        assert _criterion("industry", Operator.IN, ["tech", "finance"]).matches(_lead()) is True
        assert _criterion("industry", Operator.IN, ["retail"]).matches(_lead()) is False

    def test_contains_looks_inside_a_string(self):
        assert _criterion("company", Operator.CONTAINS, "cm").matches(_lead()) is True


class TestMissingField:
    def test_a_missing_field_is_false_for_positive_operators(self):
        lead = _lead()
        assert _criterion("custom_attributes.absent", Operator.EQUALS, "x").matches(lead) is False
        assert _criterion("custom_attributes.absent", Operator.GREATER_THAN, 1).matches(lead) is False

    def test_a_missing_field_is_true_for_not_equals(self):
        """A lead with no 'campaign' genuinely does not equal 'summer'."""
        lead = _lead()
        assert _criterion("custom_attributes.absent", Operator.NOT_EQUALS, "x").matches(lead) is True


class TestAllowedFields:
    def test_a_field_outside_the_allow_list_is_rejected(self):
        """Free reflection let a rule read tenant_id or hashed internals."""
        with pytest.raises(DomainException) as exc:
            _criterion("tenant_id", Operator.EQUALS, str(_TENANT))
        assert exc.value.error_code == "FIELD_NOT_SCORABLE"

    def test_custom_attributes_are_always_allowed(self):
        criterion = _criterion("custom_attributes.employee_count", Operator.GREATER_THAN, 10)
        assert criterion.matches(_lead(custom_attributes={"employee_count": 50})) is True

    def test_the_in_operator_demands_a_list(self):
        with pytest.raises(DomainException) as exc:
            _criterion("industry", Operator.IN, "tech")
        assert exc.value.error_code == "INVALID_RULE_VALUE"

    def test_an_empty_or_blank_field_is_rejected(self):
        for blank in ("", "   "):
            with pytest.raises(DomainException) as exc:
                Criterion.create(field=blank, operator=Operator.EQUALS, value="x")
            assert exc.value.error_code == "INVALID_RULE_FIELD"


class TestEmptiness:
    """IS_EMPTY / IS_NOT_EMPTY: what this task exists to add."""

    def test_is_empty_on_an_absent_field_is_true(self):
        assert _criterion("custom_attributes.absent", Operator.IS_EMPTY).matches(_lead()) is True

    def test_is_empty_on_none_in_custom_attributes_is_true(self):
        lead = _lead(custom_attributes={"note": None})
        assert _criterion("custom_attributes.note", Operator.IS_EMPTY).matches(lead) is True

    def test_is_empty_on_an_empty_string_is_true(self):
        lead = _lead(company="")
        assert _criterion("company", Operator.IS_EMPTY).matches(lead) is True

    def test_is_empty_on_whitespace_only_is_true(self):
        """Product decision, not an implementation detail: a CSV column left
        blank arrives as spaces, and a rule that misses it is indistinguishable
        from a broken one."""
        lead = _lead(company="   ")
        assert _criterion("company", Operator.IS_EMPTY).matches(lead) is True

    def test_is_empty_on_a_real_value_is_false(self):
        assert _criterion("company", Operator.IS_EMPTY).matches(_lead()) is False

    def test_is_not_empty_is_the_exact_negation(self):
        """Negation of each of the five IS_EMPTY cases above."""
        absent = _lead()
        none_custom = _lead(custom_attributes={"note": None})
        empty = _lead(company="")
        blank = _lead(company="   ")
        present = _lead()

        assert _criterion("custom_attributes.absent", Operator.IS_NOT_EMPTY).matches(absent) is False
        assert _criterion("custom_attributes.note", Operator.IS_NOT_EMPTY).matches(none_custom) is False
        assert _criterion("company", Operator.IS_NOT_EMPTY).matches(empty) is False
        assert _criterion("company", Operator.IS_NOT_EMPTY).matches(blank) is False
        assert _criterion("company", Operator.IS_NOT_EMPTY).matches(present) is True


class TestAllMatch:
    def test_all_match_with_no_conditions_is_true(self):
        assert all_match([], _lead()) is True

    def test_all_match_is_false_when_one_condition_fails(self):
        conditions = [
            _criterion("industry", Operator.EQUALS, "tech"),
            _criterion("company", Operator.EQUALS, "not-acme"),
        ]
        assert all_match(conditions, _lead()) is False


class TestSerialization:
    def test_as_dict_and_from_dict_round_trip(self):
        criterion = _criterion("budget", Operator.GREATER_THAN, 500)
        assert Criterion.from_dict(criterion.as_dict()) == criterion
