# F0.5 — Separación de planos: Plan de Implementación

> # ✅ FASE CERRADA — NO EJECUTAR
>
> Este plan **ya está implementado y verificado** (9 commits, 41 ficheros). Se conserva como registro
> de lo que se hizo y por qué, no como trabajo pendiente. Si eres un agente al que han encargado
> implementar algo, **este no es tu plan**: busca en [docs/plans/](.) el que no lleva esta marca.
>
> El estado del código es posterior a este documento: fases más recientes cambiaron parte de lo que
> aquí se describe. Para saber cómo está el sistema **hoy**, lee el
> [spec del MVP](../specs/2026-08-07-lead-router-mvp-design.md), no este plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar el plano de plataforma del plano de organización, de modo que el administrador gestione organizaciones sin acceder a los datos de ninguna, y cerrar la última fuga cross-tenant que sigue abierta en los endpoints de asesores.

**Architecture:** Se introduce `Tenant` como agregado con su tabla, repositorio y casos de uso. `AuthorizationPolicy` pasa de una jerarquía de privilegios —donde el administrador era un superconjunto del gestor— a dos planos disjuntos. Los repositorios de asesores incorporan el criterio de organización, que hoy no admiten en ningún método. Un endpoint de identidad permite al cliente saber en qué plano está.

**Tech Stack:** Python 3.12+, FastAPI, psycopg 3 (raw SQL, sin ORM), pytest, uv, PostgreSQL 16, Docker Compose.

**Estado de partida:** F0 cerrada. 125 tests en verde, guardián de arquitectura 4/4, stack arrancando desde volumen vacío.

## Global Constraints

- Todo el código, nombres, docstrings y comentarios **en inglés**. La documentación en español.
- **Prohibido cualquier ORM.** SQL parametrizado sobre `psycopg` 3, marcadores `%s`.
- `domain/` no importa nada fuera de la biblioteca estándar.
- `application/` importa sólo de `domain/` y de la biblioteca estándar. **Nunca** de `infrastructure/`.
- Los puertos son `abc.ABC` con `@abc.abstractmethod`. Los DTOs de aplicación son `@dataclass(frozen=True)`.
- **El guardián `tests/architecture/` debe permanecer en 4/4 en todo momento.**
- `pytest -m unit` debe pasar sin base de datos, sin red y sin variables de entorno.
- Los comentarios explican el **porqué**, nunca el qué.
- Mensajes de commit en inglés, `type(scope): description`. **Sin** `Co-authored-by`.
- No `git push`, no ramas nuevas. Rama de trabajo: `repo-status-mvp`.
- Anota los tipos en las funciones auxiliares de test. Un parámetro que pueda recibir `None` se declara `Optional[...]`.
- **Puertos del host:** PostgreSQL en **5433**, API en **8001**. Dentro de la red de compose siguen siendo 5432 y 8000.

```bash
export DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export TEST_DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export JWT_SECRET=test-secret-do-not-use-in-production
```

## Agrupación sugerida en despachos

Siete tareas, cinco despachos:

| Bloque | Tareas | Validación |
|---|---|---|
| A | 1 + 2 | pytest |
| B | 3 | pytest + base de datos |
| C | 4 + 5 | pytest |
| D | 6 | **Docker + curl + base de datos** |
| E | 7 | **Docker + curl + base de datos** |

## Mapa de ficheros

**Se crean:** `domain/entities/tenant.py` · `domain/policies/authorization_policy.py` (reescrito) · `application/ports/output/tenant_repository_port.py` · `application/ports/input/tenant_use_case_ports.py` · `application/use_cases/tenant_use_cases.py` · `infrastructure/adapters/output/persistence/raw_sql_tenant_repository.py` · `infrastructure/adapters/input/api/tenant_router.py` · `infrastructure/cli/sync_tenants.py` · `migrations/002_tenants.sql` · sus tests.

**Se modifican:** `application/ports/output/agent_repository_port.py` · `application/ports/output/unit_of_work_port.py` · `application/use_cases/agent_use_cases.py` · `application/dtos/{commands,queries}.py` · `infrastructure/adapters/output/persistence/{raw_sql_agent_repository,postgres_unit_of_work}.py` · `infrastructure/adapters/input/api/{agent_router,auth_router,schemas,dependencies}.py` · `infrastructure/main.py` · `infrastructure/di/container.py` · `docs/api/endpoints.md`.

---

## Task 1: Entidad `Tenant`

**Files:**
- Create: `backend/src/domain/entities/tenant.py`
- Create: `backend/tests/unit/domain/test_tenant.py`

**Interfaces:**
- Consumes: `TenantId` de `domain.value_objects.tenant_id`, `DomainException`.
- Produces: `Tenant` con `create(name, tenant_id=None, slug=None, is_active=True, created_at=None)`, métodos `activate()`, `deactivate()`, `rename(name)`, y la función de módulo `slugify(value) -> str`.

- [ ] **Step 1: Escribir el test**

Crear `backend/tests/unit/domain/test_tenant.py`:

```python
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from domain.entities.tenant import Tenant, slugify
from domain.exceptions import DomainException


class TestSlugify:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("Acme Corp", "acme-corp"),
            ("  Spaced  Out  ", "spaced-out"),
            ("ACME", "acme"),
            ("Ñandú & Cía.", "nandu-cia"),
            ("multi---dash", "multi-dash"),
            ("Solución 360", "solucion-360"),
        ],
    )
    def test_produces_a_url_safe_identifier(self, value: str, expected: str):
        assert slugify(value) == expected

    def test_rejects_a_value_with_no_usable_characters(self):
        with pytest.raises(DomainException):
            slugify("!!!")


class TestCreation:
    def test_derives_the_slug_from_the_name(self):
        assert Tenant.create(name="Acme Corp").slug == "acme-corp"

    def test_accepts_an_explicit_slug(self):
        assert Tenant.create(name="Acme Corp", slug="legacy-acme").slug == "legacy-acme"

    def test_generates_an_identifier_when_none_is_given(self):
        assert isinstance(Tenant.create(name="Acme").id.value, UUID)

    def test_accepts_an_explicit_identifier(self):
        given = uuid4()
        assert str(Tenant.create(name="Acme", tenant_id=given).id) == str(given)

    def test_is_active_by_default(self):
        assert Tenant.create(name="Acme").is_active is True

    def test_stamps_a_creation_time(self):
        moment = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
        assert Tenant.create(name="Acme", created_at=moment).created_at == moment

    def test_rejects_an_empty_name(self):
        with pytest.raises(DomainException):
            Tenant.create(name="")

    def test_rejects_a_whitespace_only_name(self):
        with pytest.raises(DomainException):
            Tenant.create(name="   ")

    def test_trims_the_name(self):
        assert Tenant.create(name="  Acme  ").name == "Acme"


class TestLifecycle:
    def test_deactivate_marks_it_inactive(self):
        tenant = Tenant.create(name="Acme")
        tenant.deactivate()
        assert tenant.is_active is False

    def test_activate_restores_it(self):
        tenant = Tenant.create(name="Acme")
        tenant.deactivate()
        tenant.activate()
        assert tenant.is_active is True

    def test_rename_changes_the_name(self):
        tenant = Tenant.create(name="Acme")
        tenant.rename("Acme Global")
        assert tenant.name == "Acme Global"

    def test_rename_does_not_change_the_slug(self):
        """The slug is a stable reference: renaming must not break anything
        that already points at this organization."""
        tenant = Tenant.create(name="Acme Corp")
        tenant.rename("Totally Different")
        assert tenant.slug == "acme-corp"

    def test_rename_rejects_an_empty_name(self):
        tenant = Tenant.create(name="Acme")
        with pytest.raises(DomainException):
            tenant.rename("  ")
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/domain/test_tenant.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'domain.entities.tenant'`.

- [ ] **Step 3: Implementar la entidad**

Crear `backend/src/domain/entities/tenant.py`:

```python
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.tenant_id import TenantId

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Turn a display name into a stable, URL-safe identifier.

    Accents are folded rather than dropped so that "Solución" and "Solucion"
    collapse to the same slug instead of producing two organizations that read
    identically to a human."""
    folded = unicodedata.normalize("NFKD", value)
    ascii_only = folded.encode("ascii", "ignore").decode("ascii").lower()
    slug = _NON_ALPHANUMERIC.sub("-", ascii_only).strip("-")
    if not slug:
        raise DomainException(
            "El nombre no contiene caracteres utilizables para un identificador",
            error_code="INVALID_TENANT_NAME",
        )
    return slug


@dataclass
class Tenant:
    id: TenantId
    name: str
    slug: str
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        name: str,
        tenant_id: Optional[Union[str, UUID, TenantId]] = None,
        slug: Optional[str] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
    ) -> "Tenant":
        clean_name = _require_name(name)
        identifier = tenant_id if isinstance(tenant_id, TenantId) else TenantId(tenant_id)
        return cls(
            id=identifier,
            name=clean_name,
            slug=slug or slugify(clean_name),
            is_active=is_active,
            created_at=created_at or datetime.now(timezone.utc),
        )

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False

    def rename(self, name: str) -> None:
        # The slug deliberately stays put: it is what other records reference.
        self.name = _require_name(name)


def _require_name(name: str) -> str:
    clean = (name or "").strip()
    if not clean:
        raise DomainException(
            "El nombre de la organización no puede estar vacío",
            error_code="INVALID_TENANT_NAME",
        )
    return clean
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/domain/test_tenant.py -v`
Expected: PASS, 20 tests.

