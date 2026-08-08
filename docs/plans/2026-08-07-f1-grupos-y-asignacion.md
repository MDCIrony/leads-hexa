# F1 — Grupos y asignación: Plan de Implementación

> # ✅ FASE CERRADA — NO EJECUTAR
>
> Este plan **ya está implementado y verificado** (11 commits, 76 ficheros, +3290/−638). Se conserva
> como registro de lo que se hizo y por qué, no como trabajo pendiente. Si eres un agente al que han
> encargado implementar algo, **este no es tu plan**: busca en [docs/plans/](.) el que no lleva esta
> marca.
>
> **Ojo si vienes buscando el modelo de datos:** la migración `003` que este plan describe ya está
> aplicada. La numeración libre para la fase siguiente es la **`004`**.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que un gestor pueda crear grupos de asesores con su política de reparto, definir reglas de asignación por banda de puntuación, y que un lead ingestado llegue al asesor correcto según cada estrategia — sin que ningún lead cruce jamás a otra organización.

**Architecture:** `SalesGroup` sustituye al campo `team: str` suelto por un agregado con identidad, política y clave foránea. `AssignmentRule` reemplaza a `RoutingRule` con banda de puntuación, prioridad explícita, modo de combinación de candidatos y cursor rotatorio persistido. El motor pasa de "primera regla que supera el umbral" a una cascada que prueba reglas hasta encontrar candidatos. La carga de un asesor deja de ser un contador mantenido a mano y pasa a derivarse de los leads que tiene asignados.

**Tech Stack:** Python 3.12+, FastAPI, psycopg 3 (raw SQL, sin ORM), pytest, uv, PostgreSQL 16, Docker Compose.

**Estado de partida:** F0.6 cerrada. 188 tests en verde, guardián de arquitectura 4/4, esquema con tipos nativos, dos planos separados.

## Global Constraints

- Todo el código, nombres, docstrings y comentarios **en inglés**. La documentación en español.
- **Prohibido cualquier ORM.** SQL parametrizado sobre `psycopg` 3, marcadores `%s`.
- `domain/` no importa nada fuera de la biblioteca estándar.
- `application/` importa sólo de `domain/` y de la biblioteca estándar. **Nunca** de `infrastructure/`.
- Pydantic vive **sólo** en los adaptadores.
- Los puertos son `abc.ABC` con `@abc.abstractmethod`. Los DTOs de aplicación son `@dataclass(frozen=True)`.
- **El guardián `tests/architecture/` debe permanecer en 4/4 en todo momento.**
- `pytest -m unit` debe pasar sin base de datos, sin red y sin variables de entorno.
- Los comentarios explican el **porqué**, nunca el qué.
- Mensajes de commit en inglés, `type(scope): description`. **Sin** `Co-authored-by`.
- No `git push`, no ramas nuevas. Rama de trabajo: `repo-status-mvp`.
- Anota los tipos en las funciones auxiliares de test. Un parámetro que pueda recibir `None` se declara `Optional[...]`.
- **Puertos del host:** PostgreSQL en **5433**, API en **8001**. Dentro de la red de compose siguen siendo 5432 y 8000.
- **No hay datos que preservar.** Las migraciones se aplican sobre base vacía; ningún paso escribe código de backfill.

```bash
export DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export TEST_DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export JWT_SECRET=test-secret-do-not-use-in-production
```

## Agrupación sugerida en despachos

Ocho tareas, tres despachos. Las cuatro primeras son dominio puro y no tocan la base de datos.

| Bloque | Tareas | Validación |
|---|---|---|
| A | 1 + 2 + 3 + 4 | pytest (sin base de datos salvo la Task 1) |
| B | 5 + 6 | pytest + base de datos |
| C | 7 + 8 | **Docker + curl + base de datos**, circuito completo |

## Mapa de ficheros

**Se crean:** `domain/entities/sales_group.py` · `domain/value_objects/group_id.py` · `application/ports/output/sales_group_repository_port.py` · `application/ports/input/sales_group_use_case_ports.py` · `application/use_cases/sales_group_use_cases.py` · `infrastructure/adapters/output/persistence/raw_sql_sales_group_repository.py` · `infrastructure/adapters/input/api/sales_group_router.py` · `migrations/003_groups_and_assignment.sql` · sus tests.

**Se modifican:** `domain/entities/{agent,rule}.py` · `domain/services/router_engine.py` · `domain/value_objects/enums.py` · `application/ports/output/{agent,rule}_repository_port.py` · `application/use_cases/{agent,rule,ingest_lead}_use_cases.py` · `application/dtos/{commands,queries}.py` · `infrastructure/adapters/output/persistence/raw_sql_{agent,rule,lead}_repository.py` · `infrastructure/adapters/input/api/{agent_router,rule_router,schemas,dependencies}.py` · `infrastructure/main.py` · `infrastructure/di/container.py` · `docs/api/endpoints.md`.

---

## Task 1: Cerrar la fuga cross-tenant de la asignación

**Files:**
- Modify: `backend/src/application/ports/output/agent_repository_port.py`
- Modify: `backend/src/infrastructure/adapters/output/persistence/raw_sql_agent_repository.py`
- Modify: `backend/tests/unit/mocks/in_memory_agent_repo.py`
- Modify: `backend/src/application/use_cases/ingest_lead_use_case.py`
- Test: `backend/tests/integration/test_assignment_tenant_isolation.py` (crear)

**Interfaces:**
- Produces: `AgentRepositoryPort.get_available_agents(tenant_id, team=None)`. El parámetro `tenant_id` es **obligatorio y primero**.

Esta tarea va la primera y es independiente del resto: cierra una fuga viva. Hoy `get_available_agents()` no recibe organización, y el motor filtra los candidatos únicamente por `agent.team == rule.target_team`. Dos organizaciones con un equipo llamado "Sales" —lo habitual— comparten candidatos: un lead de la empresa A puede acabar asignado a un asesor de la B.

- [ ] **Step 1: Escribir el test que demuestra la fuga**

Crear `backend/tests/integration/test_assignment_tenant_isolation.py`:

```python
import uuid
from typing import Optional

import pytest

from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import (
    RawSqlAgentRepository,
)

_TENANT_A = uuid.uuid4()
_TENANT_B = uuid.uuid4()


def _agent(name: str, email: str, tenant_id: uuid.UUID, team: str = "Sales") -> Agent:
    return Agent.create(
        name=name,
        email=email,
        team=team,
        role=AgentRole.AGENT,
        tenant_id=tenant_id,
    )


def test_available_agents_never_cross_organizations(db_connection):
    """A lead of one organization must never reach another's sales agents.

    Both organizations name their team "Sales", which is exactly the collision
    that made the leak invisible: the engine filtered by team name alone."""
    repo = RawSqlAgentRepository(db_connection)
    repo.save(_agent("Ana", "ana@a.test", _TENANT_A))
    repo.save(_agent("Bruno", "bruno@b.test", _TENANT_B))

    found = repo.get_available_agents(_TENANT_A)

    assert [a.email for a in found] == ["ana@a.test"]


def test_available_agents_still_filter_by_team(db_connection):
    repo = RawSqlAgentRepository(db_connection)
    repo.save(_agent("Ana", "ana@a.test", _TENANT_A, team="Sales"))
    repo.save(_agent("Carla", "carla@a.test", _TENANT_A, team="Support"))

    assert len(repo.get_available_agents(_TENANT_A, team="Sales")) == 1
    assert len(repo.get_available_agents(_TENANT_A)) == 2
```

Usa la fixture `db_connection` que ya emplean los demás tests de `tests/integration/`. Si su nombre difiere, compruébalo en `backend/tests/conftest.py` y usa el que exista — no crees una fixture nueva.

- [ ] **Step 2: Ejecutar y verificar que falla**

```bash
cd backend
uv run pytest tests/integration/test_assignment_tenant_isolation.py -v
```

Expected: FAIL con `TypeError: get_available_agents() takes 1 to 2 positional arguments but 3 were given`, o el test de aislamiento devolviendo los dos asesores.

- [ ] **Step 3: Cambiar el puerto**

En `backend/src/application/ports/output/agent_repository_port.py`, sustituir la declaración de `get_available_agents`:

```python
    @abstractmethod
    def get_available_agents(self, tenant_id: UUID, team: Optional[str] = None) -> List[Agent]:
        """Return the active agents of this organization eligible for assignment.

        tenant_id is required and comes first: an optional organization filter
        is one forgotten argument away from routing a lead into someone else's
        company."""
```

- [ ] **Step 4: Cambiar la implementación SQL**

En `backend/src/infrastructure/adapters/output/persistence/raw_sql_agent_repository.py`:

```python
    def get_available_agents(self, tenant_id: UUID, team: Optional[str] = None) -> List[Agent]:
        sql = "SELECT * FROM agents WHERE tenant_id = %s AND is_active = TRUE"
        params: list = [tenant_id]
        if team:
            sql += " AND team = %s"
            params.append(team)
        sql += " ORDER BY name, id"
        rows = self.connection.execute(sql, tuple(params)).fetchall()
        return [self._row_to_agent(r) for r in rows]
```

- [ ] **Step 5: Cambiar el mock**

En `backend/tests/unit/mocks/in_memory_agent_repo.py`:

```python
    def get_available_agents(self, tenant_id: UUID, team: Optional[str] = None) -> List[Agent]:
        agents = [
            a
            for a in self.agents.values()
            if a.is_active and a.tenant_id is not None and a.tenant_id.value == tenant_id
        ]
        if team:
            agents = [a for a in agents if a.team == team]
        return agents
```

- [ ] **Step 6: Pasar la organización desde la ingesta**

En `backend/src/application/use_cases/ingest_lead_use_case.py` hay **dos** llamadas a `get_available_agents()`, en dos ramas duplicadas del mismo algoritmo (una con unidad de trabajo y otra sin ella). Cambiar ambas a:

```python
available_agents = self.uow.agents.get_available_agents(lead.tenant_id.value)
```

y, en la rama sin unidad de trabajo:

```python
available_agents = agent_repo.get_available_agents(lead.tenant_id.value)
```

La duplicación de ese algoritmo es deuda conocida; la Task 8 la elimina. Aquí sólo se corrige, sin refactorizar: mezclar las dos cosas haría imposible saber cuál de las dos rompió algo.

- [ ] **Step 7: Ejecutar la suite completa**

```bash
uv run pytest -q
```

Expected: **190 passed** (188 + los 2 nuevos). Si algún test unitario llamaba a `get_available_agents()` sin argumentos, actualízalo pasándole la organización del asesor que ese test crea.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "fix(assignment): scope the candidate pool by organization

Candidates were filtered by team name alone, so two organizations naming
their team the same shared a pool and a lead could be routed into another
company's sales agent."
```

---

## Task 2: `AgentMatchMode` y la entidad `SalesGroup`

**Files:**
- Create: `backend/src/domain/value_objects/group_id.py`
- Create: `backend/src/domain/entities/sales_group.py`
- Modify: `backend/src/domain/value_objects/enums.py`
- Test: `backend/tests/unit/domain/test_sales_group.py` (crear)

**Interfaces:**
- Produces: `GroupId`, `AgentMatchMode`, y `SalesGroup` con `create(...)`, `activate()`, `deactivate()`, `rename(name)`, `has_capacity_for(active_leads)`.

- [ ] **Step 1: Añadir el enumerado**

En `backend/src/domain/value_objects/enums.py`, al final:

```python
class AgentMatchMode(str, Enum):
    """How a rule combines its target group with its named agents.

    ANY is the default because the alternative silently drops a named agent
    that happens to belong to a different group — the caller asked for that
    person explicitly, so excluding them is never what they meant."""

    ANY = "ANY"
    ONLY = "ONLY"
```

- [ ] **Step 2: Añadir el objeto de valor del identificador**

Crear `backend/src/domain/value_objects/group_id.py`, siguiendo el patrón exacto de `backend/src/domain/value_objects/tenant_id.py`. Léelo primero y replica su estructura: mismo tratamiento de `None`, de `str`, de `UUID`, mismo `__str__` y mismo `__eq__`. No inventes una variante.

- [ ] **Step 3: Escribir los tests de la entidad**

Crear `backend/tests/unit/domain/test_sales_group.py`:

```python
import uuid

