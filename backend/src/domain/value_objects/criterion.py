from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Union

from domain.exceptions import DomainException
from domain.value_objects.criterion_comparison import MISSING, compare, equal, in_options, is_empty
from domain.value_objects.enums import Operator

if TYPE_CHECKING:
    from domain.leads.lead import Lead


# Reflection over any attribute name let a rule read tenant_id or an internal
# value object. Scoring is a business concept: these are the fields a manager
# may reason about, plus anything the source itself supplied.
EVALUABLE_FIELDS = frozenset(
    {"first_name", "last_name", "email", "company", "industry", "budget", "phone", "score"}
)
_CUSTOM_PREFIX = "custom_attributes."


@dataclass(frozen=True)
class Criterion:
    """One condition of a rule: this field, compared this way, to this value.

    Shared by the three stages — viability, scoring and assignment — so a
    manager learns to write a condition once and reuses it everywhere."""

    field: str
    operator: Operator
    value: Any = None

    @classmethod
    def create(
        cls,
        field: str,
        operator: Union[Operator, str],
        value: Any = None,
    ) -> "Criterion":
        clean_field = (field or "").strip()
        if not clean_field:
            raise DomainException(
                "El campo de la condición no puede estar vacío",
                error_code="INVALID_RULE_FIELD",
            )
        if not clean_field.startswith(_CUSTOM_PREFIX) and clean_field not in EVALUABLE_FIELDS:
            raise DomainException(
                f"El campo '{clean_field}' no es evaluable",
                error_code="FIELD_NOT_SCORABLE",
            )
        op = Operator(operator) if isinstance(operator, str) else operator
        if op == Operator.IN and not isinstance(value, (list, tuple)):
            raise DomainException(
                "El operador IN exige una lista de valores",
                error_code="INVALID_RULE_VALUE",
            )
        return cls(field=clean_field, operator=op, value=value)

    def matches(self, lead: "Lead") -> bool:
        actual = self._field_value(lead)

        # Emptiness is answered before the missing-field short circuit on
        # purpose: an absent field IS empty, and routing it through the branch
        # below would make IS_EMPTY false in exactly the case it must detect.
        if self.operator == Operator.IS_EMPTY:
            return is_empty(actual)
        if self.operator == Operator.IS_NOT_EMPTY:
            return not is_empty(actual)

        if actual is MISSING:
            # A lead with no such field genuinely does not equal the target,
            # so only NOT_EQUALS is satisfied by absence.
            return self.operator == Operator.NOT_EQUALS

        if self.operator == Operator.EQUALS:
            return equal(actual, self.value)
        if self.operator == Operator.NOT_EQUALS:
            return not equal(actual, self.value)
        if self.operator == Operator.GREATER_THAN:
            return compare(actual, self.value, greater=True)
        if self.operator == Operator.LESS_THAN:
            return compare(actual, self.value, greater=False)
        if self.operator == Operator.CONTAINS:
            if isinstance(actual, str):
                return str(self.value) in actual
            if isinstance(actual, (list, tuple, dict)):
                return self.value in actual
            return False
        if self.operator == Operator.IN:
            return isinstance(self.value, (list, tuple)) and in_options(actual, self.value)
        return False

    def as_dict(self) -> Dict[str, Any]:
        """JSONB-serialisable form. The operator travels as its plain value."""
        return {"field": self.field, "operator": self.operator.value, "value": self.value}

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Criterion":
        return cls.create(
            field=raw.get("field", ""),
            operator=raw.get("operator", Operator.EQUALS),
            value=raw.get("value"),
        )

    def _field_value(self, lead: "Lead") -> Any:
        if self.field.startswith(_CUSTOM_PREFIX):
            key = self.field[len(_CUSTOM_PREFIX):]
            return lead.custom_attributes.get(key, MISSING)
        raw = getattr(lead, self.field, MISSING)
        if raw is MISSING or raw is None:
            return MISSING
        # Value objects expose their payload as .value or .amount.
        for attr in ("amount", "value"):
            if hasattr(raw, attr):
                return getattr(raw, attr)
        return raw


def all_match(conditions: List[Criterion], lead: "Lead") -> bool:
    """A rule holds when every one of its conditions holds.

    There is no OR: alternatives are written as separate rules. `all` over an
    empty list is True, which is what an assignment rule with no conditions
    needs — it discriminates by score band alone."""
    return all(condition.matches(lead) for condition in conditions)