Run: `uv run pytest tests/architecture/ -q`
Expected: 4 passed. `unicodedata` y `re` son biblioteca estándar, así que el dominio sigue limpio.

- [ ] **Step 5: Commit**

```bash
git add backend/src/domain/entities/tenant.py backend/tests/unit/domain/test_tenant.py
git commit -m "feat(domain): add tenant entity with a stable derived slug"
```

---

## Task 2: Política de dos planos

Reescribe `AuthorizationPolicy`: el administrador deja de ser un superconjunto del gestor y pasa a operar en un plano disjunto.

**Files:**
- Modify: `backend/src/domain/policies/authorization_policy.py` (completo)
- Modify: `backend/tests/unit/domain/test_authorization_policy.py` (completo)

**Interfaces:**
- Consumes: `Agent`, `AgentRole`, `ForbiddenException`.
- Produces: `can_manage_platform`, `ensure_can_manage_platform`, `can_list_agents`, `ensure_can_list_agents`, además de los métodos ya existentes con su semántica corregida.

- [ ] **Step 1: Escribir el test**

Reemplazar el contenido completo de `backend/tests/unit/domain/test_authorization_policy.py`:

```python
from typing import Optional
from uuid import UUID, uuid4

import pytest

from domain.entities.agent import Agent
from domain.exceptions import ForbiddenException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.enums import AgentRole

_TENANT_A = uuid4()
_TENANT_B = uuid4()


def _agent(
    role: AgentRole,
    tenant_id: Optional[UUID] = None,
    agent_id: Optional[UUID] = None,
) -> Agent:
    return Agent.create(
        "Someone", "someone@test.com", "Sales", role=role, tenant_id=tenant_id, agent_id=agent_id
    )


def _admin() -> Agent:
    return _agent(AgentRole.ADMIN, tenant_id=None)


def _manager(tenant_id: UUID = _TENANT_A) -> Agent:
    return _agent(AgentRole.MANAGER, tenant_id=tenant_id)


def _sales(tenant_id: UUID = _TENANT_A, agent_id: Optional[UUID] = None) -> Agent:
    return _agent(AgentRole.AGENT, tenant_id=tenant_id, agent_id=agent_id)


class TestPlaneSeparation:
    def test_platform_admin_manages_the_platform(self):
        assert AuthorizationPolicy.can_manage_platform(_admin()) is True

    def test_nobody_else_manages_the_platform(self):
        assert AuthorizationPolicy.can_manage_platform(_manager()) is False
        assert AuthorizationPolicy.can_manage_platform(_sales()) is False

    def test_platform_admin_does_not_manage_an_organization(self):
        """The whole point of this phase: the administrator is not a superset
        of the manager, it is a different plane."""
        assert AuthorizationPolicy.can_manage_organization(_admin()) is False

    def test_manager_manages_its_organization(self):
        assert AuthorizationPolicy.can_manage_organization(_manager()) is True

    def test_sales_agent_manages_nothing(self):
        assert AuthorizationPolicy.can_manage_organization(_sales()) is False


class TestTenantAccess:
    def test_platform_admin_reaches_no_organization_data(self):
        admin = _admin()
        assert AuthorizationPolicy.can_access_tenant(admin, _TENANT_A) is False
        assert AuthorizationPolicy.can_access_tenant(admin, _TENANT_B) is False

    def test_manager_reaches_only_its_own(self):
        manager = _manager()
        assert AuthorizationPolicy.can_access_tenant(manager, _TENANT_A) is True
        assert AuthorizationPolicy.can_access_tenant(manager, _TENANT_B) is False

    def test_agent_without_organization_reaches_nothing(self):
        assert AuthorizationPolicy.can_access_tenant(_agent(AgentRole.AGENT), _TENANT_A) is False

    def test_ensure_raises_for_the_platform_admin_too(self):
        with pytest.raises(ForbiddenException):
            AuthorizationPolicy.ensure_can_access_tenant(_admin(), _TENANT_A)

    def test_ensure_is_silent_when_allowed(self):
        AuthorizationPolicy.ensure_can_access_tenant(_manager(), _TENANT_A)


class TestAgentCreation:
    def test_manager_creates_managers_and_agents(self):
        manager = _manager()
        assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.MANAGER) is True
        assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.AGENT) is True

    def test_nobody_creates_a_platform_admin_through_this_path(self):
        """The single platform administrator comes from bootstrap; no API path
        mints another one."""
        for actor in (_admin(), _manager(), _sales()):
            assert AuthorizationPolicy.can_create_agent_with_role(actor, AgentRole.ADMIN) is False

    def test_platform_admin_does_not_create_organization_users_directly(self):
        admin = _admin()
        assert AuthorizationPolicy.can_create_agent_with_role(admin, AgentRole.MANAGER) is False
        assert AuthorizationPolicy.can_create_agent_with_role(admin, AgentRole.AGENT) is False

    def test_sales_agent_creates_nobody(self):
        for role in AgentRole:
            assert AuthorizationPolicy.can_create_agent_with_role(_sales(), role) is False

    def test_ensure_raises_when_denied(self):
        with pytest.raises(ForbiddenException):
            AuthorizationPolicy.ensure_can_create_agent_with_role(_sales(), AgentRole.AGENT)


class TestAgentListing:
    def test_only_the_manager_lists_agents(self):
        assert AuthorizationPolicy.can_list_agents(_manager()) is True
        assert AuthorizationPolicy.can_list_agents(_sales()) is False
        assert AuthorizationPolicy.can_list_agents(_admin()) is False

    def test_ensure_raises_for_a_sales_agent(self):
        with pytest.raises(ForbiddenException):
            AuthorizationPolicy.ensure_can_list_agents(_sales())


class TestLeadVisibility:
    def test_manager_sees_every_lead_of_its_organization(self):
        assert AuthorizationPolicy.can_view_lead(_manager(), _TENANT_A, uuid4()) is True

    def test_manager_does_not_see_another_organization_leads(self):
        assert AuthorizationPolicy.can_view_lead(_manager(), _TENANT_B, uuid4()) is False

    def test_platform_admin_sees_no_leads_at_all(self):
        assert AuthorizationPolicy.can_view_lead(_admin(), _TENANT_A, uuid4()) is False

    def test_sales_agent_sees_only_its_own(self):
        own = uuid4()
        sales = _sales(agent_id=own)
        assert AuthorizationPolicy.can_view_lead(sales, _TENANT_A, own) is True
        assert AuthorizationPolicy.can_view_lead(sales, _TENANT_A, uuid4()) is False

    def test_sales_agent_does_not_see_unassigned_leads(self):
        own = uuid4()
        assert AuthorizationPolicy.can_view_lead(_sales(agent_id=own), _TENANT_A, None) is False
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/domain/test_authorization_policy.py -v`
Expected: FAIL. En concreto `test_platform_admin_does_not_manage_an_organization` y `test_platform_admin_reaches_no_organization_data` fallan porque la política actual concede ambas cosas al administrador, y los tests de `can_manage_platform` / `can_list_agents` fallan con `AttributeError` porque esos métodos no existen.

- [ ] **Step 3: Reescribir la política**

Reemplazar el contenido completo de `backend/src/domain/policies/authorization_policy.py`:

