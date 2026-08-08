# Tarea 5b — CRUD de orígenes

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Aditiva: no cambia ninguna ruta existente. Es lo que permite al gestor responder «¿de dónde vienen
mis leads?», criterio de aceptación 5 de la fase.

## Ficheros

**Crear:**

| Fichero | Contenido |
|---|---|
| `backend/src/application/ports/input/lead_source_use_case_ports.py` | Los cuatro ABC |
| `backend/src/application/use_cases/lead_source_use_cases.py` | Los cuatro casos de uso |
| `backend/src/infrastructure/adapters/input/api/source_router.py` | El router |
| `backend/tests/e2e/test_source_endpoints.py` | Los tests |

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/application/dtos/commands.py` | `CreateLeadSourceCommand`, `UpdateLeadSourceCommand`, `LeadSourcesPageResult` |
| `backend/src/application/dtos/queries.py` | `GetLeadSourcesQuery` |
| `backend/src/domain/entities/lead_source.py` | Falta `activate()`; hoy sólo existe `deactivate()` |
| `backend/src/application/ports/output/lead_repository_port.py` | Falta `count_by_source`, que `SOURCE_IN_USE` necesita |
| `backend/src/infrastructure/adapters/output/persistence/raw_sql_lead_repository.py` | Implementa `count_by_source` |
| `backend/tests/unit/mocks/in_memory_lead_repo.py` | Implementa `count_by_source` |
| `backend/src/infrastructure/adapters/input/api/schemas.py` | Los tres esquemas + el paginado |
| `backend/src/infrastructure/adapters/input/api/dependencies.py` | Cuatro proveedores |
| `backend/src/infrastructure/main.py` | Import y `include_router` |

**Lee sólo si lo necesitas** (son el patrón a copiar, no material de estudio):
`sales_group_use_cases.py`, `sales_group_router.py`, `tests/e2e/test_agent_endpoints.py`.

## Lo que ya existe y no debes rehacer

`LeadSourceRepositoryPort` está completo (`src/application/ports/output/lead_source_repository_port.py`):

```python
def save(self, source: LeadSource) -> LeadSource: ...
def get_by_id_and_tenant(self, source_id: UUID, tenant_id: UUID) -> Optional[LeadSource]: ...
def get_by_kind(self, tenant_id: UUID, kind: LeadSourceKind) -> Optional[LeadSource]: ...
def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[LeadSource]: ...
def delete(self, source_id: UUID, tenant_id: UUID) -> bool: ...
```

Se alcanza como `uow.sources`. **No tiene `count_by_tenant`**, y no se lo añadas: para el total de la
página usa el mismo idioma que `sales_group_use_cases.py:24`, una constante
`_EFFECTIVELY_UNBOUNDED = 10_000` y `len()` sobre el listado. Una organización tiene un puñado de
orígenes; añadir un método al puerto y a sus dos adaptadores para contar cuatro filas no se paga.

La entidad `LeadSource` (`src/domain/entities/lead_source.py`) ya trae `create()`, `rename()`,
`update_mapping()` y `deactivate()`. **No tiene `secret_hash`**: esa columna existe en la tabla para
que F3b autentique fuentes externas por firma, pero la entidad no la carga, así que no hay nada que
pueda filtrarse por una respuesta. No inventes un campo para luego ocultarlo.

`CreateTenantUseCase` ya siembra los dos orígenes automáticos (`MANUAL_FORM` y `FILE_UPLOAD`) al dar
de alta una organización.

## Paso 1: `activate()` en la entidad

`LeadSource` tiene `deactivate()` pero no su simétrico, y el `PATCH` necesita ambos sentidos.
En `lead_source.py`, junto a `deactivate()`:

```python
    def activate(self) -> None:
        self.is_active = True
        self._touch()
