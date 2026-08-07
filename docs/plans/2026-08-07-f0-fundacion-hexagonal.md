# F0 — Fundación Hexagonal: Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establecer las fronteras arquitectónicas del backend —regla de dependencias efectiva, inversión de dependencias real, infraestructura de pruebas y arranque reproducible— para que las fases funcionales posteriores se construyan encima sin reescribirlas.

**Architecture:** Se invierten las tres dependencias que hoy apuntan de `application/` hacia `infrastructure/` mediante puertos abstractos (hashing, tokens, reloj, identificadores). Se extraen las decisiones de negocio que viven en los routers de FastAPI hacia políticas de dominio. Se centraliza la construcción del grafo de objetos en un composition root explícito, y el tenant deja de viajar en la URL para derivarse del token. Un test de arquitectura que analiza el árbol sintáctico de cada módulo impide la regresión.

**Tech Stack:** Python 3.12+, FastAPI, psycopg 3 (raw SQL, sin ORM), PyJWT, passlib/bcrypt, pytest, uv, PostgreSQL 16, Docker Compose.

## Global Constraints

- Todo el código fuente, nombres, docstrings y comentarios en **inglés**. La prosa de documentación en español.
- **Prohibido cualquier ORM** (SQLAlchemy, Tortoise, Peewee). La persistencia es SQL parametrizado sobre `psycopg` 3, que usa marcadores `%s`.
- `domain/` no importa **nada** fuera de la biblioteca estándar de Python.
- `application/` importa sólo de `domain/` y de la biblioteca estándar. **Nunca** de `infrastructure/`.
- Los puertos son clases abstractas `abc.ABC` con métodos `@abc.abstractmethod`.
- Los DTOs de `application/` son `@dataclass(frozen=True)`. Pydantic sólo existe en `infrastructure/adapters/input/api/`.
- `pytest -m unit` debe pasar **sin base de datos, sin red y sin variables de entorno**, en todo momento.
- Los comentarios explican el **porqué**, nunca el qué. Sin comentarios obvios.
- Mensajes de commit en inglés con formato `type(scope): description`. **Sin** `Co-authored-by`.
- No ejecutar `git push` ni abrir ramas nuevas sin petición explícita.
- Directorio de trabajo del backend: `backend/`. Los comandos se ejecutan desde ahí salvo indicación contraria.

## Mapa de ficheros

**Se crean:**

| Fichero | Responsabilidad |
|---|---|
| `backend/conftest.py` | Hace `tests` importable de forma explícita, sin depender de la instalación editable |
| `backend/tests/conftest.py` | Marcado automático por ruta, fixtures de base de datos de prueba |
| `backend/tests/architecture/test_dependency_rule.py` | Guardián de la regla de dependencias |
| `backend/src/application/ports/output/password_hasher_port.py` | Contrato de hashing |
| `backend/src/application/ports/output/token_service_port.py` | Contrato de emisión y verificación de tokens |
| `backend/src/application/ports/output/clock_port.py` | Contrato de reloj |
| `backend/src/application/ports/output/id_generator_port.py` | Contrato de generación de identificadores |
| `backend/src/infrastructure/adapters/output/security/bcrypt_password_hasher.py` | Adaptador bcrypt |
| `backend/src/infrastructure/adapters/output/security/jwt_token_service.py` | Adaptador PyJWT |
| `backend/src/infrastructure/adapters/output/system_clock.py` | Adaptador de reloj del sistema |
| `backend/src/infrastructure/adapters/output/uuid_generator.py` | Adaptador de UUID4 |
| `backend/src/domain/policies/authorization_policy.py` | Quién puede hacer qué |
| `backend/src/application/dtos/context.py` | `RequestContext` |
| `backend/src/infrastructure/config/settings.py` | Configuración centralizada |
| `backend/src/infrastructure/di/container.py` | Composition root |
| `backend/src/infrastructure/logging_config.py` | Configuración de logging |
| `backend/migrations/001_baseline_schema.sql` | Esquema base versionado |
| `backend/src/infrastructure/adapters/output/persistence/migration_runner.py` | Aplicador de migraciones |
| `backend/tests/unit/mocks/fake_password_hasher.py` | Doble de hashing |
| `backend/tests/unit/mocks/fake_token_service.py` | Doble de tokens |
| `backend/tests/unit/mocks/frozen_clock.py` | Doble de reloj |
| `backend/.dockerignore`, `frontend/.dockerignore` | Contexto de build limpio |
| `backend/.env.example` | Variables documentadas |

**Se modifican:** `domain/exceptions.py`, `application/dtos/commands.py`, `application/dtos/queries.py`, `application/use_cases/auth_use_cases.py`, `application/use_cases/agent_use_cases.py`, `application/ports/input/auth_use_case_port.py`, los cuatro routers, `dependencies.py`, `exception_handlers.py`, `main.py`, `connection.py`, `pyproject.toml`, `docker-compose.yml`, ambos `Dockerfile`.

**Se eliminan:** `infrastructure/security/jwt_service.py`, `infrastructure/security/password_hasher.py` (sustituidos por los adaptadores).

---

## Task 1: Infraestructura de pruebas

Todo lo demás se apoya en poder ejecutar tests de forma selectiva y reproducible. Hoy no hay `conftest.py`, no hay marcadores, y `uv run pytest` falla en 12 tests por falta de `DATABASE_URL`.

**Files:**
- Create: `backend/conftest.py`
- Create: `backend/tests/conftest.py`
- Modify: `backend/pyproject.toml:34-38`
- Create: `backend/.env.example`

**Interfaces:**
- Consumes: nada.
- Produces: los marcadores `unit`, `integration`, `e2e` aplicados automáticamente según la carpeta; la fixture `test_db` que devuelve un `RawSqlDatabase` apuntando a la base de datos de pruebas con las tablas vacías.

- [ ] **Step 1: Crear el conftest raíz que hace `tests` importable**

Los tests hacen `from tests.unit.mocks... import ...`. Hoy eso sólo funciona porque `uv sync` instala el proyecto en modo editable y deja un fichero `.pth` con la ruta absoluta del repo. Es frágil: fuera de ese entorno virtual, los imports revientan. Un `conftest.py` en la raíz de `backend/` lo hace explícito, porque pytest añade al `sys.path` el directorio de cada `conftest.py` que encuentra.

Crear `backend/conftest.py`:

```python
"""Root conftest: makes the `tests` package importable without relying on the
editable install's .pth file, which encodes an absolute path of the machine
that ran `uv sync`."""
```

- [ ] **Step 2: Declarar los marcadores en pyproject.toml**

Reemplazar el bloque `[tool.pytest.ini_options]` de `backend/pyproject.toml:34-38` por:

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
markers = [
    "unit: no database, no network, no environment variables",
    "integration: requires a live PostgreSQL test database",
    "e2e: full HTTP stack against a live PostgreSQL test database",
    "architecture: static analysis of the dependency rule",
]
```

- [ ] **Step 3: Escribir el conftest de tests con marcado automático**

Marcar 71 tests a mano es trabajo repetido y se olvida al añadir uno nuevo. El marcado se deriva de la carpeta.

Crear `backend/tests/conftest.py`:

```python
import os
from pathlib import Path

import pytest

_MARKER_BY_DIRECTORY = {
    "unit": "unit",
    "integration": "integration",
    "e2e": "e2e",
    "architecture": "architecture",
}

_TESTS_ROOT = Path(__file__).parent


def pytest_collection_modifyitems(items):
    """Derive the marker from the test's directory so that adding a file to
    tests/unit/ cannot silently escape `pytest -m unit`."""
    for item in items:
        relative = Path(item.fspath).relative_to(_TESTS_ROOT)
        marker = _MARKER_BY_DIRECTORY.get(relative.parts[0])
        if marker:
            item.add_marker(getattr(pytest.mark, marker))
```

- [ ] **Step 4: Verificar que el marcado funciona**

Run: `uv run pytest -m unit --collect-only -q | tail -3`
Expected: recoge los tests de `tests/unit/` y ninguno de `tests/e2e/`. El número de tests recogidos debe ser 58.

Run: `uv run pytest -m unit -q`
Expected: PASS. 58 tests, sin necesidad de `DATABASE_URL`.

- [ ] **Step 5: Añadir las fixtures de base de datos de prueba**

Añadir al final de `backend/tests/conftest.py`:

```python
_DEFAULT_TEST_DSN = "postgresql://postgres:postgrespassword@localhost:5433/leads_test"

_TABLES = (
    "leads",
    "scoring_rules",
    "routing_rules",
    "agents",
    "webhook_configs",
)


def _test_dsn() -> str:
    return os.getenv("TEST_DATABASE_URL", _DEFAULT_TEST_DSN)


def _ensure_test_database_exists(dsn: str) -> None:
    """Create the test database if it is missing, connecting to the maintenance
    database first. CREATE DATABASE cannot run inside a transaction."""
    import psycopg
    from urllib.parse import urlparse

    parsed = urlparse(dsn)
    database = parsed.path.lstrip("/")
    admin_dsn = dsn.replace(f"/{database}", "/postgres")

    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{database}"')


@pytest.fixture(scope="session")
def test_db():
    from infrastructure.adapters.output.persistence.connection import RawSqlDatabase

    dsn = _test_dsn()
    _ensure_test_database_exists(dsn)
    database = RawSqlDatabase(dsn=dsn)
    database.init_db()
    return database


@pytest.fixture(autouse=True)
def clean_tables(request):
    """Truncate before each database-backed test.

    A wrapping transaction with rollback would not work here: the unit of work
    opens its own connection and commits on its own, so an outer rollback would
    never see those rows."""
    if not set(request.node.keywords) & {"integration", "e2e"}:
        return

    database = request.getfixturevalue("test_db")
    with database.get_connection(autocommit=True) as conn:
        conn.execute(
            f"TRUNCATE {', '.join(_TABLES)} RESTART IDENTITY CASCADE"
        )
```

- [ ] **Step 6: Documentar las variables de entorno**

El `.gitignore` global del usuario ignora `.env.*`, lo que también atrapa a `.env.example`. Como es una plantilla sin secretos cuyo único propósito es estar versionada, añadir al final del `.gitignore` **de la raíz del repositorio** una negación explícita, que tiene precedencia:

```
# The template carries no secrets and only serves versioned; real .env files stay ignored.
!.env.example
```

Verificar con `git check-ignore -v backend/.env.example`: no debe devolver una regla de exclusión.

Crear `backend/.env.example`:

```bash
# PostgreSQL connection string used by the application at runtime.
# Required: the app refuses to start without it rather than silently falling
# back to another database.
DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_db

# Separate database for the test suite. Truncated before every database-backed
# test, so never point it at a database holding data you care about.
TEST_DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test

# Symmetric signing key for access tokens. Required: no default is provided.
JWT_SECRET=dev-secret-change-in-production

# Comma-separated list of allowed browser origins.
CORS_ORIGINS=http://localhost:5173,http://localhost,http://localhost:80
```

- [ ] **Step 7: Verificar la suite con base de datos**

Run: `docker compose up -d db` (desde la raíz del repositorio)
Espera a que el healthcheck esté en verde: `docker compose ps db`

Run: `cd backend && TEST_DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test JWT_SECRET=test-secret uv run pytest -q`
Expected: PASS en los 71 tests. Los 12 que fallaban por `KeyError: 'DATABASE_URL'` ahora encuentran la variable.

**Corrección adicional que el truncado destapa.** `tests/e2e/test_agent_endpoints.py:24` firma un token para un `uuid.uuid4()` inventado cuando la tabla `agents` está vacía, y `get_current_agent` lo rechaza con 401. Ese test venía pasando sólo porque la tabla arrastraba residuos de ejecuciones anteriores; con el truncado, falla.

Arreglar `_get_auth_headers()` para que cree un administrador real mediante la regla de bootstrap —con `agents` vacía, un `POST /api/v1/agents` sin autenticación crea el primer agente y le fuerza el rol `ADMIN`— siguiendo el mismo patrón que ya usa `tests/e2e/test_auth_flow_e2e.py`. La función debe funcionar tanto con la tabla vacía como con agentes presentes, porque el orden de ejecución no está garantizado.

Verificar aisladamente, con la tabla vacía:

```bash
PGPASSWORD=postgrespassword psql -h localhost -p 5433 -U postgres -d leads_test -c "TRUNCATE agents CASCADE"
uv run pytest tests/e2e/test_agent_endpoints.py -q
```

Y ejecutar la suite completa **dos veces seguidas**: ambas deben quedar en verde. Ése es el objetivo real del truncado.

- [ ] **Step 8: Commit**

```bash
git add backend/conftest.py backend/tests/conftest.py backend/pyproject.toml backend/.env.example
git commit -m "test: add pytest markers, test database fixtures and env documentation"
```

---

## Task 2: Test de arquitectura (guardián de la regla de dependencias)

Este test es el que hace verificable todo lo demás. Se escribe **antes** de corregir las violaciones: debe fallar señalando exactamente las cuatro que existen hoy (dos imports de `infrastructure` y dos de `pydantic`), repartidas en dos de sus cuatro funciones de test.

**Files:**
- Create: `backend/tests/architecture/test_dependency_rule.py`

**Interfaces:**
- Consumes: los marcadores de la Task 1.
- Produces: `test_domain_does_not_import_outer_layers`, `test_application_does_not_import_infrastructure`, `test_domain_does_not_import_third_party_frameworks`, `test_application_does_not_import_web_frameworks`.

- [ ] **Step 1: Escribir el test de arquitectura**

Crear `backend/tests/architecture/test_dependency_rule.py`:

```python
"""Static enforcement of the hexagonal dependency rule.

Reads each module's import statements from its syntax tree instead of importing
it, so a violation is reported even when the offending module cannot be
imported without its dependencies present."""