```python
from typing import Optional
from uuid import UUID

from domain.entities.agent import Agent
from domain.exceptions import ForbiddenException
from domain.value_objects.enums import AgentRole


def _same_id(left, right) -> bool:
    """Identifiers arrive as value objects, UUIDs or strings depending on the
    caller, so they are compared by their textual form."""
    return left is not None and right is not None and str(left) == str(right)


class AuthorizationPolicy:
    """Single source of truth for who may do what.

    The platform plane and the organization plane are disjoint: the
    administrator is not a more powerful manager, it operates on a different
    kind of object. That keeps a compromised platform credential away from
    every customer's data."""

    # --- Platform plane -----------------------------------------------------

    @staticmethod
    def can_manage_platform(actor: Agent) -> bool:
        return actor.role == AgentRole.ADMIN

    @staticmethod
    def ensure_can_manage_platform(actor: Agent) -> None:
        if not AuthorizationPolicy.can_manage_platform(actor):
            raise ForbiddenException("Only the platform administrator may perform this action")

    # --- Organization plane -------------------------------------------------

    @staticmethod
    def can_access_tenant(actor: Agent, tenant_id: UUID) -> bool:
        # The platform administrator has no organization and reaches none.
        return _same_id(actor.tenant_id, tenant_id)

    @staticmethod
    def ensure_can_access_tenant(actor: Agent, tenant_id: UUID) -> None:
        if not AuthorizationPolicy.can_access_tenant(actor, tenant_id):
            raise ForbiddenException("You do not have access to this organization's data")

    @staticmethod
    def can_manage_organization(actor: Agent) -> bool:
        return actor.role == AgentRole.MANAGER

    @staticmethod
    def ensure_can_manage_organization(actor: Agent) -> None:
        if not AuthorizationPolicy.can_manage_organization(actor):
            raise ForbiddenException(
                f"Role {actor.role.value} is not permitted to manage an organization"
            )

    @staticmethod
    def can_create_agent_with_role(actor: Agent, role: AgentRole) -> bool:
        if not AuthorizationPolicy.can_manage_organization(actor):
            return False
        # The single platform administrator comes from bootstrap. No API path
        # mints another one.
        return role != AgentRole.ADMIN

    @staticmethod
    def ensure_can_create_agent_with_role(actor: Agent, role: AgentRole) -> None:
        if not AuthorizationPolicy.can_create_agent_with_role(actor, role):
            raise ForbiddenException(f"You may not create an agent with role {role.value}")

    @staticmethod
    def can_list_agents(actor: Agent) -> bool:
        return AuthorizationPolicy.can_manage_organization(actor)

    @staticmethod
    def ensure_can_list_agents(actor: Agent) -> None:
        if not AuthorizationPolicy.can_list_agents(actor):
            raise ForbiddenException("You are not permitted to list agents")

    @staticmethod
    def can_view_lead(
        actor: Agent,
        lead_tenant_id: UUID,
        lead_assigned_agent_id: Optional[UUID],
    ) -> bool:
        if not AuthorizationPolicy.can_access_tenant(actor, lead_tenant_id):
            return False
        if AuthorizationPolicy.can_manage_organization(actor):
            return True
        # A sales agent sees only what is assigned to them.
        return _same_id(actor.id, lead_assigned_agent_id)

    @staticmethod
    def ensure_can_view_lead(
        actor: Agent,
        lead_tenant_id: UUID,
        lead_assigned_agent_id: Optional[UUID],
    ) -> None:
        if not AuthorizationPolicy.can_view_lead(actor, lead_tenant_id, lead_assigned_agent_id):
            raise ForbiddenException("You do not have access to this lead")
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/domain/test_authorization_policy.py -v`
Expected: PASS, 24 tests.

- [ ] **Step 5: Comprobar el daño colateral**

Run: `uv run pytest -q`

Los tests que hoy autentican como `ADMIN` para operar sobre datos de una organización **fallarán**, y es correcto: esa capacidad acaba de desaparecer. Anota cuáles fallan; la Task 6 los migra a un `MANAGER` real cuando el resto de la cadena esté en su sitio.

Si el número de fallos supera los seis, **detente y reporta**: significaría que la dependencia del administrador estaba más extendida de lo previsto.

- [ ] **Step 6: Commit**

```bash
git add backend/src/domain/policies/authorization_policy.py backend/tests/unit/domain/test_authorization_policy.py
git commit -m "feat(domain): split the platform plane from the organization plane

The platform administrator is no longer a superset of the manager: it operates
on organizations and reaches no customer data."
```

---

## Task 3: Persistencia de organizaciones

**Files:**
- Create: `backend/migrations/002_tenants.sql`
- Create: `backend/src/application/ports/output/tenant_repository_port.py`
- Create: `backend/src/infrastructure/adapters/output/persistence/raw_sql_tenant_repository.py`
- Modify: `backend/src/application/ports/output/unit_of_work_port.py`
- Modify: `backend/src/infrastructure/adapters/output/persistence/postgres_unit_of_work.py`
- Modify: `backend/tests/unit/mocks/in_memory_uow.py`
- Create: `backend/tests/unit/mocks/in_memory_tenant_repo.py`
- Create: `backend/tests/integration/test_raw_sql_tenant_repo.py`
- Modify: `backend/tests/conftest.py` (añadir `tenants` a las tablas truncadas)

**Interfaces:**
- Consumes: `Tenant` (Task 1).
- Produces: `TenantRepositoryPort` con `save`, `get_by_id`, `get_by_slug`, `list_all`, `count_all`, `count_active_agents`. `UnitOfWorkPort.tenants`. `InMemoryTenantRepository`.

- [ ] **Step 1: Escribir la migración**

Crear `backend/migrations/002_tenants.sql`:

```sql
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- Every agent query now filters by organization.
CREATE INDEX IF NOT EXISTS idx_agents_tenant ON agents (tenant_id);

-- Without these, two accounts can share an email and login authenticates
-- against whichever row the database happens to return first.
CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_email_per_tenant
    ON agents (tenant_id, email) WHERE tenant_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_platform_admin_email
    ON agents (email) WHERE tenant_id IS NULL;
```

No se añade clave foránea de `agents.tenant_id`: las filas existentes apuntan a organizaciones que nunca tuvieron respaldo y la restricción fallaría al aplicarse. F1 la añade tras sanear.

- [ ] **Step 2: Definir el puerto**

Crear `backend/src/application/ports/output/tenant_repository_port.py`:

```python
import abc
from typing import List, Optional
from uuid import UUID

from domain.entities.tenant import Tenant


class TenantRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, tenant: Tenant) -> Tenant:
        """Insert or update an organization."""

    @abc.abstractmethod
    def get_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        """Return the organization with this identifier, if it exists."""

    @abc.abstractmethod
    def get_by_slug(self, slug: str) -> Optional[Tenant]:
        """Return the organization with this slug, if it exists."""

    @abc.abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> List[Tenant]:
        """Return a page of organizations, ordered deterministically."""

    @abc.abstractmethod
    def count_all(self) -> int:
        """Return how many organizations exist."""

    @abc.abstractmethod
    def count_active_agents(self, tenant_id: UUID) -> int:
        """Return how many active users this organization has.

        An aggregate, deliberately: the platform plane sees activity without
        seeing identities."""
```

- [ ] **Step 3: Escribir el doble in-memory**

Crear `backend/tests/unit/mocks/in_memory_tenant_repo.py`:

```python
from typing import Dict, List, Optional
from uuid import UUID

from application.ports.output.tenant_repository_port import TenantRepositoryPort
from domain.entities.tenant import Tenant


class InMemoryTenantRepository(TenantRepositoryPort):
    def __init__(self) -> None:
        self._tenants: Dict[str, Tenant] = {}
        self._agent_counts: Dict[str, int] = {}

    def save(self, tenant: Tenant) -> Tenant:
        self._tenants[str(tenant.id)] = tenant
        return tenant

    def get_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        return self._tenants.get(str(tenant_id))

    def get_by_slug(self, slug: str) -> Optional[Tenant]:
        return next((t for t in self._tenants.values() if t.slug == slug), None)

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Tenant]:
        ordered = sorted(self._tenants.values(), key=lambda t: (t.created_at, str(t.id)))
        return ordered[offset : offset + limit]

    def count_all(self) -> int:
        return len(self._tenants)

    def count_active_agents(self, tenant_id: UUID) -> int:
        return self._agent_counts.get(str(tenant_id), 0)

    def set_agent_count(self, tenant_id: UUID, count: int) -> None:
        """Test seam: lets a test state the aggregate without wiring an agent
        repository into it."""
        self._agent_counts[str(tenant_id)] = count
```

- [ ] **Step 4: Escribir el test de integración**

Crear `backend/tests/integration/test_raw_sql_tenant_repo.py`:

