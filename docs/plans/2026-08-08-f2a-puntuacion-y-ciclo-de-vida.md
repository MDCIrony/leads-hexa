# F2a — Puntuación y ciclo de vida del lead: Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que un lead recorra su ciclo de vida completo —puntuado con reglas que de verdad se cumplen, asignado, reasignado, liberado o descartado— y que el asesor pueda ver por fin sus propios leads.

**Architecture:** `ScoringRule` deja de ser un registro anémico y pasa a ser una especificación evaluable: la lógica de comparación vive en la regla, no en el motor. El motor se limita a ordenar, acumular y devolver el **desglose** de lo aplicado. El `Lead` gana una máquina de estados con invariantes de transición reales, en vez de un `assign_to_agent` que acepta cualquier estado y pisa en silencio la asignación anterior.

**Tech Stack:** Python 3.12+, FastAPI, psycopg 3 (raw SQL, sin ORM), pytest, uv, PostgreSQL 16, Docker Compose.

**Estado de partida:** F1 cerrada. **256 tests en verde**, guardián de arquitectura 4/4, tres migraciones aplicadas, motor de asignación con cascada y cursor persistido.

## Alcance: por qué F2 se parte en dos

F2 en el spec cubre dos subsistemas independientes. Este plan es el primero:

| | Contenido | Depende de |
|---|---|---|
| **F2a** (este plan) | Motor de puntuación §7.1, `ScoringRule` evaluable, máquina de estados del lead, asignación manual, descarte, `/leads/mine` | F1 |
| **F2b** (siguiente) | `LeadSource`, `IntakeRecord`, `IntakeError`, pipeline unificado, cierre de la ingesta sin autenticar, migración 005 | **F2a** |

F2b necesita el motor de puntuación corregido y los estados nuevos, así que este plan va primero. Cada uno entrega software demostrable por su cuenta.

## Global Constraints

- Todo el código, nombres, docstrings y comentarios **en inglés**. La documentación en español.
- **Prohibido cualquier ORM.** SQL parametrizado sobre `psycopg` 3, marcadores `%s`.
- `domain/` no importa nada fuera de la biblioteca estándar.
- `application/` importa sólo de `domain/` y de la biblioteca estándar. **Nunca** de `infrastructure/`.
- Pydantic vive **sólo** en los adaptadores.
- Los puertos son `abc.ABC` con `@abc.abstractmethod`. Los DTOs de aplicación son `@dataclass(frozen=True)`.
- **El guardián `tests/architecture/` debe permanecer en 4/4 en todo momento.**
- `pytest -m unit` debe pasar sin base de datos, sin red y sin variables de entorno.
- Los mensajes de las excepciones de dominio van **en español**, siguiendo a sus vecinos ya existentes.
- Los comentarios explican el **porqué**, nunca el qué.
- Mensajes de commit en inglés, `type(scope): description`. **Sin** `Co-authored-by`.
- No `git push`, no ramas nuevas. Rama de trabajo: `repo-status-mvp`.
- Anota los tipos en las funciones auxiliares de test. Un parámetro que pueda recibir `None` se declara `Optional[...]`.
- **Puertos del host:** PostgreSQL en **5433**, API en **8001**. Dentro de la red de compose siguen siendo 5432 y 8000.
- **No hay datos que preservar.** Las migraciones se aplican sobre base vacía; ningún paso escribe código de backfill.
- **La migración de esta fase es la `004`.** La `003` la ocupan los grupos.

```bash
export DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export TEST_DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export JWT_SECRET=test-secret-do-not-use-in-production
```

## Agrupación en despachos

| Bloque | Tareas | Validación |
|---|---|---|
| A | 1 + 2 + 3 + 4 | `pytest` (dominio puro, sin base de datos) |
| B | 5 + 6 | `pytest` + base de datos |
| C | 7 + 8 | Docker + `curl` + base de datos, circuito completo |

## Mapa de ficheros

**Se crean:** `domain/value_objects/score_breakdown.py` · `application/ports/input/lead_lifecycle_use_case_ports.py` · `application/use_cases/lead_lifecycle_use_cases.py` · `migrations/004_lead_lifecycle_and_scoring.sql` · sus tests.

**Se modifican:** `domain/value_objects/enums.py` · `domain/entities/{lead,rule}.py` · `domain/services/scoring_engine.py` · `application/dtos/{commands,queries}.py` · `application/use_cases/ingest_lead_use_case.py` · `application/ports/output/lead_repository_port.py` · `infrastructure/adapters/output/persistence/raw_sql_{lead,rule}_repository.py` · `infrastructure/adapters/input/api/{lead_router,rule_router,schemas,dependencies}.py` · `infrastructure/di/container.py` · `tests/unit/mocks/{in_memory_lead_repo,in_memory_rule_repo}.py` · `docs/api/endpoints.md`.

---

## Task 1: Estados nuevos y campos de traza del `Lead`

**Files:**
- Modify: `backend/src/domain/value_objects/enums.py`
- Modify: `backend/src/domain/entities/lead.py`
- Test: `backend/tests/unit/domain/test_entities.py`

**Interfaces:**
- Produces: `LeadStatus.UNASSIGNED`, `LeadStatus.DISCARDED`. `Lead.assigned_at: Optional[datetime]`, `Lead.discard_reason: Optional[str]`, `Lead.updated_at: datetime`.

Hoy `LeadStatus` tiene cinco valores y ninguno describe "calificado pero sin asesor": un lead que el motor no reparte se queda `QUALIFIED` y es indistinguible de uno que aún no ha pasado por el reparto. `FAILED` **se conserva** en esta fase; lo retira F2b, cuando `IntakeRecord` recoja lo que no valida.

- [ ] **Step 1: Escribir el test que falla**

Añadir a `backend/tests/unit/domain/test_entities.py`:

```python
class TestLeadLifecycleFields:
    def test_the_new_statuses_exist(self):
        assert LeadStatus.UNASSIGNED.value == "UNASSIGNED"
        assert LeadStatus.DISCARDED.value == "DISCARDED"

    def test_a_fresh_lead_carries_no_assignment_trace(self):
        lead = Lead.create(
            tenant_id=uuid.uuid4(), first_name="Ana", last_name="Diaz",
            email="ana@x.test", company="C", budget=100, industry="tech",
        )
        assert lead.assigned_at is None
        assert lead.discard_reason is None
        assert lead.updated_at is not None
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/domain/test_entities.py::TestLeadLifecycleFields -v`
Expected: FAIL con `AttributeError: UNASSIGNED`.

- [ ] **Step 3: Añadir los estados**

En `backend/src/domain/value_objects/enums.py`, sustituir la clase `LeadStatus` entera por:

```python
class LeadStatus(str, Enum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    DISCARDED = "DISCARDED"
    # Retired in F2b, when IntakeRecord captures what fails validation and a
    # Lead stops being the place where a rejected payload lands.
    FAILED = "FAILED"
```

- [ ] **Step 4: Añadir los campos al `Lead`**