import ast
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"

# Everything the domain is allowed to depend on beyond the standard library:
# nothing. Listed explicitly so that adding a dependency is a deliberate act.
_THIRD_PARTY_FORBIDDEN_IN_DOMAIN = {
    "pydantic",
    "fastapi",
    "starlette",
    "sqlalchemy",
    "psycopg",
    "passlib",
    "bcrypt",
    "jwt",
    "httpx",
    "pandas",
    "numpy",
    "openpyxl",
}

_WEB_FRAMEWORKS_FORBIDDEN_IN_APPLICATION = {
    "fastapi",
    "starlette",
    "pydantic",
    "psycopg",
    "httpx",
    "pandas",
}


def _python_files(layer: str) -> list[Path]:
    return sorted((_SRC / layer).rglob("*.py"))


def _imported_roots(path: Path) -> set[str]:
    """Return the first segment of every module imported by this file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # Relative imports (level > 0) stay inside the layer by definition.
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


def _violations(layer: str, forbidden: set[str]) -> list[str]:
    found = []
    for path in _python_files(layer):
        offending = _imported_roots(path) & forbidden
        for module in sorted(offending):
            found.append(f"{path.relative_to(_SRC)} imports {module}")
    return found


def test_domain_does_not_import_outer_layers():
    violations = _violations("domain", {"application", "infrastructure"})
    assert violations == [], "Domain must not depend on outer layers:\n" + "\n".join(violations)


def test_application_does_not_import_infrastructure():
    violations = _violations("application", {"infrastructure"})
    assert violations == [], "Application must not depend on infrastructure:\n" + "\n".join(violations)


def test_domain_does_not_import_third_party_frameworks():
    violations = _violations("domain", _THIRD_PARTY_FORBIDDEN_IN_DOMAIN)
    assert violations == [], "Domain must depend only on the standard library:\n" + "\n".join(violations)


def test_application_does_not_import_web_frameworks():
    violations = _violations("application", _WEB_FRAMEWORKS_FORBIDDEN_IN_APPLICATION)
    assert violations == [], "Application must not depend on frameworks:\n" + "\n".join(violations)
```

- [ ] **Step 2: Ejecutar y confirmar que falla con las violaciones reales**

Run: `uv run pytest tests/architecture/ -v`

Expected: FAIL en dos tests, con este contenido exacto en los mensajes:

- `test_application_does_not_import_infrastructure` señala:
  - `use_cases/agent_use_cases.py imports infrastructure`
  - `use_cases/auth_use_cases.py imports infrastructure`
- `test_application_does_not_import_web_frameworks` señala:
  - `dtos/commands.py imports pydantic`
  - `dtos/queries.py imports pydantic`

Los dos tests de `domain` deben pasar: el dominio ya está limpio.

Si el resultado no coincide con lo anterior, **detenerse**: significa que el test está mal escrito, no que el código esté peor de lo esperado.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/architecture/test_dependency_rule.py
git commit -m "test(architecture): add dependency-rule guard, currently red on four known violations"
```

---

## Task 3: Excepciones de dominio sin códigos HTTP

`DomainException` transporta hoy un `status_code` HTTP. El dominio no debe conocer el protocolo por el que se le expone.

**Files:**
- Modify: `backend/src/domain/exceptions.py` (completo)
- Modify: `backend/src/infrastructure/adapters/input/api/exception_handlers.py` (completo)
- Modify: `backend/tests/unit/domain/test_exceptions.py` (completo)

**Interfaces:**
- Consumes: nada.
- Produces: `DomainException(message, error_code)` sin tercer parámetro. La constante `STATUS_BY_ERROR_CODE: dict[str, int]` en `exception_handlers.py`.

- [ ] **Step 1: Escribir el test que fija el contrato nuevo**

Reemplazar el contenido completo de `backend/tests/unit/domain/test_exceptions.py`:

```python
import pytest

from domain.exceptions import (
    AgentNotFoundException,
    DomainException,
    ForbiddenException,
    InvalidBudgetException,
    InvalidCredentialsException,
    InvalidEmailException,
    UnauthorizedException,
)


def test_base_exception_carries_message_and_default_code():
    exc = DomainException("something broke")
    assert exc.message == "something broke"
    assert exc.error_code == "DOMAIN_ERROR"


def test_base_exception_accepts_custom_code():
    exc = DomainException("conflict", error_code="ALREADY_EXISTS")
    assert exc.error_code == "ALREADY_EXISTS"


def test_domain_exceptions_do_not_expose_transport_details():
    """HTTP status codes belong to the adapter, not to the domain."""
    for exception_type in (
        DomainException,
        InvalidEmailException,
        InvalidBudgetException,
        AgentNotFoundException,
        InvalidCredentialsException,
        UnauthorizedException,
        ForbiddenException,
    ):
        instance = exception_type("msg") if exception_type is DomainException else exception_type()
        assert not hasattr(instance, "status_code"), (
            f"{exception_type.__name__} still carries an HTTP status code"
        )


@pytest.mark.parametrize(
    "exception_type,expected_code",
    [
        (InvalidEmailException, "INVALID_EMAIL"),
        (InvalidBudgetException, "INVALID_BUDGET"),
        (AgentNotFoundException, "AGENT_NOT_FOUND"),
        (InvalidCredentialsException, "INVALID_CREDENTIALS"),
        (UnauthorizedException, "UNAUTHORIZED"),
        (ForbiddenException, "FORBIDDEN"),
    ],
)
def test_each_exception_has_a_stable_error_code(exception_type, expected_code):
    assert exception_type().error_code == expected_code
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/domain/test_exceptions.py -v`
Expected: FAIL en `test_domain_exceptions_do_not_expose_transport_details` con el mensaje `DomainException still carries an HTTP status code`.

- [ ] **Step 3: Quitar el status_code del dominio**

Reemplazar el contenido completo de `backend/src/domain/exceptions.py`:

```python
class DomainException(Exception):
    """Base domain exception.

    Carries a stable error_code so that adapters can map it to whatever their
    transport requires. The domain itself knows nothing about HTTP."""

    def __init__(self, message: str, error_code: str = "DOMAIN_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class InvalidEmailException(DomainException):
    """Raised when an email format fails domain validation."""

    def __init__(self, message: str = "Formato de correo electrónico inválido"):
        super().__init__(message, error_code="INVALID_EMAIL")


class InvalidBudgetException(DomainException):
    """Raised when a budget/amount value is invalid (< 0)."""

    def __init__(self, message: str = "Presupuesto inválido"):
        super().__init__(message, error_code="INVALID_BUDGET")


class InvalidUUIDException(DomainException):
    """Raised when an identifier is not a well-formed UUID."""

    def __init__(self, message: str = "Formato de UUID inválido"):
        super().__init__(message, error_code="INVALID_UUID")


class InvalidRuleException(DomainException):
    """Raised when a scoring/assignment rule or its operator is invalid."""

    def __init__(self, message: str = "Regla de scoring o asignación inválida"):
        super().__init__(message, error_code="INVALID_RULE")


class LeadRoutingException(DomainException):
    """Raised when lead assignment fails in a way the caller must handle."""

    def __init__(self, message: str = "Fallo en la asignación del lead"):
        super().__init__(message, error_code="ROUTING_FAILED")


class AgentNotFoundException(DomainException):
    """Raised when a requested agent id does not exist."""

    def __init__(self, message: str = "Agent not found"):
        super().__init__(message, error_code="AGENT_NOT_FOUND")


class InvalidCredentialsException(DomainException):
    """Raised when an email/password pair does not match an active account."""

    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message, error_code="INVALID_CREDENTIALS")


class UnauthorizedException(DomainException):
    """Raised when a request carries no valid identity."""

    def __init__(self, message: str = "Authentication required or token invalid"):
        super().__init__(message, error_code="UNAUTHORIZED")


class ForbiddenException(DomainException):
    """Raised when an identity is valid but not permitted to act."""

    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message, error_code="FORBIDDEN")
```

- [ ] **Step 4: Mover el mapeo HTTP al adaptador**

Reemplazar el contenido completo de `backend/src/infrastructure/adapters/input/api/exception_handlers.py`:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from domain.exceptions import DomainException

# The domain reports what went wrong; this table decides how HTTP says it.
# Anything not listed is a client-side validation failure by default.
STATUS_BY_ERROR_CODE: dict[str, int] = {
    "AGENT_NOT_FOUND": 404,
    "INVALID_CREDENTIALS": 401,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
}

_DEFAULT_STATUS = 400


def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
        return JSONResponse(
            status_code=STATUS_BY_ERROR_CODE.get(exc.error_code, _DEFAULT_STATUS),
            content={
                "error": True,
                "error_code": exc.error_code,
                "message": exc.message,
            },
        )
```

- [ ] **Step 5: Ejecutar los tests**

Run: `uv run pytest tests/unit/domain/test_exceptions.py -v`
Expected: PASS, 9 tests.

Run: `uv run pytest -m unit -q`
Expected: PASS.

`tests/unit/application/test_agent_use_cases.py:25` afirma sobre `status_code` y romperá con este cambio. Eliminar esa única aserción, conservando la de `error_code`, que es la que sigue siendo el contrato. Es consecuencia directa del cambio, así que va en este mismo commit.

- [ ] **Step 6: Verificar que la API sigue devolviendo los mismos códigos**

Con el compose y las variables de entorno de la Task 1:

Run: `uv run pytest -m e2e -q`
Expected: PASS. `test_get_agent_not_found_returns_domain_error_shape` sigue recibiendo 404 y `test_ingest_lead_endpoint_negative_budget_returns_400` sigue recibiendo 400: el mapeo por tabla reproduce el comportamiento anterior.

- [ ] **Step 7: Commit**

```bash
git add backend/src/domain/exceptions.py backend/src/infrastructure/adapters/input/api/exception_handlers.py backend/tests/unit/domain/test_exceptions.py
git commit -m "refactor(domain): move HTTP status mapping out of domain exceptions into the API adapter"
```

---

## Task 4: Puerto de hashing de contraseñas

Primera de las dos inversiones de dependencia que cierran las violaciones duras.

**Files:**
- Create: `backend/src/application/ports/output/password_hasher_port.py`
- Create: `backend/src/infrastructure/adapters/output/security/__init__.py`
- Create: `backend/src/infrastructure/adapters/output/security/bcrypt_password_hasher.py`
- Create: `backend/tests/unit/mocks/fake_password_hasher.py`
- Create: `backend/tests/integration/test_bcrypt_password_hasher.py`
- Delete: `backend/src/infrastructure/security/password_hasher.py`
- Modify: `backend/tests/unit/infrastructure/test_password_hasher.py` → mover a `backend/tests/integration/test_bcrypt_password_hasher.py`

**Interfaces:**
- Consumes: nada.
- Produces: `PasswordHasherPort` con `hash(plain: str) -> str` y `verify(plain: str, hashed: str) -> bool`. `BcryptPasswordHasher()` como implementación. `FakePasswordHasher()` como doble determinista.

- [ ] **Step 1: Definir el puerto**

Crear `backend/src/application/ports/output/password_hasher_port.py`:

```python
import abc


class PasswordHasherPort(abc.ABC):
    """Turns plaintext credentials into an irreversible representation and
    checks a candidate against it. The algorithm is an infrastructure concern."""

    @abc.abstractmethod
    def hash(self, plain: str) -> str:
        """Return an irreversible representation of the plaintext password."""

    @abc.abstractmethod
    def verify(self, plain: str, hashed: str) -> bool:
        """Return True when the plaintext matches the stored representation."""
```

- [ ] **Step 2: Escribir el doble de test**

Crear `backend/tests/unit/mocks/fake_password_hasher.py`:

```python
from application.ports.output.password_hasher_port import PasswordHasherPort


class FakePasswordHasher(PasswordHasherPort):
    """Deterministic stand-in. Keeps unit tests free of bcrypt's cost factor,
    which adds ~250ms per call and would dominate the suite's runtime."""

    _PREFIX = "hashed:"

    def hash(self, plain: str) -> str:
        return f"{self._PREFIX}{plain}"

    def verify(self, plain: str, hashed: str) -> bool:
        return hashed == f"{self._PREFIX}{plain}"
```

- [ ] **Step 3: Escribir el test del adaptador real**

Crear `backend/tests/integration/test_bcrypt_password_hasher.py`:

```python
from application.ports.output.password_hasher_port import PasswordHasherPort
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher


def test_adapter_satisfies_the_port():
    assert isinstance(BcryptPasswordHasher(), PasswordHasherPort)


def test_hash_is_not_the_plaintext():
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash("s3cret")
    assert hashed != "s3cret"
    assert len(hashed) > 20


def test_verify_accepts_the_original_password():
    hasher = BcryptPasswordHasher()
    assert hasher.verify("s3cret", hasher.hash("s3cret")) is True


def test_verify_rejects_a_different_password():
    hasher = BcryptPasswordHasher()
    assert hasher.verify("wrong", hasher.hash("s3cret")) is False


def test_same_password_hashes_differently_each_time():
    """bcrypt salts every hash, so two calls must not collide."""
    hasher = BcryptPasswordHasher()
    assert hasher.hash("s3cret") != hasher.hash("s3cret")
```

- [ ] **Step 4: Ejecutar y verificar que falla**

Run: `uv run pytest tests/integration/test_bcrypt_password_hasher.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'infrastructure.adapters.output.security'`.

- [ ] **Step 5: Implementar el adaptador**

Crear `backend/src/infrastructure/adapters/output/security/__init__.py` vacío.

Crear `backend/src/infrastructure/adapters/output/security/bcrypt_password_hasher.py`:

```python
from passlib.context import CryptContext