```python
from uuid import uuid4

import psycopg
import pytest

from domain.entities.tenant import Tenant
from infrastructure.adapters.output.persistence.raw_sql_tenant_repository import (
    RawSqlTenantRepository,
)


def _repo(test_db):
    connection_context = test_db.get_connection(autocommit=True)
    connection = connection_context.__enter__()
    return RawSqlTenantRepository(connection), connection_context


def test_saves_and_reads_back_every_field(test_db):
    repo, ctx = _repo(test_db)
    try:
        saved = repo.save(Tenant.create(name="Acme Corp"))
        found = repo.get_by_id(saved.id.value)
        assert found is not None
        assert found.name == "Acme Corp"
        assert found.slug == "acme-corp"
        assert found.is_active is True
        assert str(found.id) == str(saved.id)
    finally:
        ctx.__exit__(None, None, None)


def test_finds_by_slug(test_db):
    repo, ctx = _repo(test_db)
    try:
        repo.save(Tenant.create(name="Acme Corp"))
        assert repo.get_by_slug("acme-corp") is not None
        assert repo.get_by_slug("nope") is None
    finally:
        ctx.__exit__(None, None, None)


def test_save_updates_an_existing_row(test_db):
    repo, ctx = _repo(test_db)
    try:
        tenant = repo.save(Tenant.create(name="Acme Corp"))
        tenant.rename("Acme Global")
        tenant.deactivate()
        repo.save(tenant)

        found = repo.get_by_id(tenant.id.value)
        assert found.name == "Acme Global"
        assert found.is_active is False
        assert repo.count_all() == 1
    finally:
        ctx.__exit__(None, None, None)


def test_duplicate_slug_is_rejected_by_the_database(test_db):
    """The unique index is the real guarantee; application checks race."""
    repo, ctx = _repo(test_db)
    try:
        repo.save(Tenant.create(name="Acme Corp"))
        with pytest.raises(psycopg.errors.UniqueViolation):
            repo.save(Tenant.create(name="Acme Corp", tenant_id=uuid4()))
    finally:
        ctx.__exit__(None, None, None)


def test_listing_is_ordered_and_paginated(test_db):
    repo, ctx = _repo(test_db)
    try:
        for name in ("Alpha", "Beta", "Gamma"):
            repo.save(Tenant.create(name=name))
        assert repo.count_all() == 3
        first_page = repo.list_all(limit=2, offset=0)
        second_page = repo.list_all(limit=2, offset=2)
        assert len(first_page) == 2
        assert len(second_page) == 1
        # No overlap between pages: the ordering is deterministic.
        assert {str(t.id) for t in first_page}.isdisjoint({str(t.id) for t in second_page})
    finally:
        ctx.__exit__(None, None, None)


def test_counts_only_active_agents_of_that_organization(test_db):
    repo, ctx = _repo(test_db)
    try:
        tenant = repo.save(Tenant.create(name="Acme Corp"))
        other = repo.save(Tenant.create(name="Other Corp"))
        with test_db.get_connection(autocommit=True) as conn:
            for email, tid, active in (
                ("a@acme.test", str(tenant.id), 1),
                ("b@acme.test", str(tenant.id), 1),
                ("c@acme.test", str(tenant.id), 0),
                ("d@other.test", str(other.id), 1),
            ):
                conn.execute(
                    "INSERT INTO agents (id, name, email, team, active_leads_count,"
                    " is_active, role, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (str(uuid4()), "X", email, "Sales", 0, active, "AGENT", tid),
                )
        assert repo.count_active_agents(tenant.id.value) == 2
    finally:
        ctx.__exit__(None, None, None)
```

- [ ] **Step 5: Ejecutar y verificar que falla**

Run: `uv run pytest tests/integration/test_raw_sql_tenant_repo.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named '...raw_sql_tenant_repository'`.

- [ ] **Step 6: Implementar el repositorio**

Crear `backend/src/infrastructure/adapters/output/persistence/raw_sql_tenant_repository.py`, siguiendo el mismo estilo que `raw_sql_agent_repository.py`:

```python
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from application.ports.output.tenant_repository_port import TenantRepositoryPort
from domain.entities.tenant import Tenant


class RawSqlTenantRepository(TenantRepositoryPort):
    def __init__(self, connection) -> None:
        self.connection = connection

    def save(self, tenant: Tenant) -> Tenant:
        self.connection.execute(
            """
            INSERT INTO tenants (id, name, slug, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                slug = EXCLUDED.slug,
                is_active = EXCLUDED.is_active
            """,
            (
                str(tenant.id),
                tenant.name,
                tenant.slug,
                1 if tenant.is_active else 0,
                tenant.created_at.isoformat(),
            ),
        )
        return tenant

    def get_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        row = self.connection.execute(
            "SELECT * FROM tenants WHERE id = %s", (str(tenant_id),)
        ).fetchone()
        return self._to_tenant(row) if row else None

    def get_by_slug(self, slug: str) -> Optional[Tenant]:
        row = self.connection.execute(
            "SELECT * FROM tenants WHERE slug = %s", (slug,)
        ).fetchone()
        return self._to_tenant(row) if row else None

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Tenant]:
        # Ordering by id as a tiebreaker keeps pages stable when two rows share
        # a creation timestamp.
        rows = self.connection.execute(
            "SELECT * FROM tenants ORDER BY created_at, id LIMIT %s OFFSET %s",
            (limit, offset),
        ).fetchall()
        return [self._to_tenant(row) for row in rows]

    def count_all(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS count FROM tenants").fetchone()
        return int(row["count"])

    def count_active_agents(self, tenant_id: UUID) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM agents WHERE tenant_id = %s AND is_active = 1",
            (str(tenant_id),),
        ).fetchone()
        return int(row["count"])

    @staticmethod
    def _to_tenant(row) -> Tenant:
        return Tenant.create(
            name=row["name"],
            tenant_id=row["id"],
            slug=row["slug"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
```

- [ ] **Step 7: Incorporar el repositorio al Unit of Work**

En `backend/src/application/ports/output/unit_of_work_port.py`, añadir el atributo:

```python
    tenants: TenantRepositoryPort
```

con su import correspondiente.

En `backend/src/infrastructure/adapters/output/persistence/postgres_unit_of_work.py`, instanciar `RawSqlTenantRepository` sobre la misma conexión que los demás repositorios, de modo que la creación de organización y gestor de la Task 4 sea atómica.

En `backend/tests/unit/mocks/in_memory_uow.py`, añadir el parámetro `tenants` con el mismo patrón que los existentes, de modo que los tests que no lo pasen sigan funcionando.

- [ ] **Step 8: Añadir la tabla al truncado de la suite**

En `backend/tests/conftest.py`, añadir `"tenants"` a la tupla `_TABLES`.

- [ ] **Step 9: Ejecutar**

Run: `uv run pytest tests/integration/test_raw_sql_tenant_repo.py -v`
Expected: PASS, 6 tests.

Run: `uv run pytest tests/architecture/ -q`
Expected: 4 passed.

Run: `uv run pytest -q`
Expected: los mismos fallos que dejó la Task 2, ni uno más.

- [ ] **Step 10: Verificar la migración contra una base limpia**

```bash
docker compose down -v && docker compose up -d db && sleep 12
docker compose up -d --build backend && sleep 20
PGPASSWORD=postgrespassword psql -h localhost -p 5433 -U postgres -d leads_db -c "SELECT name FROM schema_migrations ORDER BY name"
```
Expected: dos filas, `001_baseline_schema.sql` y `002_tenants.sql`.

```bash
PGPASSWORD=postgrespassword psql -h localhost -p 5433 -U postgres -d leads_db -c "\d tenants"
PGPASSWORD=postgrespassword psql -h localhost -p 5433 -U postgres -d leads_db -c "\di idx_agents*"
```
Expected: la tabla y los tres índices.

- [ ] **Step 11: Commit**

```bash
git add backend/migrations/002_tenants.sql backend/src/application/ports/output/ \
        backend/src/infrastructure/adapters/output/persistence/ backend/tests/
git commit -m "feat(persistence): add tenant table, repository and per-tenant email uniqueness"
```

---

## Task 4: Casos de uso de organización

**Files:**
- Create: `backend/src/application/ports/input/tenant_use_case_ports.py`
- Create: `backend/src/application/use_cases/tenant_use_cases.py`
- Modify: `backend/src/application/dtos/commands.py`
- Modify: `backend/src/application/dtos/queries.py`
- Create: `backend/tests/unit/application/test_tenant_use_cases.py`

**Interfaces:**
- Consumes: `TenantRepositoryPort`, `AgentRepositoryPort`, `PasswordHasherPort`, `UnitOfWorkPort`, `AuthorizationPolicy`.
- Produces: `CreateTenantCommand`, `TenantWithManagerResult`, `TenantSummary`, `TenantsPageResult`, `UpdateTenantCommand`, `GetTenantsQuery`; los puertos `CreateTenantInputPort`, `GetTenantsInputPort`, `UpdateTenantInputPort`; y sus implementaciones.

- [ ] **Step 1: Añadir los DTOs**

En `backend/src/application/dtos/commands.py`, añadir:

```python
@dataclass(frozen=True)
class CreateTenantCommand:
    name: str
    manager_name: str
    manager_email: str
    manager_password: str


@dataclass(frozen=True)
class UpdateTenantCommand:
    tenant_id: UUID
    name: Optional[str] = None
    is_active: Optional[bool] = None


@dataclass(frozen=True)
class TenantWithManagerResult:
    tenant: "Tenant"
    manager: "Agent"


@dataclass(frozen=True)
class TenantSummary:
    tenant: "Tenant"
    agent_count: int


@dataclass(frozen=True)
class TenantsPageResult:
    items: List[TenantSummary]
    total: int
```