En `backend/src/domain/entities/lead.py`, añadir tras `assigned_agent_id` en el cuerpo del dataclass:

```python
    assigned_at: Optional[datetime] = None
    discard_reason: Optional[str] = None
```

y tras `created_at`:

```python
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

En la firma de `create`, añadir tras `assigned_agent_id`:

```python
        assigned_at: Optional[datetime] = None,
        discard_reason: Optional[str] = None,
        updated_at: Optional[datetime] = None,
```

y en el `return cls(...)`, añadir:

```python
            assigned_at=assigned_at,
            discard_reason=discard_reason,
            updated_at=updated_at or datetime.now(timezone.utc),
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/domain/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/domain/value_objects/enums.py backend/src/domain/entities/lead.py backend/tests/unit/domain/test_entities.py
git commit -m "feat(domain): add the unassigned and discarded statuses with their trace fields"
```

---

## Task 2: La máquina de estados del `Lead`

**Files:**
- Modify: `backend/src/domain/entities/lead.py`
- Modify: `backend/src/domain/services/assignment_engine.py:_apply_strategy`
- Test: `backend/tests/unit/domain/test_lead_state_machine.py` (crear)

**Interfaces:**
- Consumes: `LeadStatus.UNASSIGNED`, `LeadStatus.DISCARDED`, `Lead.assigned_at` (Task 1).
- Produces: `Lead.assign_to(agent_id, tenant_id, at=None)`, `Lead.reassign_to(agent_id, tenant_id, at=None)`, `Lead.unassign()`, `Lead.discard(reason)`, `Lead.leave_unassigned()`. **`assign_to_agent` desaparece.**

Hoy `assign_to_agent` acepta cualquier estado y sobrescribe en silencio una asignación previa: un lead ya repartido puede reasignarse sin traza, y uno `DISQUALIFIED` puede acabar asignado. Las transiciones pasan a ser explícitas.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/unit/domain/test_lead_state_machine.py`:

```python
import uuid
from typing import Optional

import pytest

from domain.entities.lead import Lead
from domain.exceptions import DomainException
from domain.value_objects.enums import LeadStatus

_TENANT = uuid.uuid4()


def _lead(status: LeadStatus = LeadStatus.QUALIFIED, tenant_id: Optional[uuid.UUID] = None) -> Lead:
    return Lead.create(
        tenant_id=tenant_id or _TENANT, first_name="Ana", last_name="Diaz",
        email="ana@x.test", company="C", budget=100, industry="tech", status=status,
    )


class TestAssign:
    def test_assigning_a_qualified_lead_records_the_moment(self):
        lead = _lead(LeadStatus.QUALIFIED)
        agent = uuid.uuid4()

        lead.assign_to(agent, _TENANT)

        assert lead.status == LeadStatus.ASSIGNED
        assert lead.assigned_agent_id is not None
        assert lead.assigned_agent_id.value == agent
        assert lead.assigned_at is not None

    def test_an_unassigned_lead_can_be_assigned_by_hand(self):
        lead = _lead(LeadStatus.UNASSIGNED)
        lead.assign_to(uuid.uuid4(), _TENANT)
        assert lead.status == LeadStatus.ASSIGNED

    def test_a_disqualified_lead_cannot_be_assigned(self):
        """The engine must never reach it, and neither may the manager."""
        lead = _lead(LeadStatus.DISQUALIFIED)
        with pytest.raises(DomainException) as exc:
            lead.assign_to(uuid.uuid4(), _TENANT)
        assert exc.value.error_code == "INVALID_LEAD_TRANSITION"

    def test_assigning_an_already_assigned_lead_is_refused(self):
        """Overwriting in silence is what reassign_to exists to prevent."""
        lead = _lead(LeadStatus.QUALIFIED)
        lead.assign_to(uuid.uuid4(), _TENANT)
        with pytest.raises(DomainException) as exc:
            lead.assign_to(uuid.uuid4(), _TENANT)
        assert exc.value.error_code == "INVALID_LEAD_TRANSITION"

    def test_an_agent_of_another_organization_is_refused(self):
        lead = _lead(LeadStatus.QUALIFIED)
        with pytest.raises(DomainException) as exc:
            lead.assign_to(uuid.uuid4(), uuid.uuid4())
        assert exc.value.error_code == "CROSS_TENANT_ASSIGNMENT"


class TestReassign:
    def test_reassigning_replaces_the_agent_and_the_moment(self):
        lead = _lead(LeadStatus.QUALIFIED)
        first, second = uuid.uuid4(), uuid.uuid4()
        lead.assign_to(first, _TENANT)
        first_at = lead.assigned_at

        lead.reassign_to(second, _TENANT)

        assert lead.assigned_agent_id.value == second
        assert lead.assigned_at >= first_at

    def test_reassigning_something_never_assigned_is_refused(self):
        lead = _lead(LeadStatus.QUALIFIED)
        with pytest.raises(DomainException) as exc:
            lead.reassign_to(uuid.uuid4(), _TENANT)
        assert exc.value.error_code == "INVALID_LEAD_TRANSITION"


class TestUnassignAndDiscard:
    def test_releasing_an_assigned_lead_clears_the_agent(self):
        lead = _lead(LeadStatus.QUALIFIED)
        lead.assign_to(uuid.uuid4(), _TENANT)

        lead.unassign()

        assert lead.status == LeadStatus.UNASSIGNED
        assert lead.assigned_agent_id is None
        assert lead.assigned_at is None

    def test_discarding_requires_a_reason(self):
        lead = _lead(LeadStatus.QUALIFIED)
        with pytest.raises(DomainException) as exc:
            lead.discard("   ")
        assert exc.value.error_code == "DISCARD_WITHOUT_REASON"

    def test_a_lead_can_be_discarded_from_any_live_state(self):
        for status in (LeadStatus.NEW, LeadStatus.QUALIFIED, LeadStatus.UNASSIGNED, LeadStatus.ASSIGNED):
            lead = _lead(status)
            lead.discard("duplicado")
            assert lead.status == LeadStatus.DISCARDED
            assert lead.discard_reason == "duplicado"

    def test_discarding_twice_is_refused(self):
        lead = _lead(LeadStatus.QUALIFIED)
        lead.discard("duplicado")
        with pytest.raises(DomainException) as exc:
            lead.discard("otra vez")
        assert exc.value.error_code == "INVALID_LEAD_TRANSITION"

    def test_a_qualified_lead_with_no_candidate_is_left_unassigned(self):
        lead = _lead(LeadStatus.QUALIFIED)
        lead.leave_unassigned()
        assert lead.status == LeadStatus.UNASSIGNED
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/domain/test_lead_state_machine.py -q`
Expected: FAIL con `AttributeError: 'Lead' object has no attribute 'assign_to'`.

- [ ] **Step 3: Sustituir `assign_to_agent` por la máquina de estados**

En `backend/src/domain/entities/lead.py`, borrar el método `assign_to_agent` entero y añadir en su lugar:

