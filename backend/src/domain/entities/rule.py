import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, List, Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy, Operator

if TYPE_CHECKING:
    # Only for the type hint in resolve_strategy: importing SalesGroup at
    # module level would create a cycle the moment it needs a rule back.
    from domain.entities.sales_group import SalesGroup
    from domain.entities.lead import Lead


# Reflection over any attribute name let a rule read tenant_id or an internal
# value object. Scoring is a business concept: these are the fields a manager
# may reason about, plus anything the source itself supplied.
SCORABLE_FIELDS = frozenset(
    {"first_name", "last_name", "email", "company", "industry", "budget", "phone", "score"}
)
_CUSTOM_PREFIX = "custom_attributes."
_MISSING = object()


@dataclass
class ScoringRule:
    """A criterion that adds or subtracts points from a lead.

    The comparison lives here rather than in the engine: a rule that cannot
    evaluate itself is an anaemic record, and the engine ended up owning
    business semantics it had no business owning."""

    id: UUID
    tenant_id: UUID
    name: str
    field: str
    operator: Operator
    value: Any
    score_delta: int
    priority: int = 0
    is_active: bool = True

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID],
        name: str,
        field: str,
        operator: Union[Operator, str],
        value: Any,
        score_delta: int,
        priority: int = 0,
        is_active: bool = True,
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "ScoringRule":
        clean_field = (field or "").strip()
        if not clean_field:
            raise DomainException(
                "El campo de la regla no puede estar vacío",
                error_code="INVALID_RULE_FIELD",
            )
        if not clean_field.startswith(_CUSTOM_PREFIX) and clean_field not in SCORABLE_FIELDS:
            raise DomainException(
                f"El campo '{clean_field}' no es puntuable",
                error_code="FIELD_NOT_SCORABLE",
            )
        op = Operator(operator) if isinstance(operator, str) else operator
        if op == Operator.IN and not isinstance(value, (list, tuple)):
            raise DomainException(
                "El operador IN exige una lista de valores",
                error_code="INVALID_RULE_VALUE",
            )
        return cls(
            id=UUID(str(rule_id)) if rule_id else uuid.uuid4(),
            tenant_id=UUID(str(tenant_id)),
            name=name,
            field=clean_field,
            operator=op,
            value=value,
            score_delta=score_delta,
            priority=priority,
            is_active=is_active,
        )

    def matches(self, lead: "Lead") -> bool:
        actual = self._field_value(lead)
        if actual is _MISSING:
            # A lead with no such field genuinely does not equal the target,
            # so only NOT_EQUALS is satisfied by absence.
            return self.operator == Operator.NOT_EQUALS

        if self.operator == Operator.EQUALS:
            return self._equal(actual, self.value)
        if self.operator == Operator.NOT_EQUALS:
            return not self._equal(actual, self.value)
        if self.operator == Operator.GREATER_THAN:
            return self._compare(actual, self.value, greater=True)
        if self.operator == Operator.LESS_THAN:
            return self._compare(actual, self.value, greater=False)
        if self.operator == Operator.CONTAINS:
            if isinstance(actual, str):
                return str(self.value) in actual
            if isinstance(actual, (list, tuple, dict)):
                return self.value in actual
            return False
        if self.operator == Operator.IN:
            return isinstance(self.value, (list, tuple)) and self._in(actual, self.value)
        return False

    def _field_value(self, lead: "Lead") -> Any:
        if self.field.startswith(_CUSTOM_PREFIX):
            key = self.field[len(_CUSTOM_PREFIX):]
            return lead.custom_attributes.get(key, _MISSING)
        raw = getattr(lead, self.field, _MISSING)
        if raw is _MISSING or raw is None:
            return _MISSING
        # Value objects expose their payload as .value or .amount.
        for attr in ("amount", "value"):
            if hasattr(raw, attr):
                return getattr(raw, attr)
        return raw

    @staticmethod
    def _equal(actual: Any, expected: Any) -> bool:
        if actual == expected:
            return True
        as_numbers = ScoringRule._as_decimals(actual, expected)
        if as_numbers is not None:
            return as_numbers[0] == as_numbers[1]
        return str(actual) == str(expected)

    @staticmethod
    def _compare(actual: Any, expected: Any, greater: bool) -> bool:
        as_numbers = ScoringRule._as_decimals(actual, expected)
        if as_numbers is None:
            return False
        left, right = as_numbers
        return left > right if greater else left < right

    @staticmethod
    def _in(actual: Any, options: Union[list, tuple]) -> bool:
        return any(ScoringRule._equal(actual, option) for option in options)

    @staticmethod
    def _as_decimals(left: Any, right: Any) -> Optional[tuple]:
        """Decimal, never float: money compared through binary floating point
        gives wrong answers for values a manager typed exactly."""
        try:
            return Decimal(str(left)), Decimal(str(right))
        except (InvalidOperation, ValueError, TypeError):
            return None