Añadir `from domain.entities.tenant import Tenant` al bloque `if TYPE_CHECKING:` existente.

En `backend/src/application/dtos/queries.py`:

```python
@dataclass(frozen=True)
class GetTenantsQuery:
    limit: int = 100
    offset: int = 0
```

- [ ] **Step 2: Escribir el test**

Crear `backend/tests/unit/application/test_tenant_use_cases.py`:

```python
from uuid import uuid4

import pytest

from application.dtos.commands import CreateTenantCommand, UpdateTenantCommand
from application.dtos.queries import GetTenantsQuery
from application.use_cases.tenant_use_cases import (
    CreateTenantUseCase,
    GetTenantsUseCase,
    UpdateTenantUseCase,
)
from domain.entities.tenant import Tenant
from domain.exceptions import DomainException
from domain.value_objects.enums import AgentRole
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_tenant_repo import InMemoryTenantRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def _uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(
        InMemoryLeadRepository(),
        InMemoryRuleRepository(),
        InMemoryAgentRepository(),
        tenants=InMemoryTenantRepository(),
    )


def _command(name: str = "Acme Corp", email: str = "ana@acme.test") -> CreateTenantCommand:
    return CreateTenantCommand(
        name=name,
        manager_name="Ana Ruiz",
        manager_email=email,
        manager_password="s3cret",
    )


class TestCreateTenant:
    def test_creates_the_organization_and_its_manager(self):
        uow = _uow()
        result = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            _command()
        )
        assert result.tenant.name == "Acme Corp"
        assert result.tenant.slug == "acme-corp"
        assert result.manager.role == AgentRole.MANAGER

    def test_the_manager_belongs_to_the_new_organization(self):
        uow = _uow()
        result = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            _command()
        )
        assert str(result.manager.tenant_id) == str(result.tenant.id)

    def test_the_manager_password_is_hashed(self):
        uow = _uow()
        result = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            _command()
        )
        assert result.manager.hashed_password == "hashed:s3cret"

    def test_rejects_a_duplicate_organization_name(self):
        uow = _uow()
        use_case = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher())
        use_case.execute(_command())
        with pytest.raises(DomainException):
            use_case.execute(_command(email="otra@acme.test"))

    def test_rejects_an_email_already_in_use(self):
        uow = _uow()
        use_case = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher())
        use_case.execute(_command())
        with pytest.raises(DomainException):
            use_case.execute(_command(name="Other Corp"))

    def test_a_rejected_creation_leaves_no_organization_behind(self):
        """Both writes share one transaction: a failed manager must not leave an
        unreachable organization."""
        uow = _uow()
        use_case = CreateTenantUseCase(uow=uow, password_hasher=FakePasswordHasher())
        use_case.execute(_command())
        with pytest.raises(DomainException):
            use_case.execute(_command(name="Other Corp"))
        assert uow.tenants.count_all() == 1


class TestGetTenants:
    def test_returns_each_organization_with_its_agent_count(self):
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        uow.tenants.set_agent_count(tenant.id.value, 4)

        page = GetTenantsUseCase(uow=uow).execute(GetTenantsQuery())

        assert page.total == 1
        assert page.items[0].tenant.name == "Acme Corp"
        assert page.items[0].agent_count == 4

    def test_paginates(self):
        uow = _uow()
        for name in ("Alpha", "Beta", "Gamma"):
            uow.tenants.save(Tenant.create(name=name))
        page = GetTenantsUseCase(uow=uow).execute(GetTenantsQuery(limit=2, offset=0))
        assert page.total == 3
        assert len(page.items) == 2


class TestUpdateTenant:
    def test_renames(self):
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        updated = UpdateTenantUseCase(uow=uow).execute(
            UpdateTenantCommand(tenant_id=tenant.id.value, name="Acme Global")
        )
        assert updated.name == "Acme Global"

    def test_renaming_keeps_the_slug(self):
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        updated = UpdateTenantUseCase(uow=uow).execute(
            UpdateTenantCommand(tenant_id=tenant.id.value, name="Acme Global")
        )
        assert updated.slug == "acme-corp"

    def test_deactivating_also_deactivates_its_users(self):
        """A valid credential of a suspended organization must stop working."""
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme Corp"))
        from domain.entities.agent import Agent

        agent = uow.agents.save(
            Agent.create(
                "Ana", "ana@acme.test", "Sales", role=AgentRole.MANAGER, tenant_id=tenant.id.value
            )
        )
        UpdateTenantUseCase(uow=uow).execute(
            UpdateTenantCommand(tenant_id=tenant.id.value, is_active=False)
        )
        assert uow.agents.get_by_id(agent.id.value).is_active is False

    def test_unknown_organization_raises(self):
        uow = _uow()
        with pytest.raises(DomainException):
            UpdateTenantUseCase(uow=uow).execute(UpdateTenantCommand(tenant_id=uuid4(), name="X"))
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/application/test_tenant_use_cases.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'application.use_cases.tenant_use_cases'`.

- [ ] **Step 4: Definir los puertos de entrada**

Crear `backend/src/application/ports/input/tenant_use_case_ports.py` con tres ABC: `CreateTenantInputPort.execute(command: CreateTenantCommand) -> TenantWithManagerResult`, `GetTenantsInputPort.execute(query: GetTenantsQuery) -> TenantsPageResult`, `UpdateTenantInputPort.execute(command: UpdateTenantCommand) -> Tenant`.

- [ ] **Step 5: Implementar los casos de uso**

Crear `backend/src/application/use_cases/tenant_use_cases.py`:

```python
from application.dtos.commands import (
    CreateTenantCommand,
    TenantSummary,
    TenantWithManagerResult,
    TenantsPageResult,
    UpdateTenantCommand,
)
from application.dtos.queries import GetTenantsQuery
from application.ports.input.tenant_use_case_ports import (
    CreateTenantInputPort,
    GetTenantsInputPort,
    UpdateTenantInputPort,
)
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.agent import Agent
from domain.entities.tenant import Tenant, slugify
from domain.exceptions import DomainException
from domain.value_objects.enums import AgentRole


class CreateTenantUseCase(CreateTenantInputPort):
    """Creates an organization together with its first manager.

    Both writes share one transaction: an organization nobody can log into is
    not a useful intermediate state."""

    def __init__(self, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort) -> None:
        self.uow = uow
        self.password_hasher = password_hasher

    def execute(self, command: CreateTenantCommand) -> TenantWithManagerResult:
        with self.uow:
            if self.uow.tenants.get_by_slug(slugify(command.name)):
                raise DomainException(
                    "Ya existe una organización con ese nombre",
                    error_code="TENANT_ALREADY_EXISTS",
                )
            if self.uow.agents.get_by_email(command.manager_email):
                raise DomainException(
                    "Ya existe un usuario con ese correo electrónico",
                    error_code="EMAIL_ALREADY_EXISTS",
                )

            tenant = self.uow.tenants.save(Tenant.create(name=command.name))
            manager = self.uow.agents.save(
                Agent.create(
                    name=command.manager_name,
                    email=command.manager_email,
                    team="Management",
                    role=AgentRole.MANAGER,
                    hashed_password=self.password_hasher.hash(command.manager_password),
                    tenant_id=tenant.id,
                )
            )
        return TenantWithManagerResult(tenant=tenant, manager=manager)


class GetTenantsUseCase(GetTenantsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetTenantsQuery) -> TenantsPageResult:
        with self.uow:
            tenants = self.uow.tenants.list_all(limit=query.limit, offset=query.offset)
            total = self.uow.tenants.count_all()
            items = [
                TenantSummary(
                    tenant=tenant,
                    agent_count=self.uow.tenants.count_active_agents(tenant.id.value),
                )
                for tenant in tenants
            ]
        return TenantsPageResult(items=items, total=total)


class UpdateTenantUseCase(UpdateTenantInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: UpdateTenantCommand) -> Tenant:
        with self.uow:
            tenant = self.uow.tenants.get_by_id(command.tenant_id)
            if tenant is None:
                raise DomainException(
                    "La organización no existe", error_code="TENANT_NOT_FOUND"
                )

            if command.name is not None:
                tenant.rename(command.name)

            if command.is_active is not None:
                if command.is_active:
                    tenant.activate()
                else:
                    tenant.deactivate()
                    # A suspended organization must not leave working credentials
                    # behind, so its users are deactivated with it.
                    self.uow.agents.deactivate_all_by_tenant(command.tenant_id)

            self.uow.tenants.save(tenant)
        return tenant
```