```python
    _ASSIGNABLE = (LeadStatus.QUALIFIED, LeadStatus.UNASSIGNED)
    _DISCARDABLE = (
        LeadStatus.NEW,
        LeadStatus.QUALIFIED,
        LeadStatus.UNASSIGNED,
        LeadStatus.ASSIGNED,
    )

    def assign_to(
        self,
        agent_id: Union[str, UUID, AgentId],
        agent_tenant_id: Union[str, UUID, TenantId],
        at: Optional[datetime] = None,
    ) -> None:
        """Hand the lead to an agent for the first time.

        Refuses an already assigned lead on purpose: silently overwriting the
        previous agent is what made reassignments untraceable. Use
        reassign_to for that, which says so out loud."""
        if self.status not in self._ASSIGNABLE:
            raise DomainException(
                f"No se puede asignar un lead en estado {self.status.value}",
                error_code="INVALID_LEAD_TRANSITION",
            )
        self._bind_agent(agent_id, agent_tenant_id, at)

    def reassign_to(
        self,
        agent_id: Union[str, UUID, AgentId],
        agent_tenant_id: Union[str, UUID, TenantId],
        at: Optional[datetime] = None,
    ) -> None:
        if self.status != LeadStatus.ASSIGNED:
            raise DomainException(
                f"Sólo se reasigna un lead ya asignado, no uno en estado {self.status.value}",
                error_code="INVALID_LEAD_TRANSITION",
            )
        self._bind_agent(agent_id, agent_tenant_id, at)

    def unassign(self) -> None:
        if self.status != LeadStatus.ASSIGNED:
            raise DomainException(
                f"Sólo se libera un lead asignado, no uno en estado {self.status.value}",
                error_code="INVALID_LEAD_TRANSITION",
            )
        self.assigned_agent_id = None
        self.assigned_at = None
        self.status = LeadStatus.UNASSIGNED
        self._touch()

    def leave_unassigned(self) -> None:
        """Qualified, but no rule produced a candidate. Needs a manager."""
        if self.status != LeadStatus.QUALIFIED:
            raise DomainException(
                f"Sólo un lead calificado queda sin asignar, no uno en estado {self.status.value}",
                error_code="INVALID_LEAD_TRANSITION",
            )
        self.status = LeadStatus.UNASSIGNED
        self._touch()

    def discard(self, reason: str) -> None:
        if self.status not in self._DISCARDABLE:
            raise DomainException(
                f"No se puede descartar un lead en estado {self.status.value}",
                error_code="INVALID_LEAD_TRANSITION",
            )
        clean = (reason or "").strip()
        if not clean:
            raise DomainException(
                "El descarte exige un motivo",
                error_code="DISCARD_WITHOUT_REASON",
            )
        self.discard_reason = clean
        self.status = LeadStatus.DISCARDED
        self._touch()

    def _bind_agent(
        self,
        agent_id: Union[str, UUID, AgentId],
        agent_tenant_id: Union[str, UUID, TenantId],
        at: Optional[datetime],
    ) -> None:
        tenant = agent_tenant_id if isinstance(agent_tenant_id, TenantId) else TenantId(agent_tenant_id)
        if tenant.value != self.tenant_id.value:
            raise DomainException(
                "El asesor pertenece a otra organización",
                error_code="CROSS_TENANT_ASSIGNMENT",
            )
        self.assigned_agent_id = agent_id if isinstance(agent_id, AgentId) else AgentId(agent_id)
        self.assigned_at = at or datetime.now(timezone.utc)
        self.status = LeadStatus.ASSIGNED
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
```

Añadir el import que falta en la cabecera del fichero:

```python
from domain.exceptions import DomainException
```

- [ ] **Step 4: Actualizar los cuatro llamantes de `assign_to_agent`**

Además del motor, lo usan tres tests. `rg "assign_to_agent" src/ tests/` los localiza:

| Fichero | Cambio |
|---|---|
| `src/domain/services/assignment_engine.py:108` | Ver el bloque de abajo |
| `tests/unit/domain/test_entities.py:35` | `lead.assign_to(agent_id, lead.tenant_id)` |
| `tests/integration/test_raw_sql_lead_repo.py:69,73` | `lead.assign_to(ana, lead.tenant_id)` y, para el segundo, **`reassign_to`**: el lead ya está asignado |
| `tests/integration/test_raw_sql_lead_repo.py:80` | Asigna un lead `DISQUALIFIED`. La máquina de estados nueva lo **rechaza, y hace bien**. Reescribe el caso para que afirme el rechazo con `INVALID_LEAD_TRANSITION`, o parte de un lead `QUALIFIED` si lo que ese test comprobaba era otra cosa. **No relajes el invariante para que el test viejo siga pasando.** |

En el motor de asignación:

En `backend/src/domain/services/assignment_engine.py`, dentro de `_apply_strategy`, sustituir la línea:

```python
        lead.assign_to_agent(selected.id)
```

por:

```python
        # The engine only ever reaches agents of the lead's own organization,
        # so passing the lead's tenant satisfies the entity's cross-tenant
        # invariant without widening the engine's signature.
        lead.assign_to(selected.id, lead.tenant_id)
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/domain/ -q`
Expected: PASS, incluidos los tests del motor de asignación que ya existían.

- [ ] **Step 6: Commit**

```bash
git add backend/src/domain/entities/lead.py backend/src/domain/services/assignment_engine.py backend/tests/unit/domain/test_lead_state_machine.py
git commit -m "feat(domain): give the lead a state machine with real transition invariants"
```

---

## Task 3: `ScoringRule` se vuelve una especificación evaluable

**Files:**
- Modify: `backend/src/domain/entities/rule.py`
- Test: `backend/tests/unit/domain/test_scoring_rule.py` (crear)

**Interfaces:**
- Produces: `ScoringRule` con `tenant_id: UUID`, `priority: int = 0`, `is_active: bool = True`, `value: Any` (tipo preservado) y el método `matches(lead) -> bool`. `ScoringRule.create(...)` gana `tenant_id`, `priority`, `is_active`.

Hoy la comparación vive en `ScoringEngine.evaluate_rule` y la regla es un registro anémico. Al llevarla a la entidad se corrigen de paso los cuatro defectos que el spec §7.1 enumera:

1. `NOT_EQUALS` no aplica la coerción que sí aplica `EQUALS`, así que para el mismo par campo/valor **ambos pueden ser verdad a la vez**.
2. Un campo ausente devuelve falso siempre; para `NOT_EQUALS` debe ser **verdadero**.
3. Las comparaciones numéricas pasan por `float`, que pierde precisión sobre `Decimal`.
4. El campo se resuelve por reflexión libre: una regla con `field = "tenant_id"` funciona hoy.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/unit/domain/test_scoring_rule.py`:

```python
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
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/domain/test_scoring_rule.py -q`
Expected: FAIL con `TypeError: create() got an unexpected keyword argument 'tenant_id'`.

- [ ] **Step 3: Reescribir `ScoringRule`**

En `backend/src/domain/entities/rule.py`, sustituir la clase `ScoringRule` entera por:

```python
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
```

Añadir a la cabecera del fichero los imports que faltan:

```python
from decimal import Decimal, InvalidOperation
```

y dentro del bloque `if TYPE_CHECKING:` que ya existe:

```python
    from domain.entities.lead import Lead
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/domain/test_scoring_rule.py -q`
Expected: PASS, 14 casos.

- [ ] **Step 5: Commit**

```bash
git add backend/src/domain/entities/rule.py backend/tests/unit/domain/test_scoring_rule.py
git commit -m "feat(domain): make a scoring rule evaluate itself with correct operator semantics"
```

**Nota:** este paso deja en rojo `tests/unit/domain/test_scoring_engine.py` y el repositorio de reglas, porque `ScoringRule.create` ya exige `tenant_id`. Las tareas 4 y 5 lo resuelven. No parchees desde el dominio.

---

## Task 4: El motor de puntuación devuelve el desglose

**Files:**
- Create: `backend/src/domain/value_objects/score_breakdown.py`
- Modify: `backend/src/domain/services/scoring_engine.py`
- Test: `backend/tests/unit/domain/test_scoring_engine.py`

**Interfaces:**
- Consumes: `ScoringRule.matches(lead)`, `ScoringRule.priority`, `ScoringRule.is_active` (Task 3).
- Produces: `AppliedRule(rule_id: UUID, name: str, score_delta: int)` y `ScoreBreakdown(applied: List[AppliedRule], total: int)`. `ScoringEngine.evaluate(lead, rules) -> ScoreBreakdown`.

Hoy `evaluate` devuelve un entero y el resultado informa `applied_rules_count`, que además cuenta las reglas **consultadas**, no las aplicadas. El desglose es lo que permite que la interfaz explique al gestor por qué un lead puntuó lo que puntuó.

- [ ] **Step 1: Escribir el test que falla**

Sustituir el contenido de `backend/tests/unit/domain/test_scoring_engine.py` por:

```python
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
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/domain/test_scoring_engine.py -q`
Expected: FAIL con `AttributeError: 'int' object has no attribute 'total'`.

- [ ] **Step 3: Crear el value object del desglose**

Crear `backend/src/domain/value_objects/score_breakdown.py`:

```python
from dataclasses import dataclass, field
from typing import List
from uuid import UUID


@dataclass(frozen=True)
class AppliedRule:
    """One rule that actually fired, kept so the interface can explain a score."""

    rule_id: UUID
    name: str
    score_delta: int


@dataclass(frozen=True)
class ScoreBreakdown:
    applied: List[AppliedRule] = field(default_factory=list)
    total: int = 0
```

- [ ] **Step 4: Dar al `Lead` el campo donde vive su desglose**

En `backend/src/domain/entities/lead.py`, añadir al cuerpo del dataclass tras `score`:

```python
    # Stored on the lead, not recomputed from the rules: the rules that
    # produced a score can be edited or deleted afterwards, and the lead must
    # still be able to explain itself.
    score_breakdown: List[AppliedRule] = field(default_factory=list)
```

en la firma de `create`, tras `score`:

```python
        score_breakdown: Optional[List[AppliedRule]] = None,
```

en el `return cls(...)`:

```python
            score_breakdown=score_breakdown or [],
```

y en la cabecera del fichero:

```python
from typing import Any, Dict, List, Optional, Union

from domain.value_objects.score_breakdown import AppliedRule
```

- [ ] **Step 5: Reescribir el motor**

Sustituir el contenido de `backend/src/domain/services/scoring_engine.py` por:

```python
from typing import List

from domain.entities.lead import Lead
from domain.entities.rule import ScoringRule
from domain.value_objects.score_breakdown import AppliedRule, ScoreBreakdown


class ScoringEngine:
    """Accumulates the deltas of the rules a lead satisfies.

    It no longer knows how a comparison works: that moved onto the rule. What
    is left here is ordering, accumulation and the breakdown."""

    def evaluate(self, lead: Lead, rules: List[ScoringRule]) -> ScoreBreakdown:
        applied: List[AppliedRule] = []
        total = 0
        for rule in self._ordered(rules):
            if not rule.matches(lead):
                continue
            applied.append(AppliedRule(rule_id=rule.id, name=rule.name, score_delta=rule.score_delta))
            total += rule.score_delta
            lead.apply_score(rule.score_delta)
        return ScoreBreakdown(applied=applied, total=total)

    @staticmethod
    def _ordered(rules: List[ScoringRule]) -> List[ScoringRule]:
        # The sum is commutative, so priority only shapes the breakdown the
        # manager reads. The id breaks ties so the order is reproducible.
        return sorted(
            (r for r in rules if r.is_active),
            key=lambda r: (-r.priority, str(r.id)),
        )
```

- [ ] **Step 6: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/domain/ -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/domain/value_objects/score_breakdown.py backend/src/domain/services/scoring_engine.py backend/src/domain/entities/lead.py backend/tests/unit/domain/test_scoring_engine.py
git commit -m "feat(domain): return the applied-rule breakdown instead of a bare score"
```

---

## Task 5: Migración 004 y persistencia

**Files:**
- Create: `backend/migrations/004_lead_lifecycle_and_scoring.sql`
- Modify: `backend/src/infrastructure/adapters/output/persistence/raw_sql_lead_repository.py`
- Modify: `backend/src/infrastructure/adapters/output/persistence/raw_sql_rule_repository.py`
- Modify: `backend/src/application/ports/output/lead_repository_port.py`
- Modify: `backend/tests/unit/mocks/in_memory_lead_repo.py`
- Modify: `backend/tests/unit/mocks/in_memory_rule_repo.py`
- Test: `backend/tests/integration/test_lead_lifecycle_persistence.py` (crear)

**Interfaces:**
- Consumes: los campos y estados de las tareas 1-4.
- Produces: `LeadRepositoryPort.list_by_agent(tenant_id, agent_id, limit=100, offset=0) -> List[Lead]`, `LeadRepositoryPort.count_by_agent(tenant_id, agent_id) -> int`, `LeadRepositoryPort.get_by_id_and_tenant(lead_id, tenant_id) -> Optional[Lead]`. `RuleRepositoryPort.get_scoring_rules_by_tenant` devuelve reglas con `tenant_id`, `priority`, `is_active`.

`list_by_tenant` de leads **no tiene `ORDER BY`**: la paginación puede repetir o saltarse filas. Se corrige aquí, igual que se hizo con los asesores en F0.5.

- [ ] **Step 1: Escribir la migración**

Crear `backend/migrations/004_lead_lifecycle_and_scoring.sql`:

```sql
ALTER TABLE leads ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS discard_reason TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
-- The breakdown is stored, not recomputed: the rules that produced a score
-- can be edited or deleted afterwards, and the lead must still explain itself.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS score_breakdown JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 0;
ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- The agent's own dashboard lists their leads newest first.
CREATE INDEX IF NOT EXISTS idx_leads_agent_recent
    ON leads (tenant_id, assigned_agent_id, created_at DESC)
    WHERE assigned_agent_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_leads_tenant_status ON leads (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_scoring_rules_tenant ON scoring_rules (tenant_id, priority DESC);
```