import pytest

from domain.entities.sales_group import SalesGroup
from domain.exceptions import DomainException
from domain.value_objects.enums import AssignmentStrategy

_TENANT = uuid.uuid4()


class TestSalesGroupCreation:
    def test_a_group_belongs_to_one_organization(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas Norte")
        assert group.tenant_id.value == _TENANT
        assert group.name == "Ventas Norte"

    def test_the_default_strategy_is_lowest_load(self):
        """Spreading work evenly is the sane default; rotation is a choice."""
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas")
        assert group.default_strategy == AssignmentStrategy.LOWEST_LOAD

    def test_a_group_is_active_and_uncapped_by_default(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas")
        assert group.is_active is True
        assert group.capacity_per_agent is None

    def test_an_empty_name_is_rejected(self):
        with pytest.raises(DomainException) as exc:
            SalesGroup.create(tenant_id=_TENANT, name="   ")
        assert exc.value.error_code == "INVALID_GROUP_NAME"

    @pytest.mark.parametrize("capacity", [0, -1])
    def test_a_non_positive_capacity_is_rejected(self, capacity: int):
        """A capacity of zero would make the group unusable rather than uncapped;
        the way to say uncapped is None."""
        with pytest.raises(DomainException) as exc:
            SalesGroup.create(tenant_id=_TENANT, name="Ventas", capacity_per_agent=capacity)
        assert exc.value.error_code == "INVALID_GROUP_CAPACITY"

    def test_the_strategy_can_be_given_as_a_string(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas", default_strategy="ROUND_ROBIN")
        assert group.default_strategy == AssignmentStrategy.ROUND_ROBIN


class TestSalesGroupBehaviour:
    def test_deactivating_and_activating(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas")
        group.deactivate()
        assert group.is_active is False
        group.activate()
        assert group.is_active is True

    def test_renaming_rejects_an_empty_name(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas")
        with pytest.raises(DomainException):
            group.rename("")

    def test_an_uncapped_group_always_has_capacity(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas")
        assert group.has_capacity_for(9999) is True

    def test_a_capped_group_excludes_an_agent_at_the_limit(self):
        """At the limit, not past it: capacity 5 means five is already full."""
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas", capacity_per_agent=5)
        assert group.has_capacity_for(4) is True
        assert group.has_capacity_for(5) is False
        assert group.has_capacity_for(6) is False
```

- [ ] **Step 4: Ejecutar y verificar que falla**

```bash
cd backend
uv run pytest tests/unit/domain/test_sales_group.py -v
```

Expected: FAIL con `ModuleNotFoundError: No module named 'domain.entities.sales_group'`.

- [ ] **Step 5: Escribir la entidad**

Crear `backend/src/domain/entities/sales_group.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.enums import AssignmentStrategy
from domain.value_objects.group_id import GroupId
from domain.value_objects.tenant_id import TenantId


@dataclass
class SalesGroup:
    """A set of sales agents that share an assignment policy.

    It replaces the free-form `team` string. A string cannot be renamed
    without orphaning every rule that named it, cannot carry a capacity, and
    turns a typo into a rule that silently matches nobody."""

    id: GroupId
    tenant_id: TenantId
    name: str
    description: Optional[str] = None
    default_strategy: AssignmentStrategy = AssignmentStrategy.LOWEST_LOAD
    capacity_per_agent: Optional[int] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID, TenantId],
        name: str,
        description: Optional[str] = None,
        default_strategy: Union[str, AssignmentStrategy] = AssignmentStrategy.LOWEST_LOAD,
        capacity_per_agent: Optional[int] = None,
        is_active: bool = True,
        group_id: Optional[Union[str, UUID, GroupId]] = None,
        created_at: Optional[datetime] = None,
    ) -> "SalesGroup":
        strategy = (
            default_strategy
            if isinstance(default_strategy, AssignmentStrategy)
            else AssignmentStrategy(default_strategy)
        )
        return cls(
            id=group_id if isinstance(group_id, GroupId) else GroupId(group_id),
            tenant_id=tenant_id if isinstance(tenant_id, TenantId) else TenantId(tenant_id),
            name=_require_name(name),
            description=description,
            default_strategy=strategy,
            capacity_per_agent=_validate_capacity(capacity_per_agent),
            is_active=is_active,
            created_at=created_at or datetime.now(timezone.utc),
        )

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False

    def rename(self, name: str) -> None:
        self.name = _require_name(name)

    def has_capacity_for(self, active_leads: int) -> bool:
        """Whether an agent carrying this many leads can take one more."""
        if self.capacity_per_agent is None:
            return True
        return active_leads < self.capacity_per_agent


def _require_name(name: str) -> str:
    clean = (name or "").strip()
    if not clean:
        raise DomainException(
            "El nombre del grupo no puede estar vacío",
            error_code="INVALID_GROUP_NAME",
        )
    return clean


def _validate_capacity(capacity: Optional[int]) -> Optional[int]:
    if capacity is not None and capacity <= 0:
        raise DomainException(
            "La capacidad por asesor debe ser mayor que cero",
            error_code="INVALID_GROUP_CAPACITY",
        )
    return capacity
```

- [ ] **Step 6: Ejecutar y verificar que pasa**

```bash
uv run pytest tests/unit/domain/test_sales_group.py -v
```

Expected: PASS, 12 casos.

- [ ] **Step 7: Commit**

```bash
git add backend/src/domain/ backend/tests/unit/domain/test_sales_group.py
git commit -m "feat(domain): add the sales group aggregate with its assignment policy"
```

---

## Task 3: La entidad `AssignmentRule`

**Files:**
- Modify: `backend/src/domain/entities/rule.py`
- Test: `backend/tests/unit/domain/test_assignment_rule.py` (crear)

**Interfaces:**
- Consumes: `GroupId` y `AgentMatchMode` (Task 2).
- Produces: `AssignmentRule` con `create(...)`, `matches_score(score)`, `resolve_strategy(group)`, `advance_cursor(size)`. `RoutingRule` **desaparece**.

- [ ] **Step 1: Escribir los tests**

Crear `backend/tests/unit/domain/test_assignment_rule.py`:

```python
import uuid

import pytest

from domain.entities.rule import AssignmentRule
from domain.entities.sales_group import SalesGroup
from domain.exceptions import DomainException
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy

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
```

- [ ] **Step 2: Ejecutar y verificar que falla**

```bash
uv run pytest tests/unit/domain/test_assignment_rule.py -v
```

Expected: FAIL con `ImportError: cannot import name 'AssignmentRule' from 'domain.entities.rule'`.

- [ ] **Step 3: Sustituir `RoutingRule` por `AssignmentRule`**

En `backend/src/domain/entities/rule.py`, **borrar** la clase `RoutingRule` completa y poner en su lugar:

```python
@dataclass
class AssignmentRule:
    """Decides which agents may receive a lead of a given score.

    Replaces RoutingRule. The differences are what made the old one
    unusable: no name to show in an interface, no upper bound so bands could
    not be expressed, no priority so ties resolved by whatever order the
    database returned rows, and a rotation cursor living in memory."""

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

        parsed_agent_ids = [UUID(str(i)) for i in target_agent_ids] if target_agent_ids else []
        parsed_group_id = UUID(str(target_group_id)) if target_group_id else None
        if parsed_group_id is None and not parsed_agent_ids:
            raise DomainException(
                "La regla debe apuntar a un grupo o a asesores concretos",
                error_code="RULE_WITHOUT_TARGET",
            )

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
            name=clean_name,
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
```

Ajustar los imports de la cabecera del fichero: hace falta `AgentMatchMode` desde `domain.value_objects.enums`, `DomainException` desde `domain.exceptions`, y `SalesGroup` **sólo bajo `TYPE_CHECKING`** para no crear un ciclo de importación entre entidades.

- [ ] **Step 4: Ejecutar y verificar que pasa**

```bash
uv run pytest tests/unit/domain/test_assignment_rule.py -v
```

Expected: PASS, 14 casos.

- [ ] **Step 5: Localizar lo que quedó roto**

```bash
cd backend
rg -n "RoutingRule|routing_rule" --glob '*.py' src/ tests/
```

Todo lo que aparezca debe migrarse a `AssignmentRule`. No lo hagas ahora: las tareas 5, 6 y 7 lo cubren fichero a fichero. Anota la lista en tu informe para que quien las ejecute sepa qué esperar.

- [ ] **Step 6: Commit**

```bash
git add backend/src/domain/entities/rule.py backend/tests/unit/domain/test_assignment_rule.py
git commit -m "feat(domain): replace routing rules with score-banded assignment rules"
```

---

## Task 4: `Agent.group_id` sustituye a `Agent.team`

**Files:**
- Modify: `backend/src/domain/entities/agent.py`
- Modify: `backend/tests/unit/domain/test_agent.py` (o el fichero donde vivan los tests de `Agent`)

**Interfaces:**
- Produces: `Agent.group_id: Optional[GroupId]`. El campo `team` **desaparece**.

- [ ] **Step 1: Localizar los tests actuales de `Agent`**

```bash
cd backend
rg -ln "Agent.create" tests/unit/
```

- [ ] **Step 2: Escribir los tests del campo nuevo**

Añadir al fichero de tests de `Agent`:

```python
class TestAgentGroupMembership:
    def test_an_agent_starts_without_a_group(self):
        """Belonging to a group is a decision the manager makes later."""
        agent = Agent.create(name="Ana", email="ana@a.test")
        assert agent.group_id is None

    def test_an_agent_can_be_created_inside_a_group(self):
        group_id = uuid.uuid4()
        agent = Agent.create(name="Ana", email="ana@a.test", group_id=group_id)
        assert agent.group_id is not None
        assert agent.group_id.value == group_id

    def test_the_group_can_be_given_as_a_string(self):
        group_id = uuid.uuid4()
        agent = Agent.create(name="Ana", email="ana@a.test", group_id=str(group_id))
        assert agent.group_id.value == group_id
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Expected: FAIL con `TypeError: create() got an unexpected keyword argument 'group_id'`.

- [ ] **Step 4: Cambiar la entidad**

En `backend/src/domain/entities/agent.py`, sustituir el campo `team: str` por `group_id: Optional[GroupId] = None`, y en `create()` sustituir el parámetro `team: str` por `group_id: Optional[Union[str, UUID, GroupId]] = None`, resolviéndolo igual que se resuelve `tenant_id`.

`team` era obligatorio y `group_id` es opcional. No es un descuido: un asesor recién creado todavía no tiene grupo, y forzar uno obligaría a inventar un grupo "sin grupo".

Importar `GroupId` desde `domain.value_objects.group_id`.

- [ ] **Step 5: Ejecutar los tests unitarios de dominio**

```bash
uv run pytest -m unit tests/unit/domain/ -q
```

Expected: PASS en dominio. **Fuera de `tests/unit/domain/` habrá fallos**: todo lo que construye un `Agent` pasando `team=` deja de funcionar. Es lo esperado; las tareas 5 a 7 lo arreglan capa a capa.

- [ ] **Step 6: Inventariar el alcance de la rotura**

```bash
rg -n "team=|\.team|\"team\"|'team'" --glob '*.py' src/ tests/ | wc -l
rg -ln "team=|\.team|\"team\"|'team'" --glob '*.py' src/ tests/
```

Anota en tu informe la lista de ficheros. Es el mapa de trabajo de las tareas siguientes.

- [ ] **Step 7: Commit**

```bash
git add backend/src/domain/entities/agent.py backend/tests/unit/domain/
git commit -m "feat(domain): replace the free-form team string with a group reference"
```

---

## Task 5: El motor de asignación

**Files:**
- Modify: `backend/src/domain/services/router_engine.py` (renombrar a `assignment_engine.py`)
- Test: `backend/tests/unit/domain/test_assignment_engine.py` (crear)

**Interfaces:**
- Consumes: `AssignmentRule`, `SalesGroup`, `Agent`, `Lead`.
- Produces: `AssignmentEngine.select_agent(lead, rules, agents, groups, loads) -> Optional[Agent]`, donde `groups` es `Dict[UUID, SalesGroup]` y `loads` es `Dict[UUID, int]` con la carga real de cada asesor.

El motor deja de ser un objeto con estado. El cursor rotatorio vive ahora en la regla, que se persiste; el motor sólo lo hace avanzar. Eso elimina el bug por el que el reparto rotatorio dependía de que la instancia sobreviviera entre peticiones.

- [ ] **Step 1: Escribir los tests**

Crear `backend/tests/unit/domain/test_assignment_engine.py`:

```python
import uuid
from typing import Dict, List, Optional

import pytest

from domain.entities.agent import Agent
from domain.entities.lead import Lead
from domain.entities.rule import AssignmentRule
from domain.entities.sales_group import SalesGroup
from domain.services.assignment_engine import AssignmentEngine
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy

_TENANT = uuid.uuid4()


def _lead(score: int) -> Lead:
    lead = Lead.create(
        tenant_id=_TENANT,
        first_name="Laura",
        last_name="Diaz",
        email="laura@example.com",
        company="Globex",
        budget=1000,
        industry="Tech",
    )
    lead.score.value = score
    return lead


def _agent(name: str, group_id: Optional[uuid.UUID] = None, active: bool = True) -> Agent:
    return Agent.create(
        name=name, email=f"{name.lower()}@a.test", tenant_id=_TENANT,
        group_id=group_id, is_active=active,
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
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Expected: FAIL con `ModuleNotFoundError: No module named 'domain.services.assignment_engine'`.

- [ ] **Step 3: Escribir el motor**

Crear `backend/src/domain/services/assignment_engine.py` implementando el algoritmo de la sección 7.2 del spec:

```
1. Filtrar reglas activas cuya banda contenga la puntuación.
   Ordenar por priority descendente, id ascendente como desempate estable.
2. Para cada regla, en ese orden:
   a. Candidatos según agent_match_mode:
        ANY  → miembros del grupo ∪ asesores nombrados
        ONLY → miembros del grupo ∩ asesores nombrados
   b. Filtrar: misma organización que el lead, activos,
      de grupo activo, por debajo de capacity_per_agent.
   c. Sin candidatos → siguiente regla (cascada).
   d. Aplicar la estrategia resuelta.
   e. Devolver el asesor.
3. Ninguna regla produce asesor → devolver None.
```

Código literal:

```python
from typing import Dict, List, Optional
from uuid import UUID

from domain.entities.agent import Agent
from domain.entities.lead import Lead
from domain.entities.rule import AssignmentRule
from domain.entities.sales_group import SalesGroup
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy


class AssignmentEngine:
    """Picks the agent a lead goes to.

    Stateless on purpose: the rotation cursor lives on the rule, which is
    persisted. The previous engine kept it in memory, so every request got a
    fresh instance and round-robin always chose the same agent."""

    def select_agent(
        self,
        lead: Lead,
        rules: List[AssignmentRule],
        agents: List[Agent],
        groups: Dict[UUID, SalesGroup],
        loads: Dict[UUID, int],
    ) -> Optional[Agent]:
        for rule in self._ordered_rules(rules, int(lead.score)):
            group = groups.get(rule.target_group_id) if rule.target_group_id else None
            candidates = self._candidates_for(rule, group, agents, groups, loads)
            if not candidates:
                # Cascade: an empty rule used to end the search and lose the lead.
                continue
            return self._apply_strategy(lead, rule, group, candidates, loads)
        return None

    @staticmethod
    def _ordered_rules(rules: List[AssignmentRule], score: int) -> List[AssignmentRule]:
        applicable = [r for r in rules if r.is_active and r.matches_score(score)]
        # The id breaks ties: without it, two rules of equal priority resolve
        # by whatever order the database returned them.
        return sorted(applicable, key=lambda r: (-r.priority, str(r.id)))

    def _candidates_for(
        self,
        rule: AssignmentRule,
        group: Optional[SalesGroup],
        agents: List[Agent],
        groups: Dict[UUID, SalesGroup],
        loads: Dict[UUID, int],
    ) -> List[Agent]:
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
        agent: Agent,
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
        candidates: List[Agent],
        loads: Dict[UUID, int],
    ) -> Agent:
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

        lead.assign_to_agent(selected.id)
        return selected
```

Cuatro puntos donde es fácil equivocarse, y por los que el código de arriba está escrito así:

- **El desempate debe ser estable**, tanto entre reglas como entre asesores. Es el defecto que esta fase corrige: hoy el orden lo decide la base de datos.
- **Un asesor sin grupo es candidato sólo si la regla lo nombra.** Excluirlo por no tener grupo sería descartar justo a quien el gestor pidió por su nombre; incluirlo siempre lo metería en reglas que apuntan a un grupo al que no pertenece.
- **`ROUND_ROBIN` ordena los candidatos antes de indexar.** Sin orden fijo, el cursor apunta a personas distintas en cada petición y deja de ser una rotación.
- **La carga sale de `loads`, nunca de `agent.active_leads_count`.** Ese campo desaparece en la Task 6.

Borrar `backend/src/domain/services/router_engine.py`.

- [ ] **Step 4: Ejecutar y verificar que pasa**

```bash
uv run pytest tests/unit/domain/test_assignment_engine.py -v
```

Expected: PASS, 15 casos.

- [ ] **Step 5: Commit**

```bash
git add backend/src/domain/services/ backend/tests/unit/domain/test_assignment_engine.py
git commit -m "feat(domain): rewrite the assignment engine with cascade, capacity and match modes"
```

---

## Task 6: Persistencia de grupos, reglas y carga derivada

**Files:**
- Create: `backend/migrations/003_groups_and_assignment.sql`
- Create: `backend/src/application/ports/output/sales_group_repository_port.py`
- Create: `backend/src/infrastructure/adapters/output/persistence/raw_sql_sales_group_repository.py`
- Create: `backend/tests/unit/mocks/in_memory_sales_group_repo.py`
- Modify: `backend/src/application/ports/output/{rule,agent,lead}_repository_port.py`
- Modify: `backend/src/application/ports/output/unit_of_work_port.py`
- Modify: `backend/src/infrastructure/adapters/output/persistence/{raw_sql_rule,raw_sql_agent,raw_sql_lead,postgres_unit_of_work}.py`
- Test: `backend/tests/integration/test_raw_sql_sales_group_repo.py`, `backend/tests/integration/test_assignment_rule_repo.py`

**Interfaces:**
- Produces: `SalesGroupRepositoryPort` (`save`, `get_by_id`, `list_by_tenant`, `count_by_tenant`, `delete`), `RuleRepositoryPort.get_assignment_rules_by_tenant` / `save_assignment_rule` / `delete_assignment_rule`, `LeadRepositoryPort.active_load_by_agent(tenant_id) -> Dict[UUID, int]`, y `UnitOfWorkPort.groups`.

- [ ] **Step 1: Escribir la migración**

Crear `backend/migrations/003_groups_and_assignment.sql`:

```sql
CREATE TABLE IF NOT EXISTS sales_groups (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    default_strategy TEXT NOT NULL DEFAULT 'LOWEST_LOAD',
    capacity_per_agent INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    -- Two groups with the same name in one organization would be
    -- indistinguishable in the manager's interface.
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS assignment_rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    min_score INTEGER NOT NULL DEFAULT 0,
    max_score INTEGER,
    -- SET NULL, not CASCADE: deleting a group must not silently delete the
    -- rules that pointed at it. The manager sees a rule without target and
    -- decides.
    target_group_id UUID REFERENCES sales_groups (id) ON DELETE SET NULL,
    target_agent_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    agent_match_mode TEXT NOT NULL DEFAULT 'ANY',
    strategy TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    rr_cursor INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_assignment_rules_tenant
    ON assignment_rules (tenant_id, priority DESC);

ALTER TABLE agents DROP COLUMN IF EXISTS team;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS group_id UUID
    REFERENCES sales_groups (id) ON DELETE SET NULL;
ALTER TABLE agents DROP COLUMN IF EXISTS active_leads_count;

CREATE INDEX IF NOT EXISTS idx_agents_group ON agents (group_id);

-- The engine asks for each agent's current load on every ingestion.
CREATE INDEX IF NOT EXISTS idx_leads_assigned_agent
    ON leads (assigned_agent_id) WHERE assigned_agent_id IS NOT NULL;

DROP TABLE IF EXISTS routing_rules;
```

`active_leads_count` desaparece de la tabla. Era un contador que sólo subía —`+1` en cada asignación, nunca `-1`—, así que divergía de la realidad desde el segundo lead. La carga pasa a derivarse con un `COUNT` sobre `leads`.

- [ ] **Step 2: Escribir el test del repositorio de grupos**

Crear `backend/tests/integration/test_raw_sql_sales_group_repo.py`, siguiendo el patrón de `backend/tests/integration/test_raw_sql_tenant_repo.py`. Léelo primero y replica su estructura de fixtures. Cubrir: alta y relectura, `list_by_tenant` sin filtrar a otra organización, el rechazo del nombre duplicado dentro de una organización, que el mismo nombre sí valga en dos organizaciones distintas, y que `delete` sobre un grupo con asesores deje a esos asesores con `group_id` nulo en vez de borrarlos.

- [ ] **Step 3: Escribir el test de la carga derivada**

Añadir a `backend/tests/integration/` un test que cree tres leads asignados a un asesor y uno a otro, y compruebe que `active_load_by_agent(tenant_id)` devuelve `{ana: 3, beto: 1}`. Incluir un lead **sin asignar** y otro en estado `DISQUALIFIED` para comprobar que ninguno de los dos cuenta.

- [ ] **Step 4: Ejecutar y verificar que fallan**

Expected: FAIL por módulos y métodos inexistentes.

- [ ] **Step 5: Escribir el puerto y el repositorio de grupos**

`SalesGroupRepositoryPort` como `abc.ABC`, con las firmas de la sección Interfaces. La implementación sigue el patrón exacto de `RawSqlTenantRepository` — misma forma de `save` con `ON CONFLICT (id) DO UPDATE`, mismo `_to_group` estático.

- [ ] **Step 6: Migrar el repositorio de reglas**

En `RuleRepositoryPort` y en `RawSqlRuleRepository`, sustituir los métodos de `routing_rules` por los de `assignment_rules`. `save_assignment_rule` debe persistir `rr_cursor`: si no lo hace, el reparto rotatorio vuelve a empezar de cero en cada petición y el bug que esta fase corrige reaparece intacto.

- [ ] **Step 7: Añadir la carga derivada**

En `LeadRepositoryPort` y `RawSqlLeadRepository`:

```python
    def active_load_by_agent(self, tenant_id: UUID) -> Dict[UUID, int]:
        """Return how many active leads each agent of this organization holds.

        Derived on read rather than kept in a counter column: a counter that
        is only ever incremented drifts from reality on the first lead that
        gets discarded or reassigned."""
        rows = self.connection.execute(
            """
            SELECT assigned_agent_id, COUNT(*) AS load
            FROM leads
            WHERE tenant_id = %s
              AND assigned_agent_id IS NOT NULL
              AND status = %s
            GROUP BY assigned_agent_id
            """,
            (tenant_id, LeadStatus.ASSIGNED.value),
        ).fetchall()
        return {row["assigned_agent_id"]: int(row["load"]) for row in rows}
```

- [ ] **Step 8: Quitar `active_leads_count` y `team` del código**

```bash
rg -n "active_leads_count|update_active_count|\bteam\b" --glob '*.py' src/
```

Eliminar el campo de `Agent`, el método `update_active_count` del puerto y de sus implementaciones, y los rastros de `team` en los mappers. `Agent` gana `group_id` en su lugar.

- [ ] **Step 9: Exponer el repositorio en la unidad de trabajo**

Añadir `groups` a `UnitOfWorkPort`, a `PostgresUnitOfWork.__enter__` y al mock `InMemoryUnitOfWork`.

- [ ] **Step 10: Ejecutar los tests de integración**

```bash
uv run pytest -m integration -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add backend/migrations/ backend/src/ backend/tests/
git commit -m "feat(persistence): add group and assignment rule tables with derived agent load"
```

---

## Task 7: Casos de uso y CRUD

**Files:**
- Create: `backend/src/application/ports/input/sales_group_use_case_ports.py`
- Create: `backend/src/application/use_cases/sales_group_use_cases.py`
- Modify: `backend/src/application/use_cases/{agent,rule}_use_cases.py`
- Modify: `backend/src/application/dtos/{commands,queries}.py`
- Test: `backend/tests/unit/application/test_sales_group_use_cases.py`, y ampliar los de reglas y asesores

**Interfaces:**
- Produces: `CreateSalesGroupUseCase`, `GetSalesGroupsUseCase`, `UpdateSalesGroupUseCase`, `DeleteSalesGroupUseCase`; `CreateAssignmentRuleUseCase`, `GetAssignmentRulesUseCase`, `UpdateAssignmentRuleUseCase`, `DeleteAssignmentRuleUseCase`; `UpdateAgentUseCase`, `DeactivateAgentUseCase`.

- [ ] **Step 1: Escribir los tests de los casos de uso de grupo**

Crear `backend/tests/unit/application/test_sales_group_use_cases.py` sobre el `InMemoryUnitOfWork`, siguiendo el patrón de `backend/tests/unit/application/test_tenant_use_cases.py`. Cubrir como mínimo:

- Crear un grupo lo deja listado en su organización y no en otra.
- Crear un grupo con un nombre ya usado en la misma organización lanza `DomainException` con `GROUP_ALREADY_EXISTS`.
- El mismo nombre en otra organización se acepta.
- Renombrar cambia el nombre y conserva el identificador.
- Desactivar un grupo **no** desactiva a sus asesores: dejan de recibir asignaciones automáticas, pero siguen pudiendo entrar y atender los leads que ya tienen. Es la diferencia con desactivar una organización, que sí corta el acceso.
- Borrar un grupo deja a sus asesores sin grupo, sin borrarlos.

- [ ] **Step 2: Escribir los tests de los casos de uso de regla**

Cubrir: alta con banda y prioridad; que la actualización preserve `rr_cursor`; que el borrado no arrastre a los asesores; y que listar devuelva las reglas ordenadas por prioridad descendente.

- [ ] **Step 3: Escribir los tests del CRUD de asesores**

Cubrir: mover un asesor de grupo; que mover a un grupo de otra organización lance `DomainException`; y que desactivar un asesor lo saque de los candidatos sin borrar su histórico.

- [ ] **Step 4: Ejecutar y verificar que fallan**

Expected: FAIL por módulos inexistentes.

- [ ] **Step 5: Escribir los DTOs**

En `application/dtos/commands.py`, como `@dataclass(frozen=True)`: `CreateSalesGroupCommand`, `UpdateSalesGroupCommand`, `SalesGroupSummary` (grupo más recuento de asesores), `SalesGroupsPageResult`, `CreateAssignmentRuleCommand`, `UpdateAssignmentRuleCommand`, `UpdateAgentCommand`.

En `application/dtos/queries.py`: `GetSalesGroupsQuery`, `GetAssignmentRulesQuery`. Ambas llevan `tenant_id: UUID` obligatorio.

- [ ] **Step 6: Escribir los puertos de entrada y los casos de uso**

Un puerto `abc.ABC` por caso de uso, en `application/ports/input/`. Los casos de uso reciben la unidad de trabajo por constructor y abren `with self.uow:` en `execute`.

**Toda operación verifica que el recurso pertenece a la organización del comando** antes de tocarlo. Un gestor que envíe el identificador de un grupo de otra empresa debe recibir el mismo error que si no existiera — nunca una confirmación de que existe.

- [ ] **Step 7: Ejecutar y verificar que pasan**

```bash
uv run pytest -m unit -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/src/application/ backend/tests/unit/application/
git commit -m "feat(application): add group, assignment rule and agent management use cases"
```

---

## Task 8: Adaptadores HTTP e integración del motor

**Files:**
- Create: `backend/src/infrastructure/adapters/input/api/sales_group_router.py`
- Modify: `backend/src/infrastructure/adapters/input/api/{agent_router,rule_router,schemas,dependencies}.py`
- Modify: `backend/src/infrastructure/{main,di/container}.py`
- Modify: `backend/src/application/use_cases/ingest_lead_use_case.py`
- Modify: `docs/api/endpoints.md`
- Test: `backend/tests/e2e/test_assignment_flow_e2e.py` (crear)

**Interfaces:**
- Produces: `/api/v1/groups` (GET, POST, PATCH, DELETE), `/api/v1/rules/assignment` (GET, POST, PATCH, DELETE), `PATCH` y `DELETE` en `/api/v1/agents/{id}`.

- [ ] **Step 1: Escribir el test extremo a extremo**

Crear `backend/tests/e2e/test_assignment_flow_e2e.py`, que recorra el criterio de aceptación de la fase de punta a punta:

1. Bootstrap del administrador, creación de una organización con su gestor.
2. El gestor crea dos grupos: "Enterprise" con `capacity_per_agent = 1`, y "PYME" sin límite.
3. Crea tres asesores repartidos entre ambos.
4. Crea dos reglas: una de 70 a 100 puntos hacia "Enterprise" con prioridad 10, otra de 0 a 69 hacia "PYME" con prioridad 1.
5. Ingesta un lead de puntuación alta → cae en un asesor de "Enterprise".
6. Ingesta un segundo lead alto → el asesor anterior está al tope, así que **cae en el otro** o desciende por cascada a "PYME".
7. Ingesta un lead de puntuación baja → cae en "PYME".
8. Comprueba que un asesor de otra organización jamás aparece como destinatario.

Todos los endpoints se llaman con el token del gestor. Un `AGENT` recibe 403 en el CRUD de grupos y de reglas.

- [ ] **Step 2: Ejecutar y verificar que falla**

Expected: FAIL con 404 en `/api/v1/groups`.

- [ ] **Step 3: Escribir los esquemas Pydantic**

En `schemas.py`: `SalesGroupCreate`, `SalesGroupUpdate`, `SalesGroupResponse`, `PaginatedGroupsResponse`, `AssignmentRuleCreate`, `AssignmentRuleUpdate`, `AssignmentRuleResponse`, `PaginatedAssignmentRulesResponse`, `AgentUpdate`.

Ninguno lleva `tenant_id`: la organización sale del token. Un campo así en el cuerpo es una invitación a suplantarla.

- [ ] **Step 4: Escribir el router de grupos**

`sales_group_router.py`, con `require_organization_manager` como dependencia en los cuatro endpoints. Registrarlo en `main.py` bajo el prefijo `/api/v1/groups`.

- [ ] **Step 5: Ampliar el router de reglas**

Añadir los endpoints de `assignment` bajo el prefijo existente `/api/v1/rules`. **Un `APIRouter` no admite dos prefijos distintos**: si necesitas rutas que cuelguen de otro sitio, crea un router aparte.

- [ ] **Step 6: Ampliar el router de asesores**

`PATCH /api/v1/agents/{id}` para cambiar nombre y grupo, y `DELETE /api/v1/agents/{id}` que **desactiva en vez de borrar**: los leads históricos apuntan a ese asesor y borrarlo dejaría referencias rotas.

- [ ] **Step 7: Integrar el motor en la ingesta**

En `ingest_lead_use_case.py`:

- **Eliminar la rama sin unidad de trabajo.** Hoy el algoritmo está escrito dos veces, con y sin `uow`, y cualquier cambio hay que hacerlo en ambos sitios o divergen. Los tests que dependían de la rama sin `uow` pasan a usar el `InMemoryUnitOfWork`.
- Sustituir `RouterEngine` por `AssignmentEngine`.
- Antes de asignar, cargar lo que el motor necesita: `uow.rules.get_assignment_rules_by_tenant(tenant)`, `uow.agents.get_available_agents(tenant)`, `uow.groups.list_by_tenant(tenant)` indexado por identificador, y `uow.leads.active_load_by_agent(tenant)`.
- Después de asignar, **guardar la regla** si su estrategia era rotatoria: el cursor avanzó y debe persistir en la misma transacción.
- Quitar la llamada a `update_active_count`, que ya no existe.

- [ ] **Step 8: Actualizar el contenedor**

En `di/container.py`, sustituir `RouterEngine` por `AssignmentEngine`. Ya no necesita ser singleton —el motor dejó de tener estado—, pero mantenerlo como propiedad no molesta.

- [ ] **Step 9: Ejecutar la suite completa**

```bash
uv run pytest -q
```

Expected: PASS. **Toda la suite en verde**: es el cierre de la fase.

- [ ] **Step 10: Validar el circuito con Docker**

```bash
docker compose down -v
docker compose up -d --build db backend
docker compose logs backend | tail -30
```

Y con `curl` contra `http://localhost:8001`, recorrer el criterio de aceptación: crear grupos, asesores y reglas, ingestar leads de distintas puntuaciones y comprobar a quién se asignó cada uno consultando la base de datos.

Comprobar en particular las tres estrategias:
- `LOWEST_LOAD`: dos leads seguidos no caen en el mismo asesor si el primero ya le dio carga.
- `ROUND_ROBIN`: **tres leads seguidos rotan entre los asesores**. Es la prueba de que el cursor persiste; con el motor anterior los tres caían en el mismo.
- `DIRECT_AGENT`: cae en el primero de `target_agent_ids`.

```bash
docker compose --profile test run --rm --build backend-test
```

Expected: toda la suite en verde dentro del contenedor. El `--build` no es opcional.

- [ ] **Step 11: Actualizar la documentación**

En `docs/api/endpoints.md`, documentar los endpoints nuevos, el cambio de `team` a `group_id` en las respuestas de asesor, y la desaparición de `active_leads_count`.

- [ ] **Step 12: Commit**

```bash
git add backend/ docs/
git commit -m "feat(api): expose group and assignment rule management and wire the new engine"
```

---

## Criterio de aceptación de F1

- [ ] Guardián de arquitectura en 4/4.
- [ ] `pytest -m unit` en verde sin base de datos ni variables de entorno.
- [ ] La suite completa en verde, dentro y fuera de Docker.
- [ ] Un gestor crea grupos, asesores y reglas desde la API, y un lead ingestado se asigna al asesor correcto.
- [ ] **Las tres estrategias verificadas con `curl`**, y el reparto rotatorio rota de verdad entre peticiones distintas.
- [ ] Un asesor al tope de capacidad queda excluido y el lead pasa al siguiente candidato.
- [ ] Cuando una regla se queda sin candidatos, el motor prueba la siguiente en vez de rendirse.
- [ ] **Ningún lead se asigna jamás a un asesor de otra organización**, comprobado con dos organizaciones cuyos grupos se llaman igual.
- [ ] La carga de un asesor coincide con el número real de leads que tiene asignados.
- [ ] `rg "RoutingRule|active_leads_count|\.team"` no devuelve nada en `src/`.
- [ ] El sistema arranca desde volumen vacío y aplica las tres migraciones.

## Notas para quien ejecute el plan

**Orden.** La 1 es independiente y va primero por urgencia. La 2 antes que la 3 y la 4. Las 3 y 4 antes que la 5. La 5 antes que la 6. La 7 antes que la 8.

**Las tareas 3 y 4 dejan tests en rojo a propósito.** Retirar `RoutingRule` y `Agent.team` rompe todo lo que los usaba, y esos rastros se limpian capa a capa en las tareas 6, 7 y 8. Es el coste esperado de un cambio de modelo; no lo parchees desde el dominio.

**Criterio de parada.** Si un paso "verificar que falla" produce un fallo distinto del descrito, detenerse y reportar.

**Lo que esta fase NO toca:** el motor de puntuación (sus correcciones están en la sección 7.1 del spec y no tienen fase asignada), la bandeja de entrada, la máquina de estados del lead, las notificaciones y el frontend. Si aparece la tentación de arreglar algo de eso de camino, anótalo en el informe en vez de hacerlo.