`deactivate_all_by_tenant` es un método que introduce la Task 5 en `AgentRepositoryPort`. Si esta tarea se ejecuta antes, añádelo primero al puerto y a sus dos implementaciones. Una sola sentencia, no un bucle paginado: cualquier tamaño de página sería un techo silencioso sobre la garantía de que suspender una organización no deja credenciales operativas.

- [ ] **Step 6: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/application/test_tenant_use_cases.py -v`
Expected: PASS, 13 tests.

Run: `uv run pytest tests/architecture/ -q`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/src/application/ backend/tests/unit/application/test_tenant_use_cases.py
git commit -m "feat(application): add tenant use cases with atomic organization and manager creation"
```

---

## Task 5: Filtro de organización en el repositorio de asesores

Cierra la fuga descrita en la sección 2 del spec, en la capa donde se origina.

**Files:**
- Modify: `backend/src/application/ports/output/agent_repository_port.py`
- Modify: `backend/src/infrastructure/adapters/output/persistence/raw_sql_agent_repository.py`
- Modify: `backend/tests/unit/mocks/in_memory_agent_repo.py`
- Modify: `backend/src/application/use_cases/agent_use_cases.py`
- Modify: `backend/src/application/dtos/queries.py`
- Create: `backend/tests/integration/test_agent_repo_tenant_scoping.py`

**Interfaces:**
- Produces: `AgentRepositoryPort.list_by_tenant(tenant_id, team=None, limit=100, offset=0)`, `count_by_tenant(tenant_id, team=None)`, `get_by_id_and_tenant(agent_id, tenant_id)`, `deactivate_all_by_tenant(tenant_id) -> int`, `distinct_tenant_ids() -> List[UUID]`. `GetAgentsQuery` y `GetAgentQuery` ganan `tenant_id: UUID`.

- [ ] **Step 1: Escribir el test de aislamiento**

Crear `backend/tests/integration/test_agent_repo_tenant_scoping.py`:

```python
from uuid import uuid4

from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import (
    RawSqlAgentRepository,
)

_TENANT_A = uuid4()
_TENANT_B = uuid4()


def _seed(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    repo = RawSqlAgentRepository(conn)
    repo.save(Agent.create("A One", "a1@a.test", "Sales", role=AgentRole.AGENT, tenant_id=_TENANT_A))
    repo.save(Agent.create("A Two", "a2@a.test", "Sales", role=AgentRole.AGENT, tenant_id=_TENANT_A))
    b = repo.save(
        Agent.create("B One", "b1@b.test", "Sales", role=AgentRole.AGENT, tenant_id=_TENANT_B)
    )
    return repo, ctx, b


def test_listing_returns_only_the_requested_organization(test_db):
    """The regression test for the cross-tenant leak: before this change any
    authenticated user could enumerate every organization's agents."""
    repo, ctx, _ = _seed(test_db)
    try:
        found = repo.list_by_tenant(_TENANT_A)
        assert len(found) == 2
        assert {a.email for a in found} == {"a1@a.test", "a2@a.test"}
    finally:
        ctx.__exit__(None, None, None)


def test_counting_is_scoped_too(test_db):
    repo, ctx, _ = _seed(test_db)
    try:
        assert repo.count_by_tenant(_TENANT_A) == 2
        assert repo.count_by_tenant(_TENANT_B) == 1
    finally:
        ctx.__exit__(None, None, None)


def test_reading_an_agent_of_another_organization_returns_nothing(test_db):
    repo, ctx, b_agent = _seed(test_db)
    try:
        assert repo.get_by_id_and_tenant(b_agent.id.value, _TENANT_B) is not None
        assert repo.get_by_id_and_tenant(b_agent.id.value, _TENANT_A) is None
    finally:
        ctx.__exit__(None, None, None)


def test_team_filter_composes_with_the_organization_filter(test_db):
    repo, ctx, _ = _seed(test_db)
    try:
        repo.save(
            Agent.create("A Three", "a3@a.test", "Support", role=AgentRole.AGENT, tenant_id=_TENANT_A)
        )
        assert len(repo.list_by_tenant(_TENANT_A, team="Sales")) == 2
        assert len(repo.list_by_tenant(_TENANT_A, team="Support")) == 1
        assert repo.count_by_tenant(_TENANT_A, team="Support") == 1
    finally:
        ctx.__exit__(None, None, None)


def test_listing_is_deterministically_ordered(test_db):
    repo, ctx, _ = _seed(test_db)
    try:
        assert [a.email for a in repo.list_by_tenant(_TENANT_A)] == [
            a.email for a in repo.list_by_tenant(_TENANT_A)
        ]
    finally:
        ctx.__exit__(None, None, None)
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/integration/test_agent_repo_tenant_scoping.py -v`
Expected: FAIL con `AttributeError: 'RawSqlAgentRepository' object has no attribute 'list_by_tenant'`.

- [ ] **Step 3: Ampliar el puerto**

En `backend/src/application/ports/output/agent_repository_port.py`, añadir tres métodos abstractos:

```python
    @abc.abstractmethod
    def list_by_tenant(
        self,
        tenant_id: UUID,
        team: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Agent]:
        """Return a page of active agents of this organization."""

    @abc.abstractmethod
    def count_by_tenant(self, tenant_id: UUID, team: Optional[str] = None) -> int:
        """Return how many active agents this organization has."""

    @abc.abstractmethod
    def get_by_id_and_tenant(self, agent_id: UUID, tenant_id: UUID) -> Optional[Agent]:
        """Return the agent only when it belongs to this organization.

        Returning None for an agent of another organization is deliberate: a
        403 would confirm that the identifier exists."""

    @abc.abstractmethod
    def distinct_tenant_ids(self) -> List[UUID]:
        """Return every organization identifier referenced by an agent.

        Used by the backfill command of Task 7; declared here so the port is
        modified once instead of twice."""
```

Los métodos sin organización (`list_active`, `count_active`, `get_by_id`) **se conservan**: los usan la resolución de identidad desde el token y la comprobación de bootstrap, donde el llamante todavía no tiene organización.

- [ ] **Step 4: Implementar en el adaptador SQL**

En `raw_sql_agent_repository.py`:

```python
    def list_by_tenant(
        self,
        tenant_id: UUID,
        team: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Agent]:
        sql = "SELECT * FROM agents WHERE tenant_id = %s AND is_active = 1"
        params: list = [str(tenant_id)]
        if team:
            sql += " AND team = %s"
            params.append(team)
        # Explicit ordering: without it a page can repeat or skip rows.
        sql += " ORDER BY name, id LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        rows = self.connection.execute(sql, tuple(params)).fetchall()
        return [self._row_to_agent(row) for row in rows]

    def count_by_tenant(self, tenant_id: UUID, team: Optional[str] = None) -> int:
        sql = "SELECT COUNT(*) AS count FROM agents WHERE tenant_id = %s AND is_active = 1"
        params: list = [str(tenant_id)]
        if team:
            sql += " AND team = %s"
            params.append(team)
        row = self.connection.execute(sql, tuple(params)).fetchone()
        return int(row["count"])

    def get_by_id_and_tenant(self, agent_id: UUID, tenant_id: UUID) -> Optional[Agent]:
        row = self.connection.execute(
            "SELECT * FROM agents WHERE id = %s AND tenant_id = %s",
            (str(agent_id), str(tenant_id)),
        ).fetchone()
        return self._row_to_agent(row) if row else None
```

Usa el nombre real del método de conversión de fila que ya exista en el fichero, en lugar de `_row_to_agent` si difiere.

Replica los tres métodos en `backend/tests/unit/mocks/in_memory_agent_repo.py` con la misma semántica.

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/integration/test_agent_repo_tenant_scoping.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 6: Propagar a los casos de uso**

En `backend/src/application/dtos/queries.py`, añadir `tenant_id: UUID` como primer campo de `GetAgentsQuery` y de `GetAgentQuery`.

En `backend/src/application/use_cases/agent_use_cases.py`:
- `GetAgentsUseCase` pasa a `list_by_tenant(query.tenant_id, team=query.team, ...)` y `count_by_tenant(query.tenant_id, team=query.team)`.
- `GetAgentUseCase` pasa a `get_by_id_and_tenant(query.agent_id, query.tenant_id)` y sigue lanzando `AgentNotFoundException` cuando devuelve `None`.
- `CreateAgentUseCase` no cambia.

- [ ] **Step 7: Ejecutar**

Run: `uv run pytest tests/architecture/ -q`
Expected: 4 passed.

Run: `uv run pytest -q`
Expected: los fallos que quedan son sólo los de los routers, que la Task 6 arregla. Los tests unitarios de casos de uso de agentes deben estar en verde tras ajustar sus consultas.

- [ ] **Step 8: Commit**