- [ ] **Step 2: Escribir el test de integración que falla**

Crear `backend/tests/integration/test_lead_lifecycle_persistence.py`:

```python
import uuid
from typing import Optional

from domain.entities.lead import Lead
from domain.value_objects.enums import LeadStatus
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import (
    RawSqlLeadRepository,
)

_TENANT = uuid.uuid4()


def _lead(email: str, tenant_id: Optional[uuid.UUID] = None) -> Lead:
    return Lead.create(
        tenant_id=tenant_id or _TENANT, first_name="Ana", last_name="Diaz",
        email=email, company="Acme", budget=1000, industry="tech",
        status=LeadStatus.QUALIFIED,
    )


def test_the_assignment_trace_survives_a_round_trip(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        agent = uuid.uuid4()
        lead = _lead(f"trace-{uuid.uuid4()}@x.test")
        lead.assign_to(agent, _TENANT)
        repo.save(lead)

        stored = repo.get_by_id(lead.id.value)

        assert stored.status == LeadStatus.ASSIGNED
        assert stored.assigned_agent_id.value == agent
        assert stored.assigned_at is not None


def test_a_discarded_lead_keeps_its_reason(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        lead = _lead(f"disc-{uuid.uuid4()}@x.test")
        lead.discard("duplicado")
        repo.save(lead)

        stored = repo.get_by_id(lead.id.value)

        assert stored.status == LeadStatus.DISCARDED
        assert stored.discard_reason == "duplicado"


def test_an_agent_only_sees_their_own_leads(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        tenant = uuid.uuid4()
        mine, theirs = uuid.uuid4(), uuid.uuid4()

        a = _lead(f"mine-{uuid.uuid4()}@x.test", tenant); a.assign_to(mine, tenant); repo.save(a)
        b = _lead(f"theirs-{uuid.uuid4()}@x.test", tenant); b.assign_to(theirs, tenant); repo.save(b)

        found = repo.list_by_agent(tenant, mine)

        assert [str(l.email) for l in found] == [str(a.email)]
        assert repo.count_by_agent(tenant, mine) == 1


def test_reading_a_lead_of_another_organization_returns_nothing(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        lead = _lead(f"other-{uuid.uuid4()}@x.test")
        repo.save(lead)

        assert repo.get_by_id_and_tenant(lead.id.value, _TENANT) is not None
        assert repo.get_by_id_and_tenant(lead.id.value, uuid.uuid4()) is None
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Run: `uv run pytest tests/integration/test_lead_lifecycle_persistence.py -q`
Expected: FAIL con `AttributeError: 'RawSqlLeadRepository' object has no attribute 'list_by_agent'`.

- [ ] **Step 4: Ampliar el puerto de leads**

En `backend/src/application/ports/output/lead_repository_port.py`, añadir:

```python
    @abstractmethod
    def get_by_id_and_tenant(self, lead_id: UUID, tenant_id: UUID) -> Optional[Lead]:
        """Reading across organizations must be impossible, not merely forbidden."""

    @abstractmethod
    def list_by_agent(
        self, tenant_id: UUID, agent_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[Lead]:
        ...

    @abstractmethod
    def count_by_agent(self, tenant_id: UUID, agent_id: UUID) -> int:
        ...
```

- [ ] **Step 5: Implementar en el repositorio de leads**

En `backend/src/infrastructure/adapters/output/persistence/raw_sql_lead_repository.py`:

Añadir las cuatro columnas nuevas al `INSERT`/`ON CONFLICT DO UPDATE` de `save` (`assigned_at`, `discard_reason`, `updated_at`, `score_breakdown`). El desglose viaja como `Jsonb`, con los UUID en texto porque JSON no tiene tipo UUID propio:

```python
        breakdown = Jsonb(
            [
                {"rule_id": str(a.rule_id), "name": a.name, "score_delta": a.score_delta}
                for a in lead.score_breakdown
            ]
        )
```

y `_row_to_lead` lo reconstruye:

```python
            score_breakdown=[
                AppliedRule(
                    rule_id=UUID(entry["rule_id"]),
                    name=entry["name"],
                    score_delta=entry["score_delta"],
                )
                for entry in (row["score_breakdown"] or [])
            ],
```

Además, añadir los métodos:

```python
    def get_by_id_and_tenant(self, lead_id: UUID, tenant_id: UUID) -> Optional[Lead]:
        row = self.connection.execute(
            "SELECT * FROM leads WHERE id = %s AND tenant_id = %s", (lead_id, tenant_id)
        ).fetchone()
        return self._row_to_lead(row) if row else None

    def list_by_agent(
        self, tenant_id: UUID, agent_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[Lead]:
        rows = self.connection.execute(
            """
            SELECT * FROM leads
            WHERE tenant_id = %s AND assigned_agent_id = %s
            ORDER BY created_at DESC, id LIMIT %s OFFSET %s
            """,
            (tenant_id, agent_id, limit, offset),
        ).fetchall()
        return [self._row_to_lead(row) for row in rows]

    def count_by_agent(self, tenant_id: UUID, agent_id: UUID) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM leads WHERE tenant_id = %s AND assigned_agent_id = %s",
            (tenant_id, agent_id),
        ).fetchone()
        return int(row["count"])
```

Y corregir la paginación no determinista de `list_by_tenant` añadiendo el orden que le falta:

```python
            "SELECT * FROM leads WHERE tenant_id = %s ORDER BY created_at DESC, id LIMIT %s OFFSET %s",
```

- [ ] **Step 6: Actualizar el repositorio de reglas de puntuación**

En `raw_sql_rule_repository.py`, `get_scoring_rules_by_tenant` y `save_scoring_rule` deben incluir `tenant_id`, `priority` e `is_active`. El `value` ya viaja como `Jsonb` desde F0.6, así que conserva su tipo sin tocar nada más.

- [ ] **Step 7: Actualizar los dobles de test**

`tests/unit/mocks/in_memory_lead_repo.py` implementa los tres métodos nuevos; `in_memory_rule_repo.py` acompaña la firma de `ScoringRule`. Sin ellos el guardián de puertos falla.

- [ ] **Step 8: Ejecutar la suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/migrations/004_lead_lifecycle_and_scoring.sql backend/src backend/tests
git commit -m "feat(persistence): store the lifecycle trace and the score breakdown"
```

---

## Task 6: El valor de una regla conserva su tipo

**Files:**
- Modify: `backend/src/application/dtos/commands.py:48-55`
- Modify: `backend/src/infrastructure/adapters/input/api/schemas.py`
- Modify: `backend/src/application/use_cases/rule_use_cases.py`
- Modify: `backend/src/infrastructure/adapters/input/api/rule_router.py`
- Test: `backend/tests/e2e/test_scoring_rule_value_types.py` (crear)

**Interfaces:**
- Consumes: `ScoringRule.create(tenant_id=..., priority=..., is_active=...)` (Task 3).
- Produces: `CreateScoringRuleCommand.value: Any`, más `priority: int = 0` e `is_active: bool = True`.

`CreateScoringRuleCommand.value: str` fuerza a cadena en el borde, y por eso el operador `IN` **no se cumple nunca**: el motor exige una lista y siempre recibe texto. Las comparaciones numéricas funcionan hoy por casualidad, a través de coerciones.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/e2e/test_scoring_rule_value_types.py`:

```python
def test_a_list_valued_rule_survives_the_round_trip(client, manager_token):
    """The IN operator never fired because value was coerced to str."""
    created = client.post(
        "/api/v1/rules/scoring",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={
            "name": "Sectores objetivo", "field": "industry", "operator": "IN",
            "value": ["tech", "finance"], "score_delta": 40,
        },
    )
    assert created.status_code == 201

    listed = client.get(
        "/api/v1/rules/scoring", headers={"Authorization": f"Bearer {manager_token}"}
    )
    rule = next(r for r in listed.json() if r["name"] == "Sectores objetivo")
    assert rule["value"] == ["tech", "finance"]


def test_a_numeric_rule_keeps_its_number(client, manager_token):
    created = client.post(
        "/api/v1/rules/scoring",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={
            "name": "Presupuesto alto", "field": "budget", "operator": "GREATER_THAN",
            "value": 5000, "score_delta": 30,
        },
    )
    assert created.status_code == 201
    assert created.json()["value"] == 5000


def test_a_field_outside_the_allow_list_is_refused(client, manager_token):
    refused = client.post(
        "/api/v1/rules/scoring",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={
            "name": "Fuga", "field": "tenant_id", "operator": "EQUALS",
            "value": "x", "score_delta": 10,
        },
    )
    assert refused.status_code == 400
    assert refused.json()["error_code"] == "FIELD_NOT_SCORABLE"
```

**No existen fixtures `client` ni `manager_token`.** Copia la cabecera y los helpers locales de `tests/e2e/test_plane_separation_e2e.py` —que arranca un admin, crea una organización y hace login con `data={"username": ..., "password": ...}`— y envuelve cada caso en `with TestClient(app) as client:`, recibiendo `test_db` como parámetro. Los `client, manager_token` de arriba son abreviatura de eso.

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/e2e/test_scoring_rule_value_types.py -q`
Expected: FAIL — el valor vuelve como `"['tech', 'finance']"`, una cadena.

- [ ] **Step 3: Cambiar el DTO**

En `backend/src/application/dtos/commands.py`, en `CreateScoringRuleCommand`:

```python
    # Any, not str: coercing here is what kept the IN operator from ever
    # matching, since the engine needs the list the manager actually sent.
    value: Any
    score_delta: int
    priority: int = 0
    is_active: bool = True
```

Asegurar que `Any` está importado desde `typing`.

- [ ] **Step 4: Cambiar el esquema del adaptador**

En `schemas.py`, el campo `value` de la petición y de la respuesta de reglas de puntuación pasa a `Any`, y se añaden `priority: int = 0` e `is_active: bool = True`.

- [ ] **Step 5: Propagar en el caso de uso y el router**

`rule_use_cases.py` pasa `tenant_id`, `priority` e `is_active` a `ScoringRule.create`. El router traduce `DomainException` al formato de error ya establecido, de modo que un campo no puntuable devuelva 400 con `FIELD_NOT_SCORABLE`.

- [ ] **Step 6: Ejecutar la suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src backend/tests
git commit -m "fix(rules): keep a scoring rule's value in the type the manager sent"
```

---

## Task 7: Casos de uso del ciclo de vida

**Files:**
- Create: `backend/src/application/ports/input/lead_lifecycle_use_case_ports.py`
- Create: `backend/src/application/use_cases/lead_lifecycle_use_cases.py`
- Modify: `backend/src/application/dtos/{commands,queries}.py`
- Modify: `backend/src/application/use_cases/ingest_lead_use_case.py`
- Modify: `backend/src/infrastructure/di/container.py`
- Test: `backend/tests/unit/application/test_lead_lifecycle_use_cases.py` (crear)

**Interfaces:**
- Consumes: la máquina de estados (Task 2), `ScoreBreakdown` (Task 4), `list_by_agent`/`count_by_agent`/`get_by_id_and_tenant` (Task 5).
- Produces: `AssignLeadUseCase`, `DiscardLeadUseCase`, `GetMyLeadsUseCase`, `GetLeadUseCase`. DTOs `AssignLeadCommand(tenant_id, lead_id, agent_id)`, `DiscardLeadCommand(tenant_id, lead_id, reason)`, `GetMyLeadsQuery(tenant_id, agent_id, limit, offset)`, `GetLeadQuery(tenant_id, lead_id)`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `backend/tests/unit/application/test_lead_lifecycle_use_cases.py` con los dobles en memoria ya existentes. Los dos primeros casos, completos, fijan el estilo del fichero:

```python
import uuid

import pytest

from application.dtos.commands import AssignLeadCommand, DiscardLeadCommand
from application.dtos.queries import GetMyLeadsQuery
from application.use_cases.lead_lifecycle_use_cases import (
    AssignLeadUseCase,
    DiscardLeadUseCase,
    GetMyLeadsUseCase,
)
from domain.entities.agent import Agent
from domain.entities.lead import Lead
from domain.exceptions import DomainException
from domain.value_objects.enums import AgentRole, LeadStatus
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_TENANT = uuid.uuid4()
_OTHER = uuid.uuid4()


def _lead(tenant_id: uuid.UUID = _TENANT, status: LeadStatus = LeadStatus.UNASSIGNED) -> Lead:
    return Lead.create(
        tenant_id=tenant_id, first_name="Ana", last_name="Diaz", email="ana@x.test",
        company="Acme", budget=1000, industry="tech", status=status,
    )


def _agent(tenant_id: uuid.UUID = _TENANT) -> Agent:
    return Agent.create(
        "Sales One", f"{uuid.uuid4()}@x.test", role=AgentRole.AGENT, tenant_id=tenant_id
    )


def test_assigning_moves_the_lead_to_the_agent():
    uow = InMemoryUnitOfWork()
    lead, agent = _lead(), _agent()
    uow.leads.save(lead)
    uow.agents.save(agent)

    result = AssignLeadUseCase(uow).execute(
        AssignLeadCommand(tenant_id=_TENANT, lead_id=lead.id.value, agent_id=agent.id.value)
    )

    assert result.status == LeadStatus.ASSIGNED.value
    stored = uow.leads.get_by_id(lead.id.value)
    assert stored.assigned_agent_id.value == agent.id.value
    assert stored.assigned_at is not None


def test_assigning_a_lead_of_another_organization_is_not_found():
    """Not Forbidden: a 403 would confirm the lead exists elsewhere."""
    uow = InMemoryUnitOfWork()
    lead, agent = _lead(tenant_id=_OTHER), _agent()
    uow.leads.save(lead)
    uow.agents.save(agent)

    with pytest.raises(DomainException) as exc:
        AssignLeadUseCase(uow).execute(
            AssignLeadCommand(tenant_id=_TENANT, lead_id=lead.id.value, agent_id=agent.id.value)
        )
    assert exc.value.error_code == "LEAD_NOT_FOUND"
```

**El código de error importa.** No existe una `NotFoundException` en este proyecto: el patrón establecido —el que usan los casos de uso de grupos— es `DomainException(mensaje, error_code="...")`, y el router lo traduce al código HTTP. Usa `LEAD_NOT_FOUND` y `AGENT_NOT_FOUND`, que el adaptador mapea a **404**.

Y a continuación, en el mismo estilo y con aserciones completas:

- `test_assigning_an_agent_of_another_organization_is_refused` — `DomainException` con `error_code == "CROSS_TENANT_ASSIGNMENT"`.
- `test_reassigning_an_already_assigned_lead_lands_on_the_new_agent` — un lead ya `ASSIGNED` que se asigna otra vez termina en el asesor nuevo, no rechazado: el caso de uso elige `reassign_to`.
- `test_discarding_records_the_reason` — `DISCARDED` y `discard_reason` conservado.
- `test_discarding_without_a_reason_is_refused` — `DomainException` con `error_code == "DISCARD_WITHOUT_REASON"`.
- `test_my_leads_only_returns_the_requesting_agent_leads` — dos asesores con un lead cada uno; `GetMyLeadsQuery` devuelve exactamente uno.

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/application/test_lead_lifecycle_use_cases.py -q`
Expected: FAIL con `ModuleNotFoundError: application.use_cases.lead_lifecycle_use_cases`.

- [ ] **Step 3: Escribir los puertos de entrada**

`lead_lifecycle_use_case_ports.py` declara los cuatro puertos como `abc.ABC` con un único `execute`, siguiendo exactamente el patrón de `sales_group_use_case_ports.py`.

- [ ] **Step 4: Escribir los casos de uso**

`lead_lifecycle_use_cases.py`. Reglas que deben cumplirse:

- El lead se lee **siempre** con `get_by_id_and_tenant`, nunca con `get_by_id`: un lead de otra organización debe dar `NotFoundException`, no `ForbiddenException`.
- El asesor destino se lee con `agents.get_by_id_and_tenant`, por el mismo motivo.
- `AssignLeadUseCase` elige `reassign_to` si el lead ya está `ASSIGNED` y `assign_to` en caso contrario. Así el gestor tiene una sola operación y la entidad conserva sus invariantes.
- Todo ocurre dentro de `with self.uow:`.

- [ ] **Step 5: Cerrar el hueco de `UNASSIGNED` en la ingesta**

En `ingest_lead_use_case.py`: `self.scoring_engine.evaluate(...)` ahora devuelve un `ScoreBreakdown`. Guarda el desglose en el lead y, cuando el motor no encuentre asesor, deja el lead en `UNASSIGNED` en lugar de `QUALIFIED`:

```python
                assigned_agent = self.engine.select_agent(
                    lead, assignment_rules, available_agents, groups_by_id, loads
                )
                if assigned_agent is None:
                    # QUALIFIED and UNASSIGNED used to be indistinguishable, so
                    # a lead nobody could take looked like one not yet routed.
                    lead.leave_unassigned()
```

y `applied_rules_count` pasa a `len(breakdown.applied)`, que es lo que su nombre dice.

- [ ] **Step 6: Registrar en el composition root**

`container.py` expone los cuatro casos de uso nuevos, siguiendo el patrón de los de grupos.

- [ ] **Step 7: Ejecutar la suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/src backend/tests
git commit -m "feat(application): add manual assignment, discard and the agent's own lead list"
```

---

## Task 8: Adaptadores HTTP y cierre del circuito

**Files:**
- Modify: `backend/src/infrastructure/adapters/input/api/lead_router.py`
- Modify: `backend/src/infrastructure/adapters/input/api/schemas.py`
- Modify: `backend/src/infrastructure/adapters/input/api/dependencies.py`
- Modify: `docs/api/endpoints.md`
- Test: `backend/tests/e2e/test_lead_lifecycle_api.py` (crear)

**Interfaces:**
- Consumes: los cuatro casos de uso de la Task 7.
- Produces: `GET /api/v1/leads/mine`, `GET /api/v1/leads/{lead_id}`, `POST /api/v1/leads/{lead_id}/assign`, `POST /api/v1/leads/{lead_id}/discard`.

**Cuidado con el orden de las rutas.** `GET /leads/mine` debe declararse **antes** que `GET /leads/{lead_id}`, o FastAPI resolverá `mine` como un `lead_id` y devolverá un error de validación de UUID.

**Autorización, endpoint por endpoint:**

| Ruta | Dependencia | Motivo |
|---|---|---|
| `GET /leads` | `require_organization_manager` | Ya está así desde F0.5 |
| `GET /leads/mine` | `get_request_context` + rol `AGENT` o `MANAGER` | Es la única vía del asesor a sus leads |
| `GET /leads/{id}` | `get_request_context`; el asesor sólo alcanza los suyos | Un asesor no lee el detalle de un lead ajeno |
| `POST /leads/{id}/assign` | `require_organization_manager` | Repartir es competencia del gestor |
| `POST /leads/{id}/discard` | `require_organization_manager` | Descartar también |

- [ ] **Step 1: Escribir los tests e2e que fallan**

Crear `backend/tests/e2e/test_lead_lifecycle_api.py`.

**No hay fixtures compartidas de cliente ni de token:** `tests/conftest.py` sólo expone `test_db`, `clean_tables` y `dsn_of_test_db`. Cada fichero e2e monta lo suyo con helpers locales. Copia la cabecera y los helpers de `tests/e2e/test_plane_separation_e2e.py`, que ya arranca un admin, crea una organización y hace login con `data={"username": ..., "password": ...}` (el login es un formulario OAuth2, **no** JSON).

Los dos primeros casos, completos, fijan el estilo:

```python
import os
import uuid

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5433/leads_test"
)