from application.ports.output.password_hasher_port import PasswordHasherPort

# A single shared context avoids re-reading bcrypt's cost-factor config on
# every call.
_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


class BcryptPasswordHasher(PasswordHasherPort):
    def hash(self, plain: str) -> str:
        return _CONTEXT.hash(plain)

    def verify(self, plain: str, hashed: str) -> bool:
        return _CONTEXT.verify(plain, hashed)
```

- [ ] **Step 6: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/integration/test_bcrypt_password_hasher.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 7: Retirar el módulo antiguo**

El fichero `backend/src/infrastructure/security/password_hasher.py` todavía tiene consumidores (`auth_use_cases.py`, `agent_use_cases.py` y dos ficheros de test) que se migran en la Task 6. No se borra aún.

Borrar el test antiguo, cuya cobertura ya está replicada:

```bash
git rm backend/tests/unit/infrastructure/test_password_hasher.py
```

- [ ] **Step 8: Commit**

```bash
git add backend/src/application/ports/output/password_hasher_port.py \
        backend/src/infrastructure/adapters/output/security/ \
        backend/tests/unit/mocks/fake_password_hasher.py \
        backend/tests/integration/test_bcrypt_password_hasher.py
git commit -m "feat(application): add password hasher port with bcrypt adapter"
```

---

## Task 5: Puerto de servicio de tokens

**Files:**
- Create: `backend/src/application/ports/output/token_service_port.py`
- Create: `backend/src/infrastructure/adapters/output/security/jwt_token_service.py`
- Create: `backend/tests/unit/mocks/fake_token_service.py`
- Create: `backend/tests/integration/test_jwt_token_service.py`
- Modify: `backend/tests/unit/infrastructure/test_jwt_service.py` → se sustituye por el anterior

**Interfaces:**
- Consumes: `UnauthorizedException` de `domain.exceptions`.
- Produces: `TokenClaims(agent_id: str, role: str, tenant_id: str | None)` como `@dataclass(frozen=True)`. `TokenServicePort` con `issue(claims: TokenClaims) -> str` y `verify(token: str) -> TokenClaims`. `JwtTokenService(secret: str, expires_minutes: int = 60)`. `FakeTokenService()`.

- [ ] **Step 1: Definir el puerto**

Crear `backend/src/application/ports/output/token_service_port.py`:

```python
import abc
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TokenClaims:
    """Identity carried by an access token.

    Deliberately primitive: this crosses the boundary to an adapter that knows
    nothing about the domain's value objects."""

    agent_id: str
    role: str
    tenant_id: Optional[str]


class TokenServicePort(abc.ABC):
    """Issues and verifies access tokens. The token format is an
    infrastructure concern."""

    @abc.abstractmethod
    def issue(self, claims: TokenClaims) -> str:
        """Return a signed token carrying the given claims."""

    @abc.abstractmethod
    def verify(self, token: str) -> TokenClaims:
        """Return the claims of a valid token.

        Raises UnauthorizedException when the token is malformed, tampered
        with, or expired."""
```

- [ ] **Step 2: Escribir el doble de test**

Crear `backend/tests/unit/mocks/fake_token_service.py`:

```python
import json

from application.ports.output.token_service_port import TokenClaims, TokenServicePort
from domain.exceptions import UnauthorizedException


class FakeTokenService(TokenServicePort):
    """Reversible stand-in with no signing. Lets unit tests assert on the
    claims a use case issued without depending on a JWT secret."""

    def issue(self, claims: TokenClaims) -> str:
        return json.dumps(
            {
                "agent_id": claims.agent_id,
                "role": claims.role,
                "tenant_id": claims.tenant_id,
            }
        )

    def verify(self, token: str) -> TokenClaims:
        try:
            payload = json.loads(token)
        except (ValueError, TypeError):
            raise UnauthorizedException("Invalid token")
        return TokenClaims(
            agent_id=payload["agent_id"],
            role=payload["role"],
            tenant_id=payload["tenant_id"],
        )
```

- [ ] **Step 3: Escribir el test del adaptador real**

Crear `backend/tests/integration/test_jwt_token_service.py`:

```python
import pytest

from application.ports.output.token_service_port import TokenClaims, TokenServicePort
from domain.exceptions import UnauthorizedException
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService

_SECRET = "test-secret-do-not-use-in-production"


def test_adapter_satisfies_the_port():
    assert isinstance(JwtTokenService(secret=_SECRET), TokenServicePort)


def test_issued_token_round_trips_its_claims():
    service = JwtTokenService(secret=_SECRET)
    claims = TokenClaims(agent_id="a-1", role="MANAGER", tenant_id="t-1")
    assert service.verify(service.issue(claims)) == claims


def test_null_tenant_survives_the_round_trip():
    service = JwtTokenService(secret=_SECRET)
    claims = TokenClaims(agent_id="a-1", role="ADMIN", tenant_id=None)
    assert service.verify(service.issue(claims)).tenant_id is None


def test_tampered_token_is_rejected():
    service = JwtTokenService(secret=_SECRET)
    token = service.issue(TokenClaims(agent_id="a-1", role="AGENT", tenant_id="t-1"))
    with pytest.raises(UnauthorizedException):
        service.verify(token + "x")


def test_token_signed_with_another_secret_is_rejected():
    issued = JwtTokenService(secret="one-secret").issue(
        TokenClaims(agent_id="a-1", role="AGENT", tenant_id="t-1")
    )
    with pytest.raises(UnauthorizedException):
        JwtTokenService(secret="another-secret").verify(issued)


def test_expired_token_is_rejected():
    service = JwtTokenService(secret=_SECRET, expires_minutes=-1)
    token = service.issue(TokenClaims(agent_id="a-1", role="AGENT", tenant_id="t-1"))
    with pytest.raises(UnauthorizedException):
        service.verify(token)


def test_garbage_is_rejected_as_unauthorized_not_as_a_library_error():
    """A malformed token must surface as a domain exception, so the API layer
    has one thing to catch instead of every PyJWT error type."""
    with pytest.raises(UnauthorizedException):
        JwtTokenService(secret=_SECRET).verify("not-a-token")
```

- [ ] **Step 4: Ejecutar y verificar que falla**

Run: `uv run pytest tests/integration/test_jwt_token_service.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'infrastructure.adapters.output.security.jwt_token_service'`.

- [ ] **Step 5: Implementar el adaptador**

Crear `backend/src/infrastructure/adapters/output/security/jwt_token_service.py`:

```python
from datetime import datetime, timedelta, timezone

import jwt

from application.ports.output.token_service_port import TokenClaims, TokenServicePort
from domain.exceptions import UnauthorizedException

_ALGORITHM = "HS256"


class JwtTokenService(TokenServicePort):
    """PyJWT-backed adapter.

    The secret is injected rather than read from the environment here, so the
    composition root stays the single place that reads configuration."""

    def __init__(self, secret: str, expires_minutes: int = 60) -> None:
        if not secret:
            raise ValueError("JWT signing secret must not be empty")
        self._secret = secret
        self._expires_minutes = expires_minutes

    def issue(self, claims: TokenClaims) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": claims.agent_id,
            "role": claims.role,
            "tenant_id": claims.tenant_id,
            "exp": now + timedelta(minutes=self._expires_minutes),
            "iat": now,
        }
        return jwt.encode(payload, self._secret, algorithm=_ALGORITHM)

    def verify(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[_ALGORITHM])
        except jwt.PyJWTError as error:
            # Collapsing every PyJWT failure into one domain exception keeps
            # the library out of the caller's error handling.
            raise UnauthorizedException("Invalid or expired token") from error
        return TokenClaims(
            agent_id=payload["sub"],
            role=payload["role"],
            tenant_id=payload["tenant_id"],
        )
```

- [ ] **Step 6: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/integration/test_jwt_token_service.py -v`
Expected: PASS, 7 tests.

- [ ] **Step 7: Retirar el test antiguo**

```bash
git rm backend/tests/unit/infrastructure/test_jwt_service.py
```

Su cobertura está replicada y ampliada: el test antiguo no verificaba ni la expiración ni el rechazo de un secreto distinto.

- [ ] **Step 8: Commit**

```bash
git add backend/src/application/ports/output/token_service_port.py \
        backend/src/infrastructure/adapters/output/security/jwt_token_service.py \
        backend/tests/unit/mocks/fake_token_service.py \
        backend/tests/integration/test_jwt_token_service.py
git commit -m "feat(application): add token service port with JWT adapter"
```

---

## Task 6: Casos de uso de autenticación sin dependencias de infraestructura

Cierra las dos violaciones duras. Al terminar esta tarea, `test_application_does_not_import_infrastructure` pasa a verde.

**Files:**
- Modify: `backend/src/application/use_cases/auth_use_cases.py` (completo)
- Modify: `backend/src/application/use_cases/agent_use_cases.py:1-49`
- Modify: `backend/src/application/ports/input/auth_use_case_port.py`
- Modify: `backend/tests/unit/application/test_login_use_case.py` (completo)
- Modify: `backend/tests/unit/application/test_agent_use_cases.py`
- Modify: `backend/src/infrastructure/adapters/input/api/dependencies.py:68-69`
- Delete: `backend/src/infrastructure/security/password_hasher.py`, `backend/src/infrastructure/security/jwt_service.py`

**Interfaces:**
- Consumes: `PasswordHasherPort` y `FakePasswordHasher` (Task 4); `TokenServicePort`, `TokenClaims` y `FakeTokenService` (Task 5).
- Produces: `LoginUseCase(uow, password_hasher, token_service)`, `CreateAgentUseCase(uow, password_hasher)`.

- [ ] **Step 1: Reescribir el test de login contra los puertos**

Reemplazar el contenido completo de `backend/tests/unit/application/test_login_use_case.py`:

```python
import pytest

from application.ports.output.token_service_port import TokenClaims
from application.use_cases.auth_use_cases import LoginUseCase
from domain.entities.agent import Agent
from domain.exceptions import InvalidCredentialsException
from domain.value_objects.enums import AgentRole
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher
from tests.unit.mocks.fake_token_service import FakeTokenService
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_TENANT_ID = "b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"


def _build_use_case(email, password, role=AgentRole.MANAGER, is_active=True, tenant_id=_TENANT_ID):
    hasher = FakePasswordHasher()
    agent_repo = InMemoryAgentRepository()
    agent = Agent.create(
        "Test Agent",
        email,
        "Sales",
        role=role,
        hashed_password=hasher.hash(password),
        is_active=is_active,
        tenant_id=tenant_id,
    )
    agent_repo.save(agent)
    uow = InMemoryUnitOfWork(InMemoryLeadRepository(), InMemoryRuleRepository(), agent_repo)
    use_case = LoginUseCase(uow=uow, password_hasher=hasher, token_service=FakeTokenService())
    return use_case, agent


def test_login_succeeds_with_correct_credentials():
    use_case, _ = _build_use_case("manager@test.com", "correct-password")
    token = use_case.execute(email="manager@test.com", password="correct-password")
    assert isinstance(token, str) and token


def test_issued_token_carries_the_agent_identity_role_and_tenant():
    """The claims are the contract the API layer relies on to build the
    request context, so they are asserted explicitly."""
    use_case, agent = _build_use_case("manager@test.com", "correct-password")
    token = use_case.execute(email="manager@test.com", password="correct-password")
    claims = FakeTokenService().verify(token)
    assert claims == TokenClaims(
        agent_id=str(agent.id),
        role="MANAGER",
        tenant_id=_TENANT_ID,
    )


def test_platform_admin_gets_a_null_tenant_claim():
    use_case, _ = _build_use_case(
        "admin@test.com", "correct-password", role=AgentRole.ADMIN, tenant_id=None
    )
    token = use_case.execute(email="admin@test.com", password="correct-password")
    assert FakeTokenService().verify(token).tenant_id is None


def test_login_fails_with_wrong_password():
    use_case, _ = _build_use_case("manager@test.com", "correct-password")
    with pytest.raises(InvalidCredentialsException):
        use_case.execute(email="manager@test.com", password="wrong-password")


def test_login_fails_for_unknown_email():
    use_case, _ = _build_use_case("manager@test.com", "correct-password")
    with pytest.raises(InvalidCredentialsException):
        use_case.execute(email="nobody@test.com", password="correct-password")


def test_login_fails_for_inactive_agent():
    use_case, _ = _build_use_case("manager@test.com", "correct-password", is_active=False)
    with pytest.raises(InvalidCredentialsException):
        use_case.execute(email="manager@test.com", password="correct-password")


def test_unknown_email_and_wrong_password_are_indistinguishable():
    """Both paths must raise the same exception so the response does not leak
    whether an account exists."""
    use_case, _ = _build_use_case("manager@test.com", "correct-password")
    with pytest.raises(InvalidCredentialsException) as unknown:
        use_case.execute(email="nobody@test.com", password="correct-password")
    with pytest.raises(InvalidCredentialsException) as wrong:
        use_case.execute(email="manager@test.com", password="wrong-password")
    assert unknown.value.message == wrong.value.message
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/application/test_login_use_case.py -v`
Expected: FAIL con `TypeError: LoginUseCase.__init__() got an unexpected keyword argument 'password_hasher'`.

- [ ] **Step 3: Reescribir LoginUseCase**

Reemplazar el contenido completo de `backend/src/application/use_cases/auth_use_cases.py`:

```python
from application.ports.input.auth_use_case_port import LoginInputPort
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.token_service_port import TokenClaims, TokenServicePort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.exceptions import InvalidCredentialsException


class LoginUseCase(LoginInputPort):
    def __init__(
        self,
        uow: UnitOfWorkPort,
        password_hasher: PasswordHasherPort,
        token_service: TokenServicePort,
    ) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.token_service = token_service

    def execute(self, email: str, password: str) -> str:
        with self.uow:
            agent = self.uow.agents.get_by_email(email)

        # One exception for every failure path: a caller must not be able to
        # tell an unknown account from a wrong password.
        if not agent or not agent.is_active or not agent.hashed_password:
            raise InvalidCredentialsException()
        if not self.password_hasher.verify(password, agent.hashed_password):
            raise InvalidCredentialsException()

        return self.token_service.issue(
            TokenClaims(
                agent_id=str(agent.id),
                role=agent.role.value,
                tenant_id=str(agent.tenant_id) if agent.tenant_id else None,
            )
        )
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/application/test_login_use_case.py -v`
Expected: PASS, 7 tests.

- [ ] **Step 5: Adaptar el test de creación de agentes**

En `backend/tests/unit/application/test_agent_use_cases.py`, sustituir el import de infraestructura y la construcción del caso de uso.

Reemplazar la línea de import:

```python
from infrastructure.security.password_hasher import hash_password
```

por:

```python
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher
```

Sustituir cada construcción `CreateAgentUseCase(uow=uow)` por:

```python
CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher())
```

Y cada aserción que hoy comprueba que la contraseña quedó hasheada, por:

```python
assert saved.hashed_password == "hashed:plaintext-password"
```

usando como plaintext el valor que el test pase en el comando.

- [ ] **Step 6: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/application/test_agent_use_cases.py -v`
Expected: FAIL con `TypeError: CreateAgentUseCase.__init__() got an unexpected keyword argument 'password_hasher'`.

- [ ] **Step 7: Reescribir CreateAgentUseCase**

En `backend/src/application/use_cases/agent_use_cases.py`, eliminar la línea 10 (`from infrastructure.security.password_hasher import hash_password`) y reemplazar la clase `CreateAgentUseCase` (líneas 33-49) por:

```python
class CreateAgentUseCase(CreateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort):
        self.uow = uow
        self.password_hasher = password_hasher

    def execute(self, command: CreateAgentCommand) -> Agent:
        agent = Agent.create(
            name=command.name,
            email=command.email,
            team=command.team,
            active_leads_count=command.active_leads_count,
            is_active=command.is_active,
            role=command.role,
            hashed_password=self.password_hasher.hash(command.password),
            tenant_id=command.tenant_id,
        )
        with self.uow:
            return self.uow.agents.save(agent)
```

Añadir en la cabecera de imports del mismo fichero:

```python
from application.ports.output.password_hasher_port import PasswordHasherPort
```

- [ ] **Step 8: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/application/ -v`
Expected: PASS.

- [ ] **Step 9: Actualizar las factories de dependencias**

En `backend/src/infrastructure/adapters/input/api/dependencies.py`, sustituir las factories afectadas.

Reemplazar la línea 47-48:

```python
def get_create_agent_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateAgentInputPort:
    return CreateAgentUseCase(uow=uow, password_hasher=BcryptPasswordHasher())
```

Reemplazar la línea 68-69:

```python
def get_login_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> LoginInputPort:
    return LoginUseCase(
        uow=uow,
        password_hasher=BcryptPasswordHasher(),
        token_service=JwtTokenService(secret=os.environ["JWT_SECRET"]),
    )
```

Sustituir el import de la línea 28 por:

```python
import os

from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService
```

En `get_current_agent` (líneas 76-90), sustituir el bloque `try/except` por el uso del servicio de tokens:

```python
def get_current_agent(
    token: str = Depends(_oauth2_scheme),
    uow: UnitOfWorkPort = Depends(get_uow),
) -> Agent:
    claims = JwtTokenService(secret=os.environ["JWT_SECRET"]).verify(token)

    with uow:
        agent = uow.agents.get_by_id(UUID(claims.agent_id))

    if not agent or not agent.is_active:
        raise UnauthorizedException("Agent no longer exists or is inactive")
    return agent
```

Esto elimina el `except Exception:` genérico, que hoy convierte cualquier fallo —incluido un error de configuración— en un 401 engañoso. La instanciación repetida del servicio se resuelve en la Task 11.

- [ ] **Step 10: Eliminar los módulos de seguridad antiguos**

```bash
git rm backend/src/infrastructure/security/password_hasher.py backend/src/infrastructure/security/jwt_service.py
```

Verificar que no queda ningún consumidor:

Run: `rg "infrastructure.security" backend/src backend/tests`
Expected: sin resultados.

Si `backend/src/infrastructure/security/` queda con sólo `__init__.py`, borrar también el directorio.

- [ ] **Step 11: Verificar que el guardián de arquitectura pasa a verde**

Run: `uv run pytest tests/architecture/ -v`
Expected: `test_application_does_not_import_infrastructure` **PASS**. `test_application_does_not_import_web_frameworks` sigue en FAIL por Pydantic en los DTOs; lo resuelve la Task 7.

- [ ] **Step 12: Ejecutar la suite completa**

Run: `uv run pytest -m unit -q`
Expected: PASS.

Run: `uv run pytest -q` (con el compose levantado y las variables de entorno)
Expected: PASS.

- [ ] **Step 13: Commit**

```bash
git add -A backend/src backend/tests
git commit -m "refactor(application): invert security dependencies through ports

The login and agent-creation use cases now receive a password hasher and a
token service instead of importing infrastructure directly."
```

---

## Task 7: DTOs de aplicación sin Pydantic

**Files:**
- Modify: `backend/src/application/dtos/commands.py` (completo)
- Modify: `backend/src/application/dtos/queries.py` (completo)
- Modify: `backend/src/infrastructure/adapters/input/api/agent_router.py`, `rule_router.py`, `lead_router.py` (construcción de comandos y consultas)

**Interfaces:**
- Consumes: nada.
- Produces: `CreateAgentCommand`, `CreateScoringRuleCommand`, `CreateRoutingRuleCommand`, `GetLeadsQuery`, `GetAgentsQuery`, `GetAgentQuery`, `GetRulesQuery`, todos `@dataclass(frozen=True)` con los mismos nombres de campo que hoy. `LeadsPageResult.items: list[Lead]`, `AgentsPageResult.items: list[Agent]`, `BatchProcessResult.failed_rows: list[FailedRow]`.

- [ ] **Step 1: Escribir el test que fija el contrato**

Crear `backend/tests/unit/application/test_dtos_are_framework_free.py`:

```python
import dataclasses
from uuid import uuid4

from application.dtos.commands import (
    CreateAgentCommand,
    CreateRoutingRuleCommand,
    CreateScoringRuleCommand,
)
from application.dtos.queries import GetAgentQuery, GetAgentsQuery, GetLeadsQuery, GetRulesQuery

_ALL_DTOS = (
    CreateAgentCommand,
    CreateScoringRuleCommand,
    CreateRoutingRuleCommand,
    GetLeadsQuery,
    GetAgentsQuery,
    GetAgentQuery,
    GetRulesQuery,
)


def test_every_dto_is_a_frozen_dataclass():
    for dto in _ALL_DTOS:
        assert dataclasses.is_dataclass(dto), f"{dto.__name__} is not a dataclass"
        assert dto.__dataclass_params__.frozen, f"{dto.__name__} is not frozen"


def test_create_agent_command_keeps_its_field_names_and_defaults():
    command = CreateAgentCommand(
        name="Carlos Lopez",
        email="clopez@sales.com",
        team="Sales",
        password="s3cret",
    )
    assert command.active_leads_count == 0
    assert command.is_active is True
    assert command.role == "AGENT"
    assert command.tenant_id is None


def test_queries_keep_their_pagination_defaults():
    query = GetLeadsQuery(tenant_id=uuid4())
    assert query.limit == 100
    assert query.offset == 0
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/application/test_dtos_are_framework_free.py -v`
Expected: FAIL en `test_every_dto_is_a_frozen_dataclass` con `CreateAgentCommand is not a dataclass`.

- [ ] **Step 3: Reescribir los comandos**

Reemplazar el contenido completo de `backend/src/application/dtos/commands.py`:

```python
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

if TYPE_CHECKING:
    from domain.entities.agent import Agent
    from domain.entities.lead import Lead


@dataclass(frozen=True)
class IngestLeadCommand:
    tenant_id: UUID
    first_name: str
    last_name: str
    email: str
    company: str
    budget: float
    industry: str
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    phone: Optional[str] = None


@dataclass(frozen=True)
class CreateAgentCommand:
    name: str
    email: str
    team: str
    password: str
    active_leads_count: int = 0
    is_active: bool = True
    role: str = "AGENT"
    tenant_id: Optional[UUID] = None


@dataclass(frozen=True)
class CreateScoringRuleCommand:
    tenant_id: UUID
    name: str
    field: str
    operator: str
    value: str
    score_delta: int


@dataclass(frozen=True)
class CreateRoutingRuleCommand:
    tenant_id: UUID
    min_score: int
    target_team: str
    assignment_strategy: str
    target_agent_ids: List[UUID]


@dataclass(frozen=True)
class FailedRow:
    row_number: int
    email: str
    error: str
    error_code: str


@dataclass(frozen=True)
class LeadProcessedResult:
    lead_id: str
    status: str
    score: int
    assigned_agent_id: Optional[str] = None
    applied_rules_count: int = 0
    webhook_dispatched: bool = False
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass(frozen=True)
class LeadsPageResult:
    items: List["Lead"]
    total: int


@dataclass(frozen=True)
class AgentsPageResult:
    items: List["Agent"]
    total: int


@dataclass(frozen=True)
class BatchProcessResult:
    job_id: str
    total_rows: int
    successful_ingestions: int
    failed_rows: List[FailedRow]
```

`CreateAgentCommand` cambia el orden de sus campos: `password` sube antes de los que tienen valor por defecto, porque una dataclass no admite un campo obligatorio detrás de uno opcional. Todos los consumidores lo construyen con argumentos nombrados, así que el cambio de orden no rompe nada; verificarlo en el paso 6.

- [ ] **Step 4: Reescribir las consultas**

Reemplazar el contenido completo de `backend/src/application/dtos/queries.py`:

```python
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class GetLeadsQuery:
    tenant_id: UUID
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetAgentsQuery:
    team: Optional[str] = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetAgentQuery:
    agent_id: UUID


@dataclass(frozen=True)
class GetRulesQuery:
    tenant_id: UUID
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/application/test_dtos_are_framework_free.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 6: Localizar y corregir las construcciones que dependían de Pydantic**

Pydantic acepta cadenas donde el tipo declara `UUID` y las convierte; una dataclass no. Los routers ya reciben `UUID` de FastAPI, pero hay que verificarlo.

Run: `rg -n "CreateAgentCommand\(|CreateScoringRuleCommand\(|CreateRoutingRuleCommand\(|GetLeadsQuery\(|GetAgentsQuery\(|GetAgentQuery\(|GetRulesQuery\(" backend/src backend/tests`

Para cada resultado, comprobar que:
1. Se construye con argumentos nombrados.
2. Los valores que van a campos `UUID` son objetos `UUID`, no cadenas.
3. No se usa `.model_dump()`, `.dict()`, `.model_validate()` ni `.parse_obj()` sobre estos objetos. Si aparece `.model_dump()`, sustituirlo por `dataclasses.asdict(...)`.

- [ ] **Step 7: Verificar que el guardián de arquitectura pasa entero**

Run: `uv run pytest tests/architecture/ -v`
Expected: PASS, los 4 tests. La regla de dependencias queda cumplida y protegida.

- [ ] **Step 8: Ejecutar la suite completa**

Run: `uv run pytest -q` (con compose y variables de entorno)
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/src/application/dtos/ backend/src/infrastructure/adapters/input/api/ backend/tests/unit/application/test_dtos_are_framework_free.py
git commit -m "refactor(application): replace pydantic DTOs with frozen dataclasses

Completes the dependency rule: application no longer depends on any framework."
```

---

## Task 8: Puertos de reloj y de generación de identificadores

Las entidades llaman hoy a `datetime.now()` y `uuid4()` internamente. Es un efecto de lado no controlable que impide asertar sobre fechas y obliga a los tests a aceptar cualquier valor.

**Files:**
- Create: `backend/src/application/ports/output/clock_port.py`
- Create: `backend/src/application/ports/output/id_generator_port.py`
- Create: `backend/src/infrastructure/adapters/output/system_clock.py`
- Create: `backend/src/infrastructure/adapters/output/uuid_generator.py`
- Create: `backend/tests/unit/mocks/frozen_clock.py`
- Create: `backend/tests/unit/application/test_clock_and_id_ports.py`

**Interfaces:**
- Consumes: nada.
- Produces: `ClockPort.now() -> datetime` (siempre con zona horaria UTC). `IdGeneratorPort.new_id() -> UUID`. `SystemClock()`, `UuidGenerator()`, `FrozenClock(instant: datetime)`.

- [ ] **Step 1: Escribir el test**

Crear `backend/tests/unit/application/test_clock_and_id_ports.py`:

```python
from datetime import datetime, timezone
from uuid import UUID

from application.ports.output.clock_port import ClockPort
from application.ports.output.id_generator_port import IdGeneratorPort
from infrastructure.adapters.output.system_clock import SystemClock
from infrastructure.adapters.output.uuid_generator import UuidGenerator
from tests.unit.mocks.frozen_clock import FrozenClock


def test_system_clock_satisfies_the_port():
    assert isinstance(SystemClock(), ClockPort)


def test_system_clock_returns_timezone_aware_utc():
    """A naive datetime would compare incorrectly against stored timestamps."""
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 0


def test_frozen_clock_always_returns_the_same_instant():
    instant = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    clock = FrozenClock(instant)
    assert clock.now() == instant
    assert clock.now() == instant


def test_uuid_generator_satisfies_the_port():
    assert isinstance(UuidGenerator(), IdGeneratorPort)


def test_uuid_generator_returns_distinct_uuids():
    generator = UuidGenerator()
    first, second = generator.new_id(), generator.new_id()
    assert isinstance(first, UUID)
    assert first != second
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/application/test_clock_and_id_ports.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'application.ports.output.clock_port'`.

- [ ] **Step 3: Definir los puertos**

Crear `backend/src/application/ports/output/clock_port.py`:

```python
import abc
from datetime import datetime


class ClockPort(abc.ABC):
    """Supplies the current instant.

    Injecting time removes the hidden side effect that makes assertions on
    timestamps impossible."""

    @abc.abstractmethod
    def now(self) -> datetime:
        """Return the current instant, always timezone-aware in UTC."""
```

Crear `backend/src/application/ports/output/id_generator_port.py`:

```python
import abc
from uuid import UUID


class IdGeneratorPort(abc.ABC):
    """Supplies fresh entity identifiers."""

    @abc.abstractmethod
    def new_id(self) -> UUID:
        """Return a new unique identifier."""
```

- [ ] **Step 4: Implementar los adaptadores**

Crear `backend/src/infrastructure/adapters/output/system_clock.py`:

```python
from datetime import datetime, timezone

from application.ports.output.clock_port import ClockPort


class SystemClock(ClockPort):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
```

Crear `backend/src/infrastructure/adapters/output/uuid_generator.py`:

```python
from uuid import UUID, uuid4

from application.ports.output.id_generator_port import IdGeneratorPort


class UuidGenerator(IdGeneratorPort):
    def new_id(self) -> UUID:
        return uuid4()
```

Crear `backend/tests/unit/mocks/frozen_clock.py`:

```python
from datetime import datetime

from application.ports.output.clock_port import ClockPort


class FrozenClock(ClockPort):
    """Returns one fixed instant, so tests can assert on timestamps."""

    def __init__(self, instant: datetime) -> None:
        self._instant = instant

    def now(self) -> datetime:
        return self._instant
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/application/test_clock_and_id_ports.py -v`
Expected: PASS, 5 tests.

Run: `uv run pytest tests/architecture/ -v`
Expected: PASS. Los puertos nuevos no introducen dependencias prohibidas.

- [ ] **Step 6: Commit**

Los puertos quedan disponibles; los consumen las entidades nuevas de F1 y F2. No se refactorizan aquí las entidades existentes: hacerlo ahora obligaría a tocar `Lead.create()` y sus ocho tests sin ningún consumidor que lo aproveche todavía.

```bash
git add backend/src/application/ports/output/clock_port.py \
        backend/src/application/ports/output/id_generator_port.py \
        backend/src/infrastructure/adapters/output/system_clock.py \
        backend/src/infrastructure/adapters/output/uuid_generator.py \
        backend/tests/unit/mocks/frozen_clock.py \
        backend/tests/unit/application/test_clock_and_id_ports.py
git commit -m "feat(application): add clock and id generator ports with adapters"
```

---

## Task 9: Política de autorización en el dominio

Las reglas de quién puede hacer qué viven hoy repartidas entre `dependencies.py:105-135` y `agent_router.py:36-63`, acopladas a FastAPI y no reutilizables.

**Files:**
- Create: `backend/src/domain/policies/__init__.py`
- Create: `backend/src/domain/policies/authorization_policy.py`
- Create: `backend/tests/unit/domain/test_authorization_policy.py`

**Interfaces:**
- Consumes: `Agent`, `AgentRole`, `TenantId`, `ForbiddenException`.
- Produces: `AuthorizationPolicy` con métodos estáticos `can_access_tenant(actor, tenant_id) -> bool`, `can_manage_organization(actor) -> bool`, `can_create_agent_with_role(actor, role) -> bool`, `can_view_lead(actor, lead_tenant_id, lead_assigned_agent_id) -> bool`, y sus variantes `ensure_*` que lanzan `ForbiddenException`.

- [ ] **Step 1: Escribir el test**

Crear `backend/tests/unit/domain/test_authorization_policy.py`:

```python
from uuid import uuid4

import pytest

from domain.entities.agent import Agent
from domain.exceptions import ForbiddenException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.enums import AgentRole

_TENANT_A = uuid4()
_TENANT_B = uuid4()


def _agent(role: AgentRole, tenant_id=None, agent_id=None) -> Agent:
    return Agent.create(
        "Someone", "someone@test.com", "Sales", role=role, tenant_id=tenant_id, agent_id=agent_id
    )


class TestTenantAccess:
    def test_platform_admin_reaches_every_organization(self):
        admin = _agent(AgentRole.ADMIN, tenant_id=None)
        assert AuthorizationPolicy.can_access_tenant(admin, _TENANT_A) is True
        assert AuthorizationPolicy.can_access_tenant(admin, _TENANT_B) is True

    def test_manager_reaches_only_its_own_organization(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        assert AuthorizationPolicy.can_access_tenant(manager, _TENANT_A) is True
        assert AuthorizationPolicy.can_access_tenant(manager, _TENANT_B) is False

    def test_agent_without_organization_reaches_nothing(self):
        orphan = _agent(AgentRole.AGENT, tenant_id=None)
        assert AuthorizationPolicy.can_access_tenant(orphan, _TENANT_A) is False

    def test_ensure_raises_forbidden_when_denied(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        with pytest.raises(ForbiddenException):
            AuthorizationPolicy.ensure_can_access_tenant(manager, _TENANT_B)

    def test_ensure_is_silent_when_allowed(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        AuthorizationPolicy.ensure_can_access_tenant(manager, _TENANT_A)


class TestOrganizationManagement:
    def test_admin_and_manager_can_manage(self):
        assert AuthorizationPolicy.can_manage_organization(_agent(AgentRole.ADMIN)) is True
        assert AuthorizationPolicy.can_manage_organization(
            _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        ) is True

    def test_sales_agent_cannot_manage(self):
        assert AuthorizationPolicy.can_manage_organization(
            _agent(AgentRole.AGENT, tenant_id=_TENANT_A)
        ) is False


class TestAgentCreation:
    def test_only_platform_admin_creates_platform_admins(self):
        admin = _agent(AgentRole.ADMIN)
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        assert AuthorizationPolicy.can_create_agent_with_role(admin, AgentRole.ADMIN) is True
        assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.ADMIN) is False

    def test_manager_creates_managers_and_agents(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.MANAGER) is True
        assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.AGENT) is True

    def test_sales_agent_creates_nobody(self):
        sales = _agent(AgentRole.AGENT, tenant_id=_TENANT_A)
        for role in AgentRole:
            assert AuthorizationPolicy.can_create_agent_with_role(sales, role) is False


class TestLeadVisibility:
    def test_manager_sees_every_lead_of_its_organization(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        assert AuthorizationPolicy.can_view_lead(manager, _TENANT_A, uuid4()) is True

    def test_manager_does_not_see_another_organization_leads(self):
        manager = _agent(AgentRole.MANAGER, tenant_id=_TENANT_A)
        assert AuthorizationPolicy.can_view_lead(manager, _TENANT_B, uuid4()) is False

    def test_sales_agent_sees_only_leads_assigned_to_itself(self):
        own_id = uuid4()
        sales = _agent(AgentRole.AGENT, tenant_id=_TENANT_A, agent_id=own_id)
        assert AuthorizationPolicy.can_view_lead(sales, _TENANT_A, own_id) is True
        assert AuthorizationPolicy.can_view_lead(sales, _TENANT_A, uuid4()) is False

    def test_sales_agent_does_not_see_unassigned_leads(self):
        own_id = uuid4()
        sales = _agent(AgentRole.AGENT, tenant_id=_TENANT_A, agent_id=own_id)
        assert AuthorizationPolicy.can_view_lead(sales, _TENANT_A, None) is False
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/domain/test_authorization_policy.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'domain.policies'`.

- [ ] **Step 3: Implementar la política**

Crear `backend/src/domain/policies/__init__.py` vacío.

Crear `backend/src/domain/policies/authorization_policy.py`:

```python
from typing import Optional
from uuid import UUID

from domain.entities.agent import Agent
from domain.exceptions import ForbiddenException
from domain.value_objects.enums import AgentRole

_ORGANIZATION_MANAGERS = (AgentRole.ADMIN, AgentRole.MANAGER)


def _same_id(left, right) -> bool:
    """Identifiers arrive as value objects, UUIDs or strings depending on the
    caller, so they are compared by their textual form."""
    return left is not None and right is not None and str(left) == str(right)


class AuthorizationPolicy:
    """Single source of truth for who may do what.

    Lives in the domain so the same rules apply from an HTTP adapter, a CLI or
    a background worker, and so they can be tested without a web framework."""

    @staticmethod
    def can_access_tenant(actor: Agent, tenant_id: UUID) -> bool:
        if actor.role == AgentRole.ADMIN:
            return True
        return _same_id(actor.tenant_id, tenant_id)

    @staticmethod
    def ensure_can_access_tenant(actor: Agent, tenant_id: UUID) -> None:
        if not AuthorizationPolicy.can_access_tenant(actor, tenant_id):
            raise ForbiddenException("You do not have access to this organization's data")

    @staticmethod
    def can_manage_organization(actor: Agent) -> bool:
        return actor.role in _ORGANIZATION_MANAGERS

    @staticmethod
    def ensure_can_manage_organization(actor: Agent) -> None:
        if not AuthorizationPolicy.can_manage_organization(actor):
            raise ForbiddenException(
                f"Role {actor.role.value} is not permitted to perform this action"
            )

    @staticmethod
    def can_create_agent_with_role(actor: Agent, role: AgentRole) -> bool:
        if not AuthorizationPolicy.can_manage_organization(actor):
            return False
        # Only the platform administrator may mint another platform administrator.
        if role == AgentRole.ADMIN:
            return actor.role == AgentRole.ADMIN
        return True

    @staticmethod
    def ensure_can_create_agent_with_role(actor: Agent, role: AgentRole) -> None:
        if not AuthorizationPolicy.can_create_agent_with_role(actor, role):
            raise ForbiddenException(f"You may not create an agent with role {role.value}")

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
Expected: PASS, 16 tests.

Run: `uv run pytest tests/architecture/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/domain/policies/ backend/tests/unit/domain/test_authorization_policy.py
git commit -m "feat(domain): add authorization policy as the single source of permission rules"
```

---

## Task 10: Contexto de petición y eliminación del tenant de las URLs

Cierra las fugas cross-tenant por construcción: el cliente deja de poder elegir a qué organización accede.

**Files:**
- Create: `backend/src/application/dtos/context.py`
- Modify: `backend/src/infrastructure/adapters/input/api/dependencies.py:105-136`
- Modify: `backend/src/infrastructure/adapters/input/api/lead_router.py`, `rule_router.py`, `agent_router.py`
- Modify: `backend/src/infrastructure/main.py:75-78`
- Modify: `backend/tests/unit/infrastructure/test_auth_dependencies.py`
- Modify: `backend/tests/e2e/test_lead_endpoints.py`, `test_auth_flow_e2e.py`, `test_system_e2e.py`

**Interfaces:**
- Consumes: `AuthorizationPolicy` (Task 9), `Agent`.
- Produces: `RequestContext(actor: Agent, tenant_id: UUID | None)` como `@dataclass(frozen=True)`. La dependencia `get_request_context() -> RequestContext`. La dependencia `require_organization_manager() -> RequestContext`.

- [ ] **Step 1: Definir el contexto**

Crear `backend/src/application/dtos/context.py`:

```python
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from domain.entities.agent import Agent


@dataclass(frozen=True)
class RequestContext:
    """Who is acting and on which organization.

    Built once per request from the verified token. Use cases receive it
    instead of a tenant identifier supplied by the caller, which is what makes
    cross-tenant access impossible rather than merely checked."""

    actor: Agent
    tenant_id: Optional[UUID]
```

- [ ] **Step 2: Escribir el test de las dependencias nuevas**

Reemplazar el contenido completo de `backend/tests/unit/infrastructure/test_auth_dependencies.py`:

```python
from uuid import uuid4

import pytest

from application.ports.output.token_service_port import TokenClaims
from domain.entities.agent import Agent
from domain.exceptions import ForbiddenException, UnauthorizedException
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.input.api.dependencies import (
    build_request_context,
    resolve_current_agent,
)
from tests.unit.mocks.fake_token_service import FakeTokenService
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_TENANT_A = uuid4()


def _uow_with(agent: Agent) -> InMemoryUnitOfWork:
    repo = InMemoryAgentRepository()
    repo.save(agent)
    return InMemoryUnitOfWork(InMemoryLeadRepository(), InMemoryRuleRepository(), repo)


def _token_for(agent: Agent) -> str:
    return FakeTokenService().issue(
        TokenClaims(
            agent_id=str(agent.id),
            role=agent.role.value,
            tenant_id=str(agent.tenant_id) if agent.tenant_id else None,
        )
    )