```bash
git add backend/src/application/ backend/src/infrastructure/adapters/output/persistence/raw_sql_agent_repository.py backend/tests/
git commit -m "fix(persistence): scope every agent query by organization

Closes the last cross-tenant leak: any authenticated user could enumerate and
read the agents of every organization."
```

---

## Task 6: Adaptadores HTTP de los dos planos

**Files:**
- Create: `backend/src/infrastructure/adapters/input/api/tenant_router.py`
- Modify: `backend/src/infrastructure/adapters/input/api/agent_router.py`
- Modify: `backend/src/infrastructure/adapters/input/api/auth_router.py`
- Modify: `backend/src/infrastructure/adapters/input/api/schemas.py`
- Modify: `backend/src/infrastructure/adapters/input/api/dependencies.py`
- Modify: `backend/src/infrastructure/main.py`
- Modify: `backend/src/infrastructure/di/container.py`
- Modify: los tests e2e afectados
- Create: `backend/tests/e2e/test_plane_separation_e2e.py`

**Interfaces:**
- Consumes: los casos de uso de la Task 4, el repositorio de la Task 5, `AuthorizationPolicy` de la Task 2.
- Produces: `require_platform_admin(context) -> RequestContext`, `require_organization_manager` ya existente con la semántica nueva, y los endpoints de la sección 7 del spec.

- [ ] **Step 1: Escribir el test extremo a extremo**

Crear `backend/tests/e2e/test_plane_separation_e2e.py`:

```python
import os
import uuid

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5433/leads_test"
)

from fastapi.testclient import TestClient

from infrastructure.main import app


def _bootstrap_admin(client: TestClient) -> str:
    response = client.post(
        "/api/v1/agents",
        json={
            "name": "Platform Admin",
            "email": f"admin_{uuid.uuid4().hex[:6]}@platform.test",
            "team": "HQ",
            "password": "admin-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "ADMIN"
    login = client.post(
        "/api/v1/auth/login",
        data={"username": response.json()["email"], "password": "admin-pass-123"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _create_tenant(client: TestClient, admin_token: str, name: str, email: str) -> dict:
    response = client.post(
        "/api/v1/tenants",
        json={
            "name": name,
            "manager": {"name": "Manager", "email": email, "password": "manager-pass-123"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_platform_admin_creates_organizations_but_reaches_no_data():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        created = _create_tenant(client, admin_token, "Acme Corp", "ana@acme.test")
        assert created["slug"] == "acme-corp"
        assert created["manager"]["role"] == "MANAGER"

        listed = client.get("/api/v1/tenants", headers=admin_headers)
        assert listed.status_code == 200
        assert listed.json()["total"] >= 1

        # The whole point of the phase: the platform plane reaches no data.
        assert client.get("/api/v1/leads", headers=admin_headers).status_code == 403
        assert client.get("/api/v1/agents", headers=admin_headers).status_code == 403
        assert client.get("/api/v1/rules/scoring", headers=admin_headers).status_code == 403


def test_manager_works_inside_its_organization_only():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        _create_tenant(client, admin_token, "Acme Corp", "ana@acme.test")
        _create_tenant(client, admin_token, "Other Corp", "bob@other.test")

        ana = {"Authorization": f"Bearer {_login(client, 'ana@acme.test', 'manager-pass-123')}"}

        assert client.get("/api/v1/leads", headers=ana).status_code == 200
        assert client.post("/api/v1/tenants", json={}, headers=ana).status_code == 403

        # The regression test for the cross-tenant leak: Ana sees her own
        # organization's agents and nobody else's.
        agents = client.get("/api/v1/agents", headers=ana)
        assert agents.status_code == 200
        emails = {item["email"] for item in agents.json()["items"]}
        assert emails == {"ana@acme.test"}


def test_sales_agent_cannot_list_agents_but_knows_who_it_is():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        _create_tenant(client, admin_token, "Acme Corp", "ana@acme.test")
        ana = {"Authorization": f"Bearer {_login(client, 'ana@acme.test', 'manager-pass-123')}"}

        created = client.post(
            "/api/v1/agents",
            json={
                "name": "Sales Person",
                "email": "sales@acme.test",
                "team": "Sales",
                "password": "sales-pass-123",
                "role": "AGENT",
            },
            headers=ana,
        )
        assert created.status_code == 201
        assert created.json()["tenant_id"] is not None

        sales = {"Authorization": f"Bearer {_login(client, 'sales@acme.test', 'sales-pass-123')}"}
        assert client.get("/api/v1/agents", headers=sales).status_code == 403

        me = client.get("/api/v1/auth/me", headers=sales)
        assert me.status_code == 200
        assert me.json()["role"] == "AGENT"
        assert me.json()["email"] == "sales@acme.test"
        assert me.json()["tenant_name"] == "Acme Corp"


def test_identity_of_the_platform_admin_has_no_organization():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert me.status_code == 200
        assert me.json()["role"] == "ADMIN"
        assert me.json()["tenant_id"] is None
        assert me.json()["tenant_name"] is None


def test_deactivating_an_organization_locks_its_users_out():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        created = _create_tenant(client, admin_token, "Acme Corp", "ana@acme.test")

        assert _login(client, "ana@acme.test", "manager-pass-123")

        patched = client.patch(
            f"/api/v1/tenants/{created['id']}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert patched.status_code == 200
        assert patched.json()["is_active"] is False

        denied = client.post(
            "/api/v1/auth/login",
            data={"username": "ana@acme.test", "password": "manager-pass-123"},
        )
        assert denied.status_code == 401


def test_creating_a_tenant_with_a_taken_email_leaves_nothing_behind():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        _create_tenant(client, admin_token, "Acme Corp", "ana@acme.test")

        before = client.get("/api/v1/tenants", headers=admin_headers).json()["total"]
        clash = client.post(
            "/api/v1/tenants",
            json={
                "name": "Third Corp",
                "manager": {"name": "X", "email": "ana@acme.test", "password": "p"},
            },
            headers=admin_headers,
        )
        assert clash.status_code == 400
        after = client.get("/api/v1/tenants", headers=admin_headers).json()["total"]
        assert after == before
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/e2e/test_plane_separation_e2e.py -v`
Expected: FAIL con 404 en `/api/v1/tenants` y en `/api/v1/auth/me`, que aún no existen.

- [ ] **Step 3: Añadir los esquemas**

En `schemas.py`, añadir `TenantManagerCreate` (`name`, `email`, `password`), `TenantCreate` (`name`, `manager: TenantManagerCreate`), `TenantUpdate` (`name: Optional[str]`, `is_active: Optional[bool]`), `TenantResponse` (`id`, `name`, `slug`, `is_active`, `created_at`, `agent_count: Optional[int]`, `manager: Optional[AgentResponse]`), `PaginatedTenantsResponse` y `CurrentUserResponse` (`id`, `name`, `email`, `role`, `tenant_id: Optional[str]`, `tenant_name: Optional[str]`).

**`AgentCreate` pierde el campo `tenant_id`**: pasa a tomarse del contexto.

- [ ] **Step 4: Añadir la dependencia de plataforma**

En `dependencies.py`, después de `require_organization_manager`:

```python
def require_platform_admin(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    AuthorizationPolicy.ensure_can_manage_platform(context.actor)
    return context
```

Y las factories de los tres casos de uso de organización, tomando `password_hasher` del contenedor.

- [ ] **Step 5: Escribir el router de plataforma**

Crear `tenant_router.py` con los tres endpoints de la sección 7.1 del spec, todos con `Depends(require_platform_admin)`, y mapeo explícito de entidad a esquema como en el resto de routers.

- [ ] **Step 6: Añadir `/auth/me`**

En `auth_router.py`, un `GET /me` que use `get_request_context` y resuelva `tenant_name` consultando el repositorio de organizaciones cuando `context.tenant_id` no sea nulo.

- [ ] **Step 7: Ajustar el router de asesores**

- `create_agent`: el bootstrap no cambia. Fuera de él, exige `MANAGER` vía `AuthorizationPolicy.ensure_can_create_agent_with_role`, y el `tenant_id` del comando sale de `context.tenant_id`, nunca del cuerpo.
- `list_agents`: `Depends(require_organization_manager)` y `GetAgentsQuery(tenant_id=context.tenant_id, ...)`.
- `get_agent`: igual, con `GetAgentQuery(agent_id=..., tenant_id=context.tenant_id)`.

- [ ] **Step 8: Registrar el router**

En `main.py`: `app.include_router(tenant_router, prefix="/api/v1/tenants", tags=["Platform"])`.

- [ ] **Step 9: Migrar los tests e2e que autenticaban como ADMIN**