@dataclass
class AssignmentRule:
    """Decides which agents may receive a lead of a given score.

    Replaces the free-form routing rule that came before it. The
    differences are what made that one unusable: no name to show in an
    interface, no upper bound so bands could not be expressed, no priority
    so ties resolved by whatever order the database returned rows, and a
    rotation cursor living in memory."""

    id: UUID
    tenant_id: UUID
    name: str
    min_score: int = 0
    max_score: Optional[int] = None
    target_group_id: Optional[UUID] = None
    target_agent_ids: List[UUID] = field(default_factory=list)
    agent_match_mode: AgentMatchMode = AgentMatchMode.ANY
    strategy: Optional[AssignmentStrategy] = None
    priority: int = 0
    is_active: bool = True
    rr_cursor: int = 0

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID],
        name: str,
        min_score: int = 0,
        max_score: Optional[int] = None,
        target_group_id: Optional[Union[str, UUID]] = None,
        target_agent_ids: Optional[List[Union[str, UUID]]] = None,
        agent_match_mode: Union[str, AgentMatchMode] = AgentMatchMode.ANY,
        strategy: Optional[Union[str, AssignmentStrategy]] = None,
        priority: int = 0,
        is_active: bool = True,
        rr_cursor: int = 0,
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "AssignmentRule":
        clean_name = (name or "").strip()
        if not clean_name:
            raise DomainException(
                "El nombre de la regla no puede estar vacío",
                error_code="INVALID_RULE_NAME",
            )
        if max_score is not None and max_score < min_score:
            raise DomainException(
                "La puntuación máxima no puede ser menor que la mínima",
                error_code="INVALID_SCORE_BAND",
            )

        if not target_group_id and not target_agent_ids:
            raise DomainException(
                "La regla debe apuntar a un grupo o a asesores concretos",
                error_code="RULE_WITHOUT_TARGET",
            )

        return cls.restore(
            tenant_id=tenant_id,
            name=clean_name,
            min_score=min_score,
            max_score=max_score,
            target_group_id=target_group_id,
            target_agent_ids=target_agent_ids,
            agent_match_mode=agent_match_mode,
            strategy=strategy,
            priority=priority,
            is_active=is_active,
            rr_cursor=rr_cursor,
            rule_id=rule_id,
        )

    @classmethod
    def restore(
        cls,
        tenant_id: Union[str, UUID],
        name: str,
        min_score: int = 0,
        max_score: Optional[int] = None,
        target_group_id: Optional[Union[str, UUID]] = None,
        target_agent_ids: Optional[List[Union[str, UUID]]] = None,
        agent_match_mode: Union[str, AgentMatchMode] = AgentMatchMode.ANY,
        strategy: Optional[Union[str, AssignmentStrategy]] = None,
        priority: int = 0,
        is_active: bool = True,
        rr_cursor: int = 0,
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "AssignmentRule":
        """Rebuild a stored rule, applying no input validation.

        Deleting a group nulls target_group_id by design, so storage can
        legitimately hold a rule with no target for the manager to resolve.
        create() rejects that state; reading it back must not, or one group
        deletion would break every ingestion for the organization."""
        parsed_agent_ids = [UUID(str(i)) for i in target_agent_ids] if target_agent_ids else []
        parsed_group_id = UUID(str(target_group_id)) if target_group_id else None

        mode = (
            agent_match_mode
            if isinstance(agent_match_mode, AgentMatchMode)
            else AgentMatchMode(agent_match_mode)
        )
        parsed_strategy: Optional[AssignmentStrategy]
        if strategy is None:
            parsed_strategy = None
        elif isinstance(strategy, AssignmentStrategy):
            parsed_strategy = strategy
        else:
            parsed_strategy = AssignmentStrategy(strategy)

        return cls(
            id=UUID(str(rule_id)) if rule_id else uuid.uuid4(),
            tenant_id=UUID(str(tenant_id)),
            name=(name or "").strip(),
            min_score=min_score,
            max_score=max_score,
            target_group_id=parsed_group_id,
            target_agent_ids=parsed_agent_ids,
            agent_match_mode=mode,
            strategy=parsed_strategy,
            priority=priority,
            is_active=is_active,
            rr_cursor=rr_cursor,
        )

    def matches_score(self, score: int) -> bool:
        if score < self.min_score:
            return False
        return self.max_score is None or score <= self.max_score

    def resolve_strategy(self, group: Optional["SalesGroup"]) -> AssignmentStrategy:
        """The rule's own strategy, or the group's, or the safe default."""
        if self.strategy is not None:
            return self.strategy
        if group is not None:
            return group.default_strategy
        return AssignmentStrategy.LOWEST_LOAD

    def advance_cursor(self, size: int) -> int:
        """Return the index to use now and move the cursor past it.

        The modulo is applied on read, not on write, so the cursor stays valid
        when agents join or leave the group between two assignments."""
        if size <= 0:
            raise DomainException(
                "No hay candidatos sobre los que rotar",
                error_code="EMPTY_CANDIDATE_POOL",
            )
        index = self.rr_cursor % size
        self.rr_cursor = index + 1
        return index