from fastapi.testclient import TestClient

from infrastructure.main import app


def test_an_agent_sees_only_their_own_leads_on_mine(test_db):
    """The agent's only door to their leads: GET /leads is manager-only."""
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        manager_token, tenant_id = _create_org(client, admin_token)
        agent_token, agent_id = _create_agent(client, manager_token)
        mine_id = _ingest_and_assign(client, manager_token, tenant_id, agent_id)
        _ingest_and_assign(client, manager_token, tenant_id, _create_agent(client, manager_token)[1])

        mine = client.get("/api/v1/leads/mine", headers={"Authorization": f"Bearer {agent_token}"})

        assert mine.status_code == 200, mine.text
        assert [item["id"] for item in mine.json()["items"]] == [mine_id]


def test_the_platform_admin_is_refused_on_mine(test_db):
    """The admin has no tenant, so it must reach no operational data."""
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)

        refused = client.get(
            "/api/v1/leads/mine", headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert refused.status_code == 403, refused.text
```

Y a continuación, en el mismo estilo y con aserciones completas:

- `test_a_manager_can_also_call_mine_and_gets_their_own` — 200, y sólo los suyos.
- `test_an_agent_cannot_read_a_colleagues_lead_detail` — **404**, no 403.
- `test_a_manager_assigns_a_lead_by_hand` — un lead `UNASSIGNED` pasa a `ASSIGNED` con `assigned_at` no nulo.
- `test_assigning_an_agent_of_another_organization_fails` — 400 con `CROSS_TENANT_ASSIGNMENT`, o 404 si el asesor se resuelve antes por organización; asegura cuál y afírmalo.
- `test_an_agent_cannot_assign` — 403.
- `test_a_manager_discards_with_a_reason` — `DISCARDED` y motivo conservado.
- `test_discarding_without_a_reason_is_refused` — 400 con `DISCARD_WITHOUT_REASON`.
- `test_the_lead_detail_carries_the_applied_rule_breakdown` — el detalle trae `score_breakdown` con `rule_id`, `name` y `score_delta` de cada regla que se cumplió.

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/e2e/test_lead_lifecycle_api.py -q`
Expected: FAIL con 404 en `/leads/mine`.

- [ ] **Step 3: Escribir la dependencia del asesor**

En `dependencies.py`:

```python
def require_organization_member(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    """Any member of an organization: manager or sales agent.

    The platform admin has no tenant, so it is excluded by construction —
    which is the point: it must not reach operational data."""
    AuthorizationPolicy.ensure_can_access_tenant(context)
    return context
```

- [ ] **Step 4: Escribir los endpoints**

En `lead_router.py`, declarando `/mine` antes que `/{lead_id}`. La respuesta de detalle incluye `score_breakdown` como lista de objetos `{rule_id, name, score_delta}`.

- [ ] **Step 5: Actualizar la documentación**

En `docs/api/endpoints.md`, documentar los cuatro endpoints nuevos con petición, respuesta y códigos de error, en el estilo del resto del fichero, y retirar la nota de la sección 4 que decía que `/leads/mine` llegaría en F2.

- [ ] **Step 6: Validación del circuito completo**

```bash
uv run pytest -q                                          # sin banderas, en verde
docker compose --profile test run --rm --build backend-test
docker compose down -v && docker compose up -d --build
```

Con `curl` contra el 8001, como gestor y como asesor:

1. Las **cuatro migraciones** aplican en orden desde volumen vacío.
2. Una regla con operador `IN` y lista de valores **puntúa de verdad** un lead.
3. El detalle de un lead devuelve el **desglose** de reglas aplicadas.
4. Un lead calificado sin candidato queda **`UNASSIGNED`**, no `QUALIFIED`.
5. El gestor lo asigna a mano → `ASSIGNED` con `assigned_at`.
6. Reasignar a otro asesor cambia el asesor y conserva el estado.
7. El asesor ve **sólo sus leads** en `/leads/mine` y recibe 404 en el detalle de uno ajeno.
8. El descarte sin motivo devuelve 400; con motivo deja el lead `DISCARDED`.
9. El ADMIN recibe 403 en `/leads/mine`.

- [ ] **Step 7: Commit**

```bash
git add backend/src backend/tests docs/api/endpoints.md
git commit -m "feat(api): expose the agent's lead list, manual assignment and discard"
```

---

## Criterio de aceptación de F2a

- [ ] Guardián de arquitectura en 4/4.
- [ ] `pytest -m unit` en verde sin base de datos ni variables de entorno.
- [ ] La suite completa en verde **sin banderas**, dentro y fuera de Docker.
- [ ] El sistema arranca desde volumen vacío y aplica las **cuatro** migraciones.
- [ ] Una regla con operador `IN` se cumple. Hoy no se cumple nunca.
- [ ] `NOT_EQUALS` y `EQUALS` **no pueden ser ambos verdad** para el mismo par campo/valor.
- [ ] Un campo ausente da falso en los operadores positivos y **verdadero** en `NOT_EQUALS`.
- [ ] Una regla sobre un campo no puntuable (`tenant_id`) se rechaza con `FIELD_NOT_SCORABLE`.
- [ ] `applied_rules_count` cuenta las reglas **aplicadas**, no las consultadas.
- [ ] El detalle de un lead explica su puntuación con el desglose.
- [ ] Un lead calificado sin candidato queda `UNASSIGNED`.
- [ ] `assign_to` rechaza un lead ya asignado; la reasignación es explícita.
- [ ] Un lead no se asigna jamás a un asesor de otra organización, ni siquiera a mano.
- [ ] El asesor ve sus leads en `/leads/mine` y **sólo** los suyos.
- [ ] `rg "assign_to_agent" src/` no devuelve nada.

## Notas para quien ejecute el plan

**Orden.** 1 antes que 2. 3 antes que 4. 5 después de 1-4. 7 antes que 8.

**La Task 3 deja tests en rojo a propósito:** `ScoringRule.create` pasa a exigir `tenant_id`, lo que rompe el repositorio de reglas y sus dobles. Se limpia en las tareas 5 y 6. No lo parchees desde el dominio.

**Diagnóstico durante el trayecto.** Si un `ImportError` aborta la recolección, usa
`uv run pytest -q --continue-on-collection-errors` para recuperar visibilidad. Al cerrar el bloque C
la suite debe correr **sin** esa bandera.

**Criterio de parada.** Si un paso «verificar que falla» produce un fallo distinto del descrito, detente y repórtalo.

**Lo que esta fase NO toca:** `LeadSource`, `IntakeRecord`, la bandeja de entrada, el cierre de la ingesta sin autenticar, las notificaciones y el frontend. Todo eso es F2b o posterior. Si te tienta arreglar algo de ahí de camino, anótalo en el informe en vez de hacerlo.

**Ruido conocido, no lo arregles:** cinco tests e2e siguen enviando `"team": "HQ"` al crear asesores (`rg '"team"' tests/`). Pydantic descarta el campo sobrante, así que no rompe nada. Retirarlo no aporta a esta fase.

## Protocolo de ejecución

Este plan es la fuente de requisitos. **No hace falta explorar el repositorio para entenderlo:** las
firmas, los patrones a copiar y los ficheros exactos están arriba. Si algo del plan no cuadra con el
código real, eso **es** un hallazgo: aplícalo con criterio y repórtalo, no abras una investigación.

**Validación: fíate del harness.** La suite tiene 256 tests, guardián de arquitectura, y el compose
levanta y baja limpio. Ejecuta lo que cada tarea pide y sigue. No hace falta releer ficheros ya
verificados ni reconfirmar lo que la suite en verde ya demuestra.

**Los hallazgos van en la respuesta, no sólo en el informe.** Si encuentras un defecto y lo corriges
al paso para completar tu tarea, dilo en el texto que devuelves: qué era, dónde, y qué hiciste. Un
arreglo que sólo aparece en un fichero de informe obliga a revisarlo todo otra vez, que es
exactamente lo que este protocolo evita.