```

## Paso 2: `count_by_source` en el repositorio de leads

`DELETE` sobre un origen con leads debe fallar con `SOURCE_IN_USE`. Sin la comprobación, la clave
foránea `leads.source_id` (migración 005) revienta con un error de base de datos que sale como 500.
Aquí no vale el truco de `_EFFECTIVELY_UNBOUNDED`: los leads sí son muchos.

En `lead_repository_port.py`, junto a `count_by_tenant`:

```python
    @abstractmethod
    def count_by_source(self, tenant_id: UUID, source_id: UUID) -> int:
        ...
```

En `raw_sql_lead_repository.py`, con marcadores `%s` (C3), copiando el estilo de `count_by_tenant`:

```sql
SELECT COUNT(*) AS total FROM leads WHERE tenant_id = %s AND source_id = %s
```

Y en `tests/unit/mocks/in_memory_lead_repo.py` la versión equivalente sobre el diccionario interno.
**Los tres van juntos:** dejar el ABC sin una de sus dos implementaciones rompe la suite entera.

## Paso 3: DTOs

En `commands.py`, con el estilo de `CreateSalesGroupCommand` (`@dataclass(frozen=True)`):

```python
@dataclass(frozen=True)
class CreateLeadSourceCommand:
    tenant_id: UUID
    name: str
    kind: str
    field_mapping: Optional[Dict[str, str]] = None


@dataclass(frozen=True)
class UpdateLeadSourceCommand:
    tenant_id: UUID
    source_id: UUID
    # None-means-unchanged, misma convención que UpdateSalesGroupCommand.
    name: Optional[str] = None
    field_mapping: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None


@dataclass(frozen=True)
class LeadSourcesPageResult:
    items: List["LeadSource"]
    total: int
```

`kind` viaja como `str` y no como `LeadSourceKind`: los DTO de la aplicación no importan enums del
dominio en este repositorio — mira `CreateSalesGroupCommand.default_strategy`, que hace lo mismo.

En `queries.py`:

```python
@dataclass(frozen=True)
class GetLeadSourcesQuery:
    tenant_id: UUID
    limit: int = 100
    offset: int = 0
```

## Paso 4: puertos de entrada

En `lead_source_use_case_ports.py`, calcado de `sales_group_use_case_ports.py`:

```python
class CreateLeadSourceInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateLeadSourceCommand) -> LeadSource: ...


class GetLeadSourcesInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetLeadSourcesQuery) -> LeadSourcesPageResult: ...


class UpdateLeadSourceInputPort(ABC):
    @abstractmethod
    def execute(self, command: UpdateLeadSourceCommand) -> LeadSource: ...


class DeleteLeadSourceInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, source_id: UUID) -> None: ...
```

`Delete` recibe argumentos sueltos y no un comando: es la convención que ya sigue
`DeleteSalesGroupInputPort`.

## Paso 5: casos de uso

En `lead_source_use_cases.py`. El helper de C5 primero, copiando `_get_owned_group`:

```python
def _get_owned_source(uow: UnitOfWorkPort, tenant_id: UUID, source_id: UUID) -> LeadSource:
    """Un origen de otra organización debe leerse como inexistente, nunca como
    un 403 que confirmaría que existe en otro sitio."""
    source = uow.sources.get_by_id_and_tenant(source_id, tenant_id)
    if source is None:
        raise DomainException("El origen no existe", error_code="SOURCE_NOT_FOUND")
    return source