Los tests que la Task 2 dejó en rojo deben pasar a autenticar con un `MANAGER` creado a través de `POST /api/v1/tenants`. Búscalos con `rg -n "AgentRole.ADMIN|role=\"ADMIN\"" tests/e2e`.

- [ ] **Step 10: Ejecutar todo**

```bash
uv run pytest tests/e2e/test_plane_separation_e2e.py -v
uv run pytest -q
uv run pytest tests/architecture/ -q
env -u DATABASE_URL -u TEST_DATABASE_URL -u JWT_SECRET uv run pytest -m unit -q
```
Expected: todo en verde.

- [ ] **Step 11: Validar contra contenedores**

```bash
docker compose down -v && docker compose up -d --build && sleep 25
docker compose ps
docker compose logs backend | tail -30
```

Y con `curl` sobre el puerto 8001, comprobando el código de estado de cada paso:

1. Bootstrap del administrador → 201 con `role: "ADMIN"`
2. Login del administrador → 200 con token
3. `POST /api/v1/tenants` con nombre y gestor → 201, con `slug` y `manager`
4. `GET /api/v1/tenants` con el token del administrador → 200 y `agent_count` presente
5. `GET /api/v1/leads` con el token del administrador → **403**
6. `GET /api/v1/agents` con el token del administrador → **403**
7. Login del gestor → 200
8. `GET /api/v1/agents` con el token del gestor → 200, y **sólo** su organización
9. `GET /api/v1/auth/me` con cada token → identidad correcta en ambos casos
10. `PATCH /api/v1/tenants/{id}` con `is_active: false` → 200, y el login del gestor pasa a **401**

Y en base de datos:
```bash
PGPASSWORD=postgrespassword psql -h localhost -p 5433 -U postgres -d leads_db -c "SELECT id, name, slug, is_active FROM tenants"
PGPASSWORD=postgrespassword psql -h localhost -p 5433 -U postgres -d leads_db -c "SELECT email, role, tenant_id, is_active FROM agents ORDER BY role"
```

Copia la salida literal de todo en el informe.

- [ ] **Step 12: Commit**

```bash
git add backend/src/infrastructure/ backend/tests/
git commit -m "feat(api): add the platform plane and scope every agent endpoint by organization"
```

---

## Task 7: Sincronización de datos previos y documentación

**Files:**
- Create: `backend/src/infrastructure/cli/__init__.py`
- Create: `backend/src/infrastructure/cli/sync_tenants.py`
- Modify: `docs/api/endpoints.md`
- Modify: `docs/specs/2026-08-07-lead-router-mvp-design.md` (matriz de permisos)
- Create: `backend/tests/integration/test_sync_tenants.py`

**Interfaces:**
- Produces: `sync_tenants(uow) -> list[str]`, que devuelve los slugs creados.

- [ ] **Step 1: Escribir el test**

Crear `backend/tests/integration/test_sync_tenants.py`:

```python
from uuid import uuid4

from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.cli.sync_tenants import sync_tenants


def test_creates_one_organization_per_orphan_tenant_id(test_db):
    orphan_a, orphan_b = uuid4(), uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        for email, tid in (("a@x.test", orphan_a), ("b@x.test", orphan_a), ("c@y.test", orphan_b)):
            conn.execute(
                "INSERT INTO agents (id, name, email, team, active_leads_count,"
                " is_active, role, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (str(uuid4()), "X", email, "Sales", 0, 1, "AGENT", str(tid)),
            )

    created = sync_tenants(PostgresUnitOfWork(test_db))

    assert len(created) == 2
    with PostgresUnitOfWork(test_db) as uow:
        assert uow.tenants.get_by_id(orphan_a) is not None
        assert uow.tenants.get_by_id(orphan_b) is not None


def test_is_idempotent(test_db):
    orphan = uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(
            "INSERT INTO agents (id, name, email, team, active_leads_count,"
            " is_active, role, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (str(uuid4()), "X", "a@x.test", "Sales", 0, 1, "AGENT", str(orphan)),
        )

    assert len(sync_tenants(PostgresUnitOfWork(test_db))) == 1
    assert sync_tenants(PostgresUnitOfWork(test_db)) == []


def test_ignores_the_platform_admin(test_db):
    """The platform administrator has no organization by design; it must not
    produce a phantom one."""
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(
            "INSERT INTO agents (id, name, email, team, active_leads_count,"
            " is_active, role, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,NULL)",
            (str(uuid4()), "Admin", "admin@p.test", "HQ", 0, 1, AgentRole.ADMIN.value),
        )
    assert sync_tenants(PostgresUnitOfWork(test_db)) == []
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/integration/test_sync_tenants.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'infrastructure.cli'`.

- [ ] **Step 3: Implementar el comando**

Crear `backend/src/infrastructure/cli/__init__.py` vacío y `sync_tenants.py`:

```python
"""Backfills the tenants table for databases that predate it.

Organization identifiers used to circulate with no row backing them. This
creates one organization per distinct identifier still referenced by an agent,
so the data becomes consistent without discarding it. Run by hand, never at
startup: it is a one-off repair, not part of the boot sequence."""

from typing import List

from domain.entities.tenant import Tenant


def sync_tenants(uow) -> List[str]:
    created: List[str] = []
    with uow:
        rows = uow.agents.distinct_tenant_ids()
        for tenant_id in rows:
            if uow.tenants.get_by_id(tenant_id) is not None:
                continue
            short = str(tenant_id)[:8]
            # The identifier is preserved: existing agents already reference it.
            uow.tenants.save(
                Tenant.create(name=f"Organización {short}", tenant_id=tenant_id)
            )
            created.append(short)
    return created


if __name__ == "__main__":
    from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    from infrastructure.config.settings import Settings

    settings = Settings.from_environment()
    database = RawSqlDatabase(dsn=settings.database_url)
    for slug in sync_tenants(PostgresUnitOfWork(database)):
        print(f"created organization for {slug}")
    database.close()
```

`distinct_tenant_ids()` ya se declaró en el puerto en la Task 5. Si sus implementaciones quedaron pendientes, el SQL es:

```sql
SELECT DISTINCT tenant_id FROM agents WHERE tenant_id IS NOT NULL
```

- [ ] **Step 4: Ejecutar**

Run: `uv run pytest tests/integration/test_sync_tenants.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Actualizar la documentación**

En `docs/api/endpoints.md`: añadir la sección del plano de plataforma con los tres endpoints y `GET /auth/me`; corregir los de asesores para reflejar que exigen `MANAGER` y están acotados a la organización; retirar `tenant_id` del cuerpo de `AgentCreate`.

En `docs/specs/2026-08-07-lead-router-mvp-design.md`, sustituir la matriz de permisos de la sección 9.2 por la de la sección 6.2 del spec de esta fase, y añadir bajo el hueco de diseño una nota indicando que quedó resuelto en F0.5 con la separación de planos.

- [ ] **Step 6: Verificación final de fase**

```bash
uv run pytest -q
uv run pytest tests/architecture/ -q
env -u DATABASE_URL -u TEST_DATABASE_URL -u JWT_SECRET uv run pytest -m unit -q
docker compose down -v && docker compose up -d --build && sleep 25
docker compose ps
docker compose --profile test run --rm backend-test
```

Todo debe quedar en verde y los tres servicios levantados.

- [ ] **Step 7: Commit**

```bash
git add backend/src/infrastructure/cli/ backend/tests/integration/test_sync_tenants.py docs/
git commit -m "feat(cli): add tenant backfill command and update the permission documentation"
```

---

## Criterio de aceptación de F0.5

- [ ] Guardián de arquitectura en 4/4.
- [ ] `pytest -m unit` en verde sin base de datos ni variables de entorno.
- [ ] Un `ADMIN` recibe 403 en `/leads`, `/agents` y `/rules/*`, verificado con `curl`.
- [ ] Un `MANAGER` lista únicamente los asesores de su organización, verificado con dos organizaciones reales.
- [ ] Un `AGENT` recibe 403 al listar asesores y obtiene su identidad por `/auth/me`.
- [ ] Crear una organización con un correo ya usado no deja la organización creada.
- [ ] Desactivar una organización impide el acceso de sus usuarios.
- [ ] El sistema arranca desde volumen vacío y aplica las dos migraciones.

## Notas para quien ejecute el plan

**Orden.** Las tareas 1 y 2 son independientes entre sí pero ambas preceden al resto. La 3 antes que la 4. La 5 antes que la 6. La 7 al final.

**La Task 2 deja tests en rojo a propósito** y no se arreglan hasta la Task 6. Es la consecuencia esperada de retirar un privilegio: los tests que se apoyaban en él dejan de pasar. Si los fallos superan los seis, el diagnóstico de partida era incorrecto y hay que revisarlo antes de seguir.

**Criterio de parada.** Si un paso "verificar que falla" produce un fallo distinto del descrito, detenerse y reportar.