def test_valid_token_resolves_the_agent():
    agent = Agent.create("M", "m@test.com", "Sales", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    resolved = resolve_current_agent(
        token=_token_for(agent), uow=_uow_with(agent), token_service=FakeTokenService()
    )
    assert str(resolved.id) == str(agent.id)


def test_malformed_token_is_unauthorized():
    agent = Agent.create("M", "m@test.com", "Sales", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    with pytest.raises(UnauthorizedException):
        resolve_current_agent(
            token="garbage", uow=_uow_with(agent), token_service=FakeTokenService()
        )


def test_deactivated_agent_is_unauthorized_even_with_a_valid_token():
    """Identity is revalidated against the database on every request, so
    deactivating an account cuts an outstanding token immediately."""
    agent = Agent.create(
        "M", "m@test.com", "Sales", role=AgentRole.MANAGER, tenant_id=_TENANT_A, is_active=False
    )
    with pytest.raises(UnauthorizedException):
        resolve_current_agent(
            token=_token_for(agent), uow=_uow_with(agent), token_service=FakeTokenService()
        )


def test_context_carries_the_agent_own_tenant():
    agent = Agent.create("M", "m@test.com", "Sales", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    context = build_request_context(current_agent=agent)
    assert context.actor is agent
    assert str(context.tenant_id) == str(_TENANT_A)


def test_platform_admin_context_has_no_tenant():
    admin = Agent.create("A", "a@test.com", "Platform", role=AgentRole.ADMIN, tenant_id=None)
    assert build_request_context(current_agent=admin).tenant_id is None


def test_sales_agent_is_refused_organization_management():
    from infrastructure.adapters.input.api.dependencies import require_organization_manager

    sales = Agent.create("S", "s@test.com", "Sales", role=AgentRole.AGENT, tenant_id=_TENANT_A)
    with pytest.raises(ForbiddenException):
        require_organization_manager(context=build_request_context(current_agent=sales))


def test_manager_is_allowed_organization_management():
    from infrastructure.adapters.input.api.dependencies import require_organization_manager

    manager = Agent.create("M", "m@test.com", "Sales", role=AgentRole.MANAGER, tenant_id=_TENANT_A)
    context = build_request_context(current_agent=manager)
    assert require_organization_manager(context=context) is context
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/infrastructure/test_auth_dependencies.py -v`
Expected: FAIL con `ImportError: cannot import name 'build_request_context'`.

- [ ] **Step 4: Reescribir las dependencias de autorización**

En `backend/src/infrastructure/adapters/input/api/dependencies.py`, reemplazar el bloque de las líneas 105-136 por:

```python
def resolve_current_agent(token: str, uow: UnitOfWorkPort, token_service: TokenServicePort) -> Agent:
    """Pure function so it can be tested without FastAPI's dependency machinery."""
    claims = token_service.verify(token)

    with uow:
        agent = uow.agents.get_by_id(UUID(claims.agent_id))

    if not agent or not agent.is_active:
        raise UnauthorizedException("Agent no longer exists or is inactive")
    return agent


def build_request_context(current_agent: Agent) -> RequestContext:
    """The organization always comes from the verified identity, never from the
    request path or body."""
    tenant_id = UUID(str(current_agent.tenant_id)) if current_agent.tenant_id else None
    return RequestContext(actor=current_agent, tenant_id=tenant_id)
```

**Orden de definición.** `Depends(get_request_context)` se evalúa cuando Python define la función, no cuando se llama. Por eso `require_organization_manager` debe escribirse **después** de `get_request_context`, y éste después de `get_current_agent`. El orden correcto en el fichero es: `get_token_service` → `get_current_agent` → `get_optional_current_agent` → `get_request_context` → `require_organization_manager`.

Sustituir `get_current_agent` / `get_optional_current_agent` para que deleguen en `resolve_current_agent`:

```python
def get_current_agent(
    token: str = Depends(_oauth2_scheme),
    uow: UnitOfWorkPort = Depends(get_uow),
    token_service: TokenServicePort = Depends(get_token_service),
) -> Agent:
    return resolve_current_agent(token=token, uow=uow, token_service=token_service)


def get_optional_current_agent(
    token: Optional[str] = Depends(_optional_oauth2_scheme),
    uow: UnitOfWorkPort = Depends(get_uow),
    token_service: TokenServicePort = Depends(get_token_service),
) -> Optional[Agent]:
    if not token:
        return None
    try:
        return resolve_current_agent(token=token, uow=uow, token_service=token_service)
    except UnauthorizedException:
        return None


def get_request_context(current_agent: Agent = Depends(get_current_agent)) -> RequestContext:
    return build_request_context(current_agent=current_agent)


def require_organization_manager(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    AuthorizationPolicy.ensure_can_manage_organization(context.actor)
    return context
```

Y, antes de todas ellas, la factory del servicio de tokens. En la Task 11 pasa a servirse del contenedor; aquí basta con esto:

```python
def get_token_service() -> TokenServicePort:
    return JwtTokenService(secret=os.environ["JWT_SECRET"])
```

Eliminar por completo `require_role`, `verify_tenant_access` y `require_role_and_tenant`: sus reglas viven ahora en `AuthorizationPolicy`.

Añadir los imports necesarios:

```python
from application.dtos.context import RequestContext
from application.ports.output.token_service_port import TokenServicePort
from domain.policies.authorization_policy import AuthorizationPolicy
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/infrastructure/test_auth_dependencies.py -v`
Expected: PASS, 7 tests.

- [ ] **Step 6: Quitar el tenant de los prefijos de las rutas**

En `backend/src/infrastructure/main.py`, reemplazar las líneas 75-78 por:

```python
app.include_router(lead_router, prefix="/api/v1/leads", tags=["Leads"])
app.include_router(rule_router, prefix="/api/v1/rules", tags=["Rules"])
app.include_router(agent_router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
```

- [ ] **Step 7: Adaptar los routers al contexto**

En `lead_router.py` y `rule_router.py`, para cada endpoint:

1. Eliminar el parámetro `tenant_id: UUID` de la firma.
2. Sustituir la dependencia de autorización por `context: RequestContext = Depends(get_request_context)` en los de lectura, o `Depends(require_organization_manager)` en los de gestión de reglas.
3. Sustituir cada uso de `tenant_id` por `context.tenant_id`.

Ejemplo, para el listado de leads en `lead_router.py`:

```python
@router.get("", response_model=PaginatedLeadsResponse)
def list_leads(
    limit: int = 100,
    offset: int = 0,
    context: RequestContext = Depends(get_request_context),
    use_case: GetLeadsInputPort = Depends(get_get_leads_use_case),
) -> PaginatedLeadsResponse:
    result = use_case.execute(
        GetLeadsQuery(tenant_id=context.tenant_id, limit=limit, offset=offset)
    )
    ...
```

En `agent_router.py`, sustituir la función `_authorize_agent_creation` (líneas 36-45) por llamadas a la política:

```python
AuthorizationPolicy.ensure_can_create_agent_with_role(actor, requested_role)
if actor.role != AgentRole.ADMIN:
    AuthorizationPolicy.ensure_can_access_tenant(actor, request.tenant_id)
```

- [ ] **Step 8: Nota sobre los endpoints públicos de ingesta**

`POST /leads/ingest` y `POST /leads/batch-upload` quedan **sin cambios de autorización en F0**. Su modelo de acceso depende de `LeadSource`, que se introduce en F2. Documentarlo con un comentario en cada endpoint:

```python
# Unauthenticated by design until F2 introduces LeadSource credentials.
# Tracked in docs/specs/2026-08-07-lead-router-mvp-design.md §8.
```

Provisionalmente, el `tenant_id` de estos dos endpoints se mantiene como parámetro de ruta bajo el prefijo `/api/v1/intake/{tenant_id}/`, para no dejarlos sin forma de identificar la organización.

- [ ] **Step 9: Actualizar los tests extremo a extremo**

En `tests/e2e/test_lead_endpoints.py`, `test_auth_flow_e2e.py` y `test_system_e2e.py`, sustituir todas las URLs `/api/v1/tenants/{tenant_id}/leads...` y `/api/v1/tenants/{tenant_id}/rules...` por `/api/v1/leads...` y `/api/v1/rules...`, y añadir la cabecera `Authorization: Bearer <token>` en las llamadas que ahora la exigen.

Los tests de ingesta pasan a `/api/v1/intake/{tenant_id}/leads/ingest`.

- [ ] **Step 10: Ejecutar la suite completa**

Run: `uv run pytest -q` (con compose y variables de entorno)
Expected: PASS.

Run: `uv run pytest tests/architecture/ -v`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add -A backend/src backend/tests
git commit -m "refactor(api): derive tenant from the access token instead of the URL path

Removes the {tenant_id} path segment and replaces the role/tenant dependencies
with the domain authorization policy, closing the cross-tenant access paths by
construction."
```

---

## Task 11: Configuración centralizada y composition root

Hoy la configuración se lee con `os.getenv` en tres sitios distintos y el grafo de objetos se construye a trozos entre `main.py` y doce factories.

**Files:**
- Create: `backend/src/infrastructure/config/__init__.py`
- Create: `backend/src/infrastructure/config/settings.py`
- Create: `backend/src/infrastructure/di/__init__.py`
- Create: `backend/src/infrastructure/di/container.py`
- Create: `backend/tests/unit/infrastructure/test_settings.py`
- Modify: `backend/src/infrastructure/main.py:20-46`
- Modify: `backend/src/infrastructure/adapters/input/api/dependencies.py` (completo)

**Interfaces:**
- Consumes: todos los adaptadores creados hasta aquí.
- Produces: `Settings.from_environment() -> Settings` con los campos `database_url`, `jwt_secret`, `jwt_expires_minutes`, `cors_origins`, `webhook_timeout_seconds`. `Container(settings)` con las propiedades `password_hasher`, `token_service`, `clock`, `id_generator`, `assignment_engine`, `file_parser`, `event_publisher`, y el método `unit_of_work()`.

- [ ] **Step 1: Escribir el test de configuración**

Crear `backend/tests/unit/infrastructure/test_settings.py`:

```python
import pytest

from infrastructure.config.settings import Settings


def test_reads_every_value_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("JWT_SECRET", "a-secret")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test,http://b.test")

    settings = Settings.from_environment()

    assert settings.database_url == "postgresql://u:p@host:5432/db"
    assert settings.jwt_secret == "a-secret"
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_missing_database_url_fails_loudly(monkeypatch):
    """A silent fallback is what once let this app write to an unrelated
    in-memory database while a real PostgreSQL container sat empty next to it."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("JWT_SECRET", "a-secret")

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings.from_environment()


def test_missing_jwt_secret_fails_loudly(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings.from_environment()


def test_cors_origins_default_covers_the_bare_localhost_origin(monkeypatch):
    """A browser serving the SPA on port 80 sends `http://localhost` with no
    port, so the default must include it or the preflight fails."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("JWT_SECRET", "a-secret")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    assert "http://localhost" in Settings.from_environment().cors_origins


def test_whitespace_around_origins_is_trimmed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("JWT_SECRET", "a-secret")
    monkeypatch.setenv("CORS_ORIGINS", " http://a.test , http://b.test ")

    assert Settings.from_environment().cors_origins == ["http://a.test", "http://b.test"]
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/unit/infrastructure/test_settings.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'infrastructure.config'`.

- [ ] **Step 3: Implementar la configuración**

Crear `backend/src/infrastructure/config/__init__.py` vacío.

Crear `backend/src/infrastructure/config/settings.py`:

```python
import os
from dataclasses import dataclass, field
from typing import List

# `http://localhost` without a port is what a browser actually sends when the
# SPA is served on port 80; omitting it breaks the CORS preflight.
_DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://localhost,http://localhost:80"


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_expires_minutes: int = 60
    webhook_timeout_seconds: float = 5.0
    cors_origins: List[str] = field(default_factory=list)

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL is required and has no default")

        jwt_secret = os.getenv("JWT_SECRET")
        if not jwt_secret:
            raise ValueError("JWT_SECRET is required and has no default")

        raw_origins = os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
        origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

        return cls(
            database_url=database_url,
            jwt_secret=jwt_secret,
            jwt_expires_minutes=int(os.getenv("JWT_EXPIRES_MINUTES", "60")),
            webhook_timeout_seconds=float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5.0")),
            cors_origins=origins,
        )
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/unit/infrastructure/test_settings.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Escribir el composition root**

Crear `backend/src/infrastructure/di/__init__.py` vacío.

Crear `backend/src/infrastructure/di/container.py`:

```python
from application.ports.output.clock_port import ClockPort
from application.ports.output.file_parser_port import FileParserPort
from application.ports.output.id_generator_port import IdGeneratorPort
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.token_service_port import TokenServicePort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from infrastructure.adapters.output.events.in_memory_event_publisher import InMemoryEventPublisher
from infrastructure.adapters.output.parsers.pandas_file_parser import PandasFileParser
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService
from infrastructure.adapters.output.system_clock import SystemClock
from infrastructure.adapters.output.uuid_generator import UuidGenerator
from infrastructure.config.settings import Settings


class Container:
    """Single place where concrete implementations are chosen and their
    lifetimes decided.

    Stateless adapters are built once and shared; anything holding
    per-transaction state is built on demand. Getting this wrong is what makes
    a round-robin cursor reset on every request."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._database = RawSqlDatabase(dsn=settings.database_url)
        self._password_hasher = BcryptPasswordHasher()
        self._token_service = JwtTokenService(
            secret=settings.jwt_secret,
            expires_minutes=settings.jwt_expires_minutes,
        )
        self._clock = SystemClock()
        self._id_generator = UuidGenerator()
        self._file_parser = PandasFileParser()
        self._event_publisher = InMemoryEventPublisher()

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def database(self) -> RawSqlDatabase:
        return self._database

    @property
    def password_hasher(self) -> PasswordHasherPort:
        return self._password_hasher

    @property
    def token_service(self) -> TokenServicePort:
        return self._token_service

    @property
    def clock(self) -> ClockPort:
        return self._clock

    @property
    def id_generator(self) -> IdGeneratorPort:
        return self._id_generator

    @property
    def file_parser(self) -> FileParserPort:
        return self._file_parser

    @property
    def event_publisher(self) -> InMemoryEventPublisher:
        return self._event_publisher

    def unit_of_work(self) -> UnitOfWorkPort:
        """A fresh unit of work per call: it owns a transaction, which must not
        be shared between requests."""
        return PostgresUnitOfWork(self._database)
```

- [ ] **Step 6: Conectar el composition root al arranque**

En `backend/src/infrastructure/main.py`, reemplazar el bloque `lifespan` (líneas 20-46) por:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = Settings.from_environment()
    container = Container(settings)
    container.database.init_db()

    webhook_handler = WebhookEventHandler(
        webhook_repo=RawSqlWebhookRepository(container.database.get_connection(autocommit=True)),
        webhook_dispatcher=HttpxWebhookDispatcher(timeout=settings.webhook_timeout_seconds),
    )
    container.event_publisher.subscribe(LeadProcessedEvent, webhook_handler.handle_lead_processed)

    app.state.container = container
    yield
    container.database.close()
```

Y sustituir la lectura de CORS de la línea 64 por `settings.cors_origins`. Como el middleware se registra fuera del `lifespan`, mover el registro dentro de una función `create_app()` o leer la configuración a nivel de módulo con `Settings.from_environment()`; elegir la segunda, que es un cambio menor:

```python
_settings = Settings.from_environment()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 7: Reescribir las factories para consultar el contenedor**

En `dependencies.py`, sustituir `get_db` y `get_uow` y añadir el acceso al contenedor:

```python
def get_container(request: Request) -> Container:
    return request.app.state.container


def get_uow(container: Container = Depends(get_container)) -> UnitOfWorkPort:
    return container.unit_of_work()


def get_token_service(container: Container = Depends(get_container)) -> TokenServicePort:
    return container.token_service
```

Y cada factory de caso de uso pasa a tomar sus colaboradores del contenedor. Ejemplo:

```python
def get_login_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> LoginInputPort:
    return LoginUseCase(
        uow=uow,
        password_hasher=container.password_hasher,
        token_service=container.token_service,
    )
```

Eliminar todos los accesos directos a `request.app.state.file_parser` y `request.app.state.event_publisher`, sustituyéndolos por `container.file_parser` y `container.event_publisher`.

- [ ] **Step 8: Ejecutar la suite completa**

Run: `uv run pytest -q` (con compose y variables de entorno)
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add -A backend/src backend/tests
git commit -m "refactor(infrastructure): add settings module and explicit composition root"
```

---

## Task 12: Migraciones versionadas

El esquema se recrea hoy en cada arranque desde una constante de Python que ha ido acumulando `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. F1 y F2 introducen tablas nuevas y cambian tipos: sin migraciones versionadas, eso es irrepetible.

**Files:**
- Create: `backend/migrations/001_baseline_schema.sql`
- Create: `backend/src/infrastructure/adapters/output/persistence/migration_runner.py`
- Create: `backend/tests/integration/test_migration_runner.py`
- Modify: `backend/src/infrastructure/adapters/output/persistence/connection.py`
- Modify: `backend/src/infrastructure/main.py` (sustituir `init_db()` por el runner)
- Modify: `backend/Dockerfile` (copiar `migrations/`)

**Interfaces:**
- Consumes: `RawSqlDatabase`.
- Produces: `MigrationRunner(database, migrations_dir)` con `apply_pending() -> list[str]` que devuelve los nombres aplicados en esta ejecución.

- [ ] **Step 1: Escribir el test del runner**

Crear `backend/tests/integration/test_migration_runner.py`:

```python
from pathlib import Path

from infrastructure.adapters.output.persistence.migration_runner import MigrationRunner

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def test_applies_every_migration_on_a_fresh_database(test_db):
    applied = MigrationRunner(test_db, _MIGRATIONS_DIR).apply_pending()
    assert "001_baseline_schema.sql" in applied


def test_is_idempotent(test_db):
    """Running twice must be a no-op, or every container restart would fail."""
    runner = MigrationRunner(test_db, _MIGRATIONS_DIR)
    runner.apply_pending()
    assert runner.apply_pending() == []


def test_records_what_it_applied(test_db):
    MigrationRunner(test_db, _MIGRATIONS_DIR).apply_pending()
    with test_db.get_connection(autocommit=True) as conn:
        rows = conn.execute("SELECT name FROM schema_migrations ORDER BY name").fetchall()
    assert [row["name"] for row in rows] == sorted(
        path.name for path in _MIGRATIONS_DIR.glob("*.sql")
    )


def test_creates_the_expected_tables(test_db):
    MigrationRunner(test_db, _MIGRATIONS_DIR).apply_pending()
    with test_db.get_connection(autocommit=True) as conn:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()
    names = {row["table_name"] for row in rows}
    assert {"leads", "scoring_rules", "routing_rules", "agents", "webhook_configs"} <= names
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/integration/test_migration_runner.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named '...migration_runner'`.

- [ ] **Step 3: Extraer el esquema actual a la migración base**

Crear `backend/migrations/001_baseline_schema.sql` con el contenido del DDL que hoy vive en `connection.py:10-78`, consolidando los tres `ALTER TABLE` dentro de la definición de `agents`:

```sql
CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT NOT NULL,
    budget DOUBLE PRECISION NOT NULL,
    industry TEXT NOT NULL,
    custom_attributes TEXT,
    phone TEXT,
    score INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    assigned_agent_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scoring_rules (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    field TEXT NOT NULL,
    operator TEXT NOT NULL,
    value TEXT NOT NULL,
    score_delta INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS routing_rules (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    min_score INTEGER NOT NULL,
    target_team TEXT NOT NULL,
    assignment_strategy TEXT NOT NULL,
    target_agent_ids TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    team TEXT NOT NULL,
    active_leads_count INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    role TEXT NOT NULL DEFAULT 'AGENT',
    hashed_password TEXT,
    tenant_id TEXT
);

CREATE TABLE IF NOT EXISTS webhook_configs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    target_url TEXT NOT NULL,
    secret_token TEXT NOT NULL
);
```

Los tipos siguen siendo los actuales. Corregirlos a `UUID`, `TIMESTAMPTZ`, `NUMERIC` y `JSONB` corresponde a F1, donde hay tests funcionales que cubren esas columnas; hacerlo aquí sería un cambio sin red de seguridad.

- [ ] **Step 4: Implementar el runner**

Crear `backend/src/infrastructure/adapters/output/persistence/migration_runner.py`:

```python
from pathlib import Path
from typing import List

_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


class MigrationRunner:
    """Applies numbered .sql files once each, in filename order.

    Deliberately not Alembic: that would pull in SQLAlchemy, which this project
    rules out."""

    def __init__(self, database, migrations_dir: Path) -> None:
        self._database = database
        self._migrations_dir = Path(migrations_dir)

    def apply_pending(self) -> List[str]:
        applied: List[str] = []
        with self._database.get_connection(autocommit=True) as conn:
            conn.execute(_TRACKING_TABLE)
            rows = conn.execute("SELECT name FROM schema_migrations").fetchall()
            already_applied = {row["name"] for row in rows}

            for path in sorted(self._migrations_dir.glob("*.sql")):
                if path.name in already_applied:
                    continue
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,)
                )
                applied.append(path.name)
        return applied
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/integration/test_migration_runner.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 6: Sustituir init_db por el runner en el arranque**

En `backend/src/infrastructure/main.py`, dentro de `lifespan`, reemplazar `container.database.init_db()` por:

```python
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
    MigrationRunner(container.database, migrations_dir).apply_pending()
```

En `backend/src/infrastructure/adapters/output/persistence/connection.py`, dejar `init_db()` como un alias que delega en el runner, para no romper la fixture `test_db` de la Task 1:

```python
    def init_db(self) -> None:
        """Kept as the single entry point used by tests; the schema itself now
        lives in versioned .sql files."""
        from pathlib import Path

        from infrastructure.adapters.output.persistence.migration_runner import MigrationRunner

        migrations_dir = Path(__file__).resolve().parents[5] / "migrations"
        MigrationRunner(self, migrations_dir).apply_pending()
```

El índice sale de contar los directorios desde `connection.py` hasta `backend/`: `parents[0]`=persistence, `[1]`=output, `[2]`=adapters, `[3]`=infrastructure, `[4]`=src, `[5]`=backend. Confirmarlo antes de continuar:

Run: `uv run python -c "from pathlib import Path; p = Path('backend/src/infrastructure/adapters/output/persistence/connection.py').resolve(); print(p.parents[5])"`
Expected: la ruta absoluta de `backend/`.

Eliminar la constante con el DDL de `connection.py`.

- [ ] **Step 7: Copiar las migraciones a la imagen**

En `backend/Dockerfile`, añadir junto al `COPY` de `src`:

```dockerfile
COPY --from=builder /app/migrations /app/migrations
```

- [ ] **Step 8: Verificar de punta a punta**

Run: `docker compose down -v && docker compose up -d --build`
Run: `docker compose logs backend | tail -20`
Expected: sin excepciones. El contenedor pasa a `healthy`.

Run: `docker compose exec db psql -U postgres -d leads_db -c "SELECT name FROM schema_migrations"`
Expected: una fila con `001_baseline_schema.sql`.

- [ ] **Step 9: Commit**

```bash
git add backend/migrations/ backend/src/infrastructure/adapters/output/persistence/ backend/src/infrastructure/main.py backend/Dockerfile backend/tests/integration/test_migration_runner.py
git commit -m "feat(persistence): replace startup DDL with versioned SQL migrations"
```

---

## Task 13: Pool de conexiones

Cada bloque `with uow:` abre y cierra una conexión TCP nueva. Una carga de 200 filas produce 200 conexiones secuenciales.

**Files:**
- Modify: `backend/pyproject.toml` (dependencia `psycopg_pool`)
- Modify: `backend/src/infrastructure/adapters/output/persistence/connection.py`
- Create: `backend/tests/integration/test_connection_pool.py`

**Interfaces:**
- Consumes: `Settings`.
- Produces: `RawSqlDatabase(dsn, min_size=1, max_size=10)` con `get_connection(autocommit=False)` sirviendo del pool, y `close()` cerrándolo de verdad.

- [ ] **Step 1: Añadir la dependencia**

En `backend/pyproject.toml`, añadir a `dependencies`:

```toml
    "psycopg-pool>=3.2",
```

Run: `uv sync`
Expected: instala `psycopg-pool`.

- [ ] **Step 2: Escribir el test**

Crear `backend/tests/integration/test_connection_pool.py`:

```python
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase


def test_connections_are_reused_across_calls(test_db):
    """Two sequential borrows must return the same underlying backend process,
    which is the observable difference between a pool and connect-per-call."""
    with test_db.get_connection(autocommit=True) as conn:
        first_pid = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
    with test_db.get_connection(autocommit=True) as conn:
        second_pid = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
    assert first_pid == second_pid


def test_rows_come_back_as_dictionaries(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        row = conn.execute("SELECT 1 AS answer").fetchone()
    assert row["answer"] == 1


def test_close_is_safe_to_call_twice(dsn_of_test_db):
    database = RawSqlDatabase(dsn=dsn_of_test_db)
    database.close()
    database.close()
```

Añadir la fixture auxiliar al final de `backend/tests/conftest.py`:

```python
@pytest.fixture
def dsn_of_test_db() -> str:
    return _test_dsn()
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Run: `uv run pytest tests/integration/test_connection_pool.py -v`
Expected: FAIL en `test_connections_are_reused_across_calls` — sin pool, cada llamada abre un backend distinto y los PID difieren.

- [ ] **Step 4: Implementar el pool**

En `backend/src/infrastructure/adapters/output/persistence/connection.py`, reemplazar la clase `RawSqlDatabase` por:

```python
import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class RawSqlDatabase:
    """Owns a pool of PostgreSQL connections.

    No silent fallback to another database: that is exactly what let this app
    run for a while writing to an unrelated in-memory SQLite instance while a
    real Postgres container sat empty next to it."""

    def __init__(self, dsn: str | None = None, min_size: int = 1, max_size: int = 10) -> None:
        self.dsn = dsn or os.environ["DATABASE_URL"]
        self._pool = ConnectionPool(
            conninfo=self.dsn,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=True,
        )

    @contextmanager
    def get_connection(self, autocommit: bool = False):
        with self._pool.connection() as conn:
            conn.autocommit = autocommit
            yield conn

    def close(self) -> None:
        if not self._pool.closed:
            self._pool.close()
```

`get_connection` pasa a ser un gestor de contexto. Verificar cada consumidor:

Run: `rg -n "get_connection" backend/src backend/tests`

Todo consumidor debe usarlo con `with`. `PostgresUnitOfWork.__enter__` y `__exit__` deben adaptarse para entrar y salir de ese gestor de contexto en lugar de guardar la conexión como atributo suelto.

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/integration/ -v`
Expected: PASS.

Run: `uv run pytest -q` (suite completa)
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src/infrastructure/adapters/output/persistence/ backend/tests/
git commit -m "perf(persistence): serve connections from a pool instead of connecting per transaction"
```

---

## Task 14: Logging estructurado

No hay una sola llamada de logging en todo el backend. Los fallos de webhook se tragan en silencio y un error de base de datos no deja rastro.

**Files:**
- Create: `backend/src/infrastructure/logging_config.py`
- Modify: `backend/src/infrastructure/main.py`
- Modify: `backend/src/infrastructure/adapters/output/http/httpx_webhook_dispatcher.py:32-33`
- Modify: `backend/src/infrastructure/adapters/output/events/in_memory_event_publisher.py:20-24`

**Interfaces:**
- Consumes: nada.
- Produces: `configure_logging(level: str = "INFO") -> None`.

- [ ] **Step 1: Implementar la configuración de logging**

Crear `backend/src/infrastructure/logging_config.py`:

```python
import logging
import os
import sys


def configure_logging(level: str | None = None) -> None:
    """Send everything to stdout in a single line per record, which is what a
    container log collector expects."""
    logging.basicConfig(
        level=(level or os.getenv("LOG_LEVEL", "INFO")).upper(),
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
```

- [ ] **Step 2: Invocarlo al arrancar**

En `backend/src/infrastructure/main.py`, como primera línea del `lifespan`:

```python
    configure_logging()
```

- [ ] **Step 3: Dejar de tragar los fallos de webhook**

En `httpx_webhook_dispatcher.py`, reemplazar el bloque `except Exception: return False` por:

```python
        except Exception:
            _LOGGER.warning("Webhook dispatch to %s failed", target_url, exc_info=True)
            return False
```

Añadir en la cabecera del fichero:

```python
import logging

_LOGGER = logging.getLogger(__name__)
```

- [ ] **Step 4: Aislar los fallos de los manejadores de eventos**

En `in_memory_event_publisher.py`, envolver la invocación de cada manejador:

```python
    def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(type(event), []):
            try:
                handler(event)
            except Exception:
                # A failing side effect must not undo work that is already
                # committed, nor stop the remaining handlers.
                _LOGGER.error(
                    "Handler %s failed for %s", handler, event.event_type, exc_info=True
                )
```

Añadir el logger al fichero igual que en el paso anterior.

- [ ] **Step 5: Escribir el test del aislamiento**

Crear `backend/tests/unit/infrastructure/test_event_publisher_isolation.py`:

```python
from domain.events.lead_events import LeadProcessedEvent
from domain.value_objects.enums import LeadStatus
from infrastructure.adapters.output.events.in_memory_event_publisher import InMemoryEventPublisher


def _explode(event) -> None:
    raise RuntimeError("boom")


def _event() -> LeadProcessedEvent:
    return LeadProcessedEvent(
        tenant_id="t-1",
        lead_id="l-1",
        email="lead@test.com",
        score=35,
        status=LeadStatus.ASSIGNED,
        assigned_agent_id="a-1",
    )


def test_a_failing_handler_does_not_stop_the_others():
    seen = []
    publisher = InMemoryEventPublisher()
    publisher.subscribe(LeadProcessedEvent, _explode)
    publisher.subscribe(LeadProcessedEvent, lambda event: seen.append(event))

    publisher.publish(_event())

    assert len(seen) == 1


def test_a_failing_handler_does_not_propagate_to_the_caller():
    """The lead is already committed by the time events are published, so a
    handler error must not surface as a failed ingestion."""
    publisher = InMemoryEventPublisher()
    publisher.subscribe(LeadProcessedEvent, _explode)

    publisher.publish(_event())
```

- [ ] **Step 6: Ejecutar**

Run: `uv run pytest tests/unit/infrastructure/test_event_publisher_isolation.py -v`
Expected: PASS, 2 tests.

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/infrastructure/ backend/tests/unit/infrastructure/test_event_publisher_isolation.py
git commit -m "feat(infrastructure): add logging and isolate event handler failures"
```

---

## Task 15: Envoltorio de error unificado

Conviven tres formatos de error distintos: el del manejador de dominio, el de `HTTPException` y el de validación de Pydantic.

**Files:**
- Modify: `backend/src/infrastructure/adapters/input/api/exception_handlers.py`
- Create: `backend/tests/e2e/test_error_envelope.py`

**Interfaces:**
- Consumes: `STATUS_BY_ERROR_CODE` (Task 3).
- Produces: manejadores para `RequestValidationError`, `HTTPException` y `Exception`, todos emitiendo `{error, error_code, message, details}`.

- [ ] **Step 1: Escribir el test**

Crear `backend/tests/e2e/test_error_envelope.py`:

```python
from fastapi.testclient import TestClient

from infrastructure.main import app

_REQUIRED_KEYS = {"error", "error_code", "message"}


def test_validation_errors_use_the_common_envelope():
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/login", data={"username": "only-this"})
    assert response.status_code == 422
    body = response.json()
    assert _REQUIRED_KEYS <= set(body)
    assert body["error_code"] == "VALIDATION_ERROR"
    assert isinstance(body["details"], list)


def test_missing_credentials_use_the_common_envelope():
    with TestClient(app) as client:
        response = client.get("/api/v1/agents")
    assert response.status_code == 401
    body = response.json()
    assert _REQUIRED_KEYS <= set(body)
    assert body["error_code"] == "UNAUTHORIZED"


def test_unknown_route_uses_the_common_envelope():
    with TestClient(app) as client:
        response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert _REQUIRED_KEYS <= set(response.json())
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/e2e/test_error_envelope.py -v` (con compose y variables)
Expected: FAIL. FastAPI devuelve hoy `{"detail": [...]}` para validación y `{"detail": "Not authenticated"}` para el 401.

- [ ] **Step 3: Añadir los manejadores**

Añadir a `backend/src/infrastructure/adapters/input/api/exception_handlers.py`, dentro de `add_exception_handlers`:

```python
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "La petición no supera la validación de esquema",
                "details": [
                    {
                        "field": ".".join(str(part) for part in error["loc"][1:]),
                        "code": error["type"],
                        "message": error["msg"],
                    }
                    for error in exc.errors()
                ],
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "error_code": _ERROR_CODE_BY_STATUS.get(exc.status_code, "HTTP_ERROR"),
                "message": str(exc.detail),
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # The message is deliberately generic: internal failures must not leak
        # database or stack details to a client.
        _LOGGER.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": "Se ha producido un error interno",
            },
        )
```

Y en la cabecera del fichero:

```python
import logging

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

_LOGGER = logging.getLogger(__name__)

_ERROR_CODE_BY_STATUS = {
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/e2e/test_error_envelope.py -v`
Expected: PASS, 3 tests.

Run: `uv run pytest -q`
Expected: PASS. Comprobar que `test_ingest_lead_endpoint_invalid_email_validation`, que espera 422, sigue verde: el código de estado no cambia, sólo la forma del cuerpo.

- [ ] **Step 5: Commit**

```bash
git add backend/src/infrastructure/adapters/input/api/exception_handlers.py backend/tests/e2e/test_error_envelope.py
git commit -m "feat(api): unify every error response under a single envelope"
```

---

## Task 16: Arranque reproducible con Docker

**Files:**
- Create: `backend/.dockerignore`, `frontend/.dockerignore`
- Modify: `docker-compose.yml`
- Modify: `backend/Dockerfile`
- Modify: `README.md` (sección de arranque)
- Remove from git: `backend/tests/unit/__pycache__/*.pyc`

**Interfaces:**
- Consumes: `Settings` (Task 11), `MigrationRunner` (Task 12).
- Produces: `docker compose up` deja el sistema utilizable; `docker compose --profile test run --rm backend-test` ejecuta la suite completa.

- [ ] **Step 1: Sacar de git los bytecode versionados**

```bash
git rm -r --cached backend/tests/unit/__pycache__
git commit -m "chore: stop tracking compiled bytecode"
```

El `.gitignore` ya tiene la regla; el fichero entró antes de que existiera.

- [ ] **Step 2: Crear los .dockerignore**

Crear `backend/.dockerignore`:

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
.env
```

`tests/` **no** se excluye: la etapa de pruebas del paso 4 los necesita dentro de la imagen. La etapa `runner`, que es la que se despliega, copia únicamente `src/`, `migrations/` y el entorno virtual, así que los tests nunca llegan a la imagen final.

Lo que sí importa excluir es `.venv/`: el `COPY . .` del builder lo sobreescribiría con el entorno virtual del host, que apunta a un intérprete que no existe dentro del contenedor.

Crear `frontend/.dockerignore`:

```
node_modules/
dist/
.vite/
.env
```

- [ ] **Step 3: Correr el backend como usuario sin privilegios**

En `backend/Dockerfile`, antes del `CMD` de la etapa runner:

```dockerfile
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
```

- [ ] **Step 4: Corregir el compose**

En `docker-compose.yml`:

Añadir a las variables de entorno del servicio `backend`:

```yaml
      CORS_ORIGINS: http://localhost:5173,http://localhost,http://localhost:80
      LOG_LEVEL: INFO
```

Cambiar la dependencia del servicio `frontend`:

```yaml
    depends_on:
      backend:
        condition: service_healthy
```

El puerto de PostgreSQL se publica como `5433:5432` (ya aplicado antes de empezar el plan, porque el 5432 del host estaba ocupado por otro proyecto). Dentro de la red de compose el puerto sigue siendo 5432, así que `DATABASE_URL` del backend no cambia; sólo cambia la cadena de conexión desde el host.

Los tres `container_name` fijos se eliminaron por el mismo motivo: impedían que dos copias del repositorio coexistieran.

Añadir el servicio de pruebas:

```yaml
  backend-test:
    profiles: ["test"]
    build:
      context: ./backend
      dockerfile: Dockerfile
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://postgres:postgrespassword@db:5432/leads_test
      TEST_DATABASE_URL: postgresql://postgres:postgrespassword@db:5432/leads_test
      JWT_SECRET: test-secret-do-not-use-in-production
    command: ["pytest", "-q"]
```

El servicio de pruebas necesita las dependencias de desarrollo, que la etapa `runner` instala con `--no-dev`. Añadir una etapa dedicada al final de `backend/Dockerfile`:

```dockerfile
FROM builder AS test
WORKDIR /app
RUN uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH"
CMD ["pytest", "-q"]
```

Hereda de `builder`, que ya hizo `COPY . .`, así que `src/`, `tests/`, `conftest.py` y `migrations/` están presentes. El `uv sync --frozen` sin `--no-dev` añade pytest.

Apuntar el servicio a esa etapa:

```yaml
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: test
```

- [ ] **Step 5: Verificar el arranque limpio**

```bash
docker compose down -v
docker compose up -d --build
```

Run: `docker compose ps`
Expected: `db` y `backend` en `healthy`, `frontend` en `running`.

Run: `curl -s http://localhost:8000/health`
Expected: `{"status":"ok"}`

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost/`
Expected: `200`

Run: `docker compose logs backend | grep -i -E "error|traceback"`
Expected: sin resultados.

- [ ] **Step 6: Verificar la suite dentro de Docker**

Run: `docker compose --profile test run --rm backend-test`
Expected: PASS en toda la suite.

- [ ] **Step 7: Actualizar el README**

Sustituir la sección de arranque de `README.md` por instrucciones que reflejen la realidad: la variable `DATABASE_URL` es obligatoria para la suite completa, el conteo de tests real, y los comandos de los perfiles.

```markdown
### Ejecución con Docker Compose

    docker compose up --build -d

- Frontend: http://localhost
- API (Swagger UI): http://localhost:8000/docs

### Ejecución de la suite de pruebas

Sin infraestructura (dominio y casos de uso):

    cd backend && uv run pytest -m unit

Suite completa, dentro de Docker:

    docker compose --profile test run --rm backend-test

El puerto 5432 se publica al host para poder ejecutar los tests de integración
desde fuera del contenedor. Si ya tienes un PostgreSQL local escuchando ahí,
cambia el mapeo en `docker-compose.yml`.
```

- [ ] **Step 8: Commit**

```bash
git add backend/.dockerignore frontend/.dockerignore backend/Dockerfile docker-compose.yml README.md
git commit -m "chore(docker): add dockerignore files, non-root user, test profile and healthy dependency"
```

---

## Verificación final de F0

- [ ] **Guardián de arquitectura en verde**

Run: `cd backend && uv run pytest tests/architecture/ -v`
Expected: PASS, 4 tests.

- [ ] **Unitarios sin infraestructura**

Run: `cd backend && env -u DATABASE_URL -u JWT_SECRET uv run pytest -m unit -q`
Expected: PASS. Ni una sola variable de entorno necesaria.

- [ ] **Suite completa en Docker**

Run: `docker compose --profile test run --rm backend-test`
Expected: PASS.

- [ ] **Arranque de cero**

Run: `docker compose down -v && docker compose up -d --build && sleep 20 && docker compose ps`
Expected: `db` y `backend` en `healthy`.

- [ ] **Sin restos de la estructura antigua**

Run: `rg -n "infrastructure.security|require_role|verify_tenant_access|status_code=" backend/src`
Expected: sin resultados en `backend/src` salvo los `status_code` de las respuestas de FastAPI en `exception_handlers.py`.

---

## Notas para quien ejecute el plan

**Requisito previo de cada tarea con base de datos.** Levantar `docker compose up -d db` y exportar:

```bash
export DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export TEST_DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export JWT_SECRET=test-secret-do-not-use-in-production
```

**Orden.** Las tareas 1 y 2 preceden a todo. Las 3 a 7 son la secuencia que pone el guardián de arquitectura en verde y deben ejecutarse en orden. Las 8 a 16 dependen de que las anteriores estén cerradas, pero entre ellas sólo hay una dependencia real: la 12 (migraciones) antes que la 16 (Docker).

**Criterio de parada.** Si un paso "verificar que falla" produce un fallo distinto del descrito, detenerse y reportar. Un fallo inesperado significa que el diagnóstico de partida era incorrecto, y seguir adelante construiría sobre una premisa falsa.

**Qué no se toca en F0.** El motor de asignación, el modelo de `Lead`, los tipos de las columnas y los defectos funcionales listados en §2.3 del spec permanecen intactos. Corregirlos aquí significaría hacerlo sin los tests funcionales que los cubren, que llegan en F1.