```

`SOURCE_NOT_FOUND` es el mismo código que ya usa `IngestLeadUseCase.resolve_source_id`. Reutilízalo,
no crees uno nuevo.

| Caso de uso | Comportamiento |
|---|---|
| `CreateLeadSourceUseCase` | Rechaza nombre repetido en la organización con `SOURCE_ALREADY_EXISTS`, comparando contra `list_by_tenant(..., limit=_EFFECTIVELY_UNBOUNDED)`. Construye con `LeadSource.create(...)` y devuelve `uow.sources.save(source)` |
| `GetLeadSourcesUseCase` | `list_by_tenant(query.tenant_id, limit=query.limit, offset=query.offset)` para los items, y un segundo listado sin paginar para el total |
| `UpdateLeadSourceUseCase` | `_get_owned_source`, luego `rename()` / `update_mapping()` / `activate()` o `deactivate()` sólo para los campos no nulos, y `save` |
| `DeleteLeadSourceUseCase` | `_get_owned_source`, luego `count_by_source`; si es > 0 lanza `DomainException(error_code="SOURCE_IN_USE")`; si no, `uow.sources.delete(source_id, tenant_id)` |

Todos abren `with self.uow:` como primera línea de `execute`.

La unicidad del nombre la garantiza además `UNIQUE (tenant_id, name)` en la migración 005. La
comprobación en el caso de uso existe igualmente porque el repositorio in-memory de los tests
unitarios no tiene esa restricción, y el mensaje de error de Postgres saldría como 500.

## Paso 6: esquemas

En `schemas.py`, junto a los de grupo:

```python
class LeadSourceCreate(BaseModel):
    name: str
    kind: LeadSourceKind
    field_mapping: Optional[Dict[str, str]] = None

class LeadSourceUpdate(BaseModel):
    name: Optional[str] = None
    field_mapping: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None

class LeadSourceResponse(BaseModel):
    id: str
    name: str
    kind: str
    field_mapping: Dict[str, str]
    is_active: bool
    created_at: datetime

class PaginatedSourcesResponse(BaseModel):
    items: List[LeadSourceResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
```

`kind` entra tipado como enum (Pydantic valida el valor en el borde) y sale como `str`, igual que
`SalesGroupResponse.default_strategy`.

## Paso 7: router y cableado

`source_router.py` copia la forma de `sales_group_router.py`, incluido el helper `_to_response` y el
**doble decorador** de las rutas de colección, que evita el redirect 307 de FastAPI:

```python
@router.post("", response_model=LeadSourceResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=LeadSourceResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
```

| Método | Ruta | Acceso |
|---|---|---|
| `GET`·`POST` | `/api/v1/sources` | Gestor |
| `PATCH`·`DELETE` | `/api/v1/sources/{source_id}` | Gestor |

Cada endpoint lleva `context: RequestContext = Depends(require_organization_manager)` y saca la
organización de `context.tenant_id` (C4). `DELETE` devuelve `204`.

En `dependencies.py`, cuatro proveedores de una línea con el patrón de
`get_create_sales_group_use_case`:

```python
def get_create_lead_source_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateLeadSourceInputPort:
    return CreateLeadSourceUseCase(uow=uow)
```

En `main.py`, junto a los demás:

```python
app.include_router(source_router, prefix="/api/v1/sources", tags=["Sources"])
```

`container.py` **no** se toca: el cableado de casos de uso vive en `dependencies.py`.

## Tests — `test_source_endpoints.py`

Sigue la forma de `test_agent_endpoints.py`: `TestClient(app)`, un gestor por organización y
`Authorization: Bearer`.

| Caso | Esperado |
|---|---|
| Una organización recién creada lista sus dos orígenes automáticos | `200` con `MANUAL_FORM` y `FILE_UPLOAD` |
| Crear un origen | `201`, y aparece en el listado |
| Crear con nombre repetido en la misma organización | `SOURCE_ALREADY_EXISTS`, y el listado no crece |
| El mismo nombre en **otra** organización | `201`: la unicidad es por organización |
| `PATCH` y `DELETE` de un origen de otra organización | **404** en ambos. No hay `GET` de detalle: la superficie del Paso 7 sólo expone la colección |
| `PATCH` con `is_active: false` y luego `true` | El campo cambia en ambos sentidos |
| Borrar un origen sin leads | `204` |
| Borrar un origen con un lead ingerido | `SOURCE_IN_USE`, no un 500 |
| Un asesor (`AGENT`) llama a cualquiera de las cuatro | `403` |

Para el caso de `SOURCE_IN_USE` necesitas un lead real: ingiere uno por
`POST /api/v1/intake/leads/ingest` con el token del gestor, que la Tarea 5a dejó autenticado, y
borra después el origen `MANUAL_FORM`.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
./scripts/verify-e2e.sh
git commit -m "feat(api): let the manager see and edit where leads come from"
```
