# Tarea 5c — La bandeja de entrada

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Es lo que convierte `IntakeRecord` de tabla en producto, y la que cumple el criterio de aceptación 2,
el que justifica la fase entera: *un payload ininterpretable queda en la bandeja con el detalle del
fallo, y el gestor lo corrige y lo promueve*.

**Es la única de las tres tareas de API que toca el dominio.** Lee entero el Paso 1 antes de escribir
nada: la promoción no funciona sin él, y el motivo no es evidente desde el código.

## Ficheros

**Crear:**

| Fichero | Contenido |
|---|---|
| `backend/src/application/ports/input/intake_record_use_case_ports.py` | Los tres ABC |
| `backend/src/application/use_cases/intake_record_use_cases.py` | Los tres casos de uso |
| `backend/tests/e2e/test_intake_inbox.py` | Los tests de extremo a extremo |

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/domain/entities/intake_record.py` | `reject()` debe aceptar REJECTED (Paso 1) |
| `backend/tests/unit/domain/test_intake_record.py` | Hay un test que afirma lo contrario |
| `backend/src/application/use_cases/ingest_lead_use_case.py` | `execute()` gana `existing_record` |
| `backend/src/application/ports/input/ingest_lead_use_case_port.py` | El ABC sigue a su implementación |
| `backend/src/application/dtos/commands.py` | `IntakeRecordsPageResult`, `PromoteIntakeRecordCommand` |
| `backend/src/application/dtos/queries.py` | `GetIntakeRecordsQuery` |
| `backend/src/infrastructure/adapters/input/api/intake_router.py` | Los tres endpoints nuevos |
| `backend/src/infrastructure/adapters/input/api/schemas.py` | Los tres esquemas |
| `backend/src/infrastructure/adapters/input/api/dependencies.py` | Tres proveedores |

`main.py` **no se toca**: el router de intake ya está montado con prefijo `/api/v1/intake` y sus
rutas de ingesta llevan `/leads/` en el propio decorador, precisamente para dejar libre
`/api/v1/intake/records`.

## Lo que ya existe y no debes rehacer

`IntakeRecordRepositoryPort` está completo y se alcanza como `uow.intake_records`:

```python
def save(self, record: IntakeRecord) -> IntakeRecord: ...
def get_by_id_and_tenant(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]: ...
def list_by_tenant(self, tenant_id, status=None, limit=100, offset=0) -> List[IntakeRecord]: ...
def count_by_tenant(self, tenant_id, status=None) -> int: ...
```

La entidad `IntakeRecord` trae `promote(lead_id)`, `reject(errors)` y `discard()`, y el value object
`IntakeError` con `field`, `message`, `received_value` y `error_code`.

`promote()` **ya acepta un registro REJECTED** a propósito (`_REOPENABLE_STATUSES`, línea 14). Un
registro `PROMOTED` o `DISCARDED` no vuelve atrás por ningún camino.

## Paso 1: dos cambios sin los que la promoción no funciona

`PromoteIntakeRecordUseCase` reinterpreta el payload corregido con el mismo pipeline que la ingesta.
Tal como está hoy, eso choca con dos cosas:

**1. `IngestLeadUseCase.execute()` siempre crea un `IntakeRecord` nuevo** (línea 66). Llamarlo desde
la promoción dejaría dos filas en la bandeja por el mismo lead. Gana un parámetro opcional:

```python
    def execute(
        self,
        command: IngestLeadCommand,
        existing_record: Optional[IntakeRecord] = None,
    ) -> LeadProcessedResult:
        assigned_agent = None
        with self.uow:
            # La promoción reutiliza la fila que el gestor está corrigiendo, en
            # vez de abrir otra: la bandeja debe mostrar un intento por payload,
            # no uno por reintento.
            record = existing_record or self.uow.intake_records.save(
                IntakeRecord.create(
                    tenant_id=command.tenant_id,
                    source_id=command.source_id,
                    payload=self._payload_of(command),
                )
            )
```

El resto del método no cambia. `ingest_lead_use_case_port.py` replica la firma nueva en su ABC.

**2. `reject()` sólo acepta PENDING** (línea 82), así que un reintento fallido revienta con
`INVALID_INTAKE_TRANSITION`. Pasa a aceptar los mismos estados que `promote()`:

```python
    def reject(self, errors: List[IntakeError]) -> None:
        # Mismo motivo que promote(): el gestor corrige un registro rechazado y
        # la corrección puede volver a fallar. Ambas transiciones parten de los
        # mismos estados o la bandeja no cierra el ciclo.
        if self.status not in _REOPENABLE_STATUSES:
            raise DomainException(
                f"Cannot reject an intake record from status {self.status.value}",
                error_code="INVALID_INTAKE_TRANSITION",
            )
```

En `tests/unit/domain/test_intake_record.py` hay un test que afirma que rechazar desde REJECTED
falla. **Actualízalo para que afirme lo contrario** —rechazar dos veces sustituye los errores y
mantiene el estado— y deja intactos los que cubren PROMOTED y DISCARDED, que siguen siendo
terminales.

## Paso 2: DTOs

En `commands.py`:

```python
@dataclass(frozen=True)
class PromoteIntakeRecordCommand:
    tenant_id: UUID
    record_id: UUID
    # El payload corregido completo, no un parche: el gestor reenvía el
    # formulario entero desde la bandeja.
    payload: Dict[str, Any]


@dataclass(frozen=True)
class IntakeRecordsPageResult:
    items: List["IntakeRecord"]
    total: int
```

En `queries.py`:

```python
@dataclass(frozen=True)
class GetIntakeRecordsQuery:
    tenant_id: UUID
    status: Optional[str] = None
    limit: int = 100
    offset: int = 0
```

`status` viaja como `str` y el caso de uso lo convierte a `IntakeRecordStatus`: los DTO de la
aplicación no importan enums del dominio en este repositorio.

## Paso 3: casos de uso

En `intake_record_use_cases.py`, con el helper de C5 delante:

```python
def _get_owned_record(uow: UnitOfWorkPort, tenant_id: UUID, record_id: UUID) -> IntakeRecord:
    """Un registro de otra organización debe leerse como inexistente."""
    record = uow.intake_records.get_by_id_and_tenant(record_id, tenant_id)
    if record is None:
        raise DomainException("El registro no existe", error_code="INTAKE_RECORD_NOT_FOUND")
    return record
```

**`GetIntakeRecordsUseCase`** — página de registros con filtro opcional por estado. Devuelve el
payload **y los errores por campo** de cada uno: sin eso el gestor ve que algo falló pero no qué
corregir, que es justo lo que la bandeja existe para evitar. Un `status` desconocido debe salir como
`DomainException(error_code="INVALID_INTAKE_STATUS")`, no como un `ValueError` que acabe en 500.

**`PromoteIntakeRecordUseCase`** — recibe `IngestLeadUseCase` por constructor, igual que los routers
reciben sus casos de uso:

```python
class PromoteIntakeRecordUseCase(PromoteIntakeRecordInputPort):
    def __init__(self, uow: UnitOfWorkPort, ingest: IngestLeadInputPort) -> None:
        self.uow = uow
        self.ingest = ingest
```

Su `execute`:

1. `_get_owned_record(...)` — 404 si es de otra organización
2. Construye un `IngestLeadCommand` con `tenant_id` del contexto, `source_id` **del registro**
   (`record.source_id.value`, no uno nuevo: el lead conserva el canal por el que entró) y los campos
   del payload corregido
3. `self.ingest.execute(command, existing_record=record)`
4. Devuelve el `LeadProcessedResult` tal cual

No llames a `record.promote(...)` ni a `record.reject(...)` desde aquí: `IngestLeadUseCase` ya hace
ambas cosas sobre el registro que le pasas, y duplicarlo provocaría una segunda transición sobre un
registro ya terminal. Un registro `PROMOTED` que se intenta promover otra vez sale por
`INVALID_INTAKE_TRANSITION` desde la entidad, que es el comportamiento correcto.

**`DiscardIntakeRecordUseCase`** — `_get_owned_record(...)`, `record.discard()`, `save`.

Los tres abren `with self.uow:`.

## Paso 4: endpoints

En `intake_router.py`, junto a los de ingesta que 5a dejó autenticados. Mismas dependencias:
`context: RequestContext = Depends(require_organization_manager)`.

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/v1/intake/records?status=REJECTED&limit=&offset=` | Lista paginada, filtro opcional |
| `POST` | `/api/v1/intake/records/{record_id}/promote` | Reintenta con el payload corregido |
| `POST` | `/api/v1/intake/records/{record_id}/discard` | El gestor decide no recuperarlo |

`promote` devuelve `200` con el `LeadProcessedResponse` que ya existe si sale bien, y `400` con el
mismo sobre de error que usa la ingesta (`error`, `error_code`, `message`, `intake_record_id`) si el
payload corregido vuelve a fallar. `discard` devuelve `204`.

En `dependencies.py`, tres proveedores. El de promoción compone dos:

```python
def get_promote_intake_record_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    ingest: IngestLeadInputPort = Depends(get_ingest_lead_use_case),
) -> PromoteIntakeRecordInputPort:
    return PromoteIntakeRecordUseCase(uow=uow, ingest=ingest)
```

## Paso 5: esquemas

En `schemas.py`:

```python
class IntakeErrorResponse(BaseModel):
    field: str
    message: str
    received_value: Optional[str] = None
    error_code: Optional[str] = None

class IntakeRecordResponse(BaseModel):
    id: str
    source_id: str
    status: str
    payload: Dict[str, Any]
    errors: List[IntakeErrorResponse]
    received_at: datetime
    processed_at: Optional[datetime] = None
    lead_id: Optional[str] = None

class IntakeRecordsPageResponse(BaseModel):
    items: List[IntakeRecordResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

class PromoteIntakeRecordRequest(BaseModel):
    payload: Dict[str, Any]
```

## Tests — `test_intake_inbox.py`

El primero recorre el criterio de aceptación 2 completo, en un solo hilo:

1. Ingesta con correo mal formado → **400** con `intake_record_id` no vacío
2. Ese registro aparece en `GET /records?status=REJECTED`, con un error de campo `email` y el
   payload original
3. `POST /records/{id}/promote` con el correo corregido → **200**
4. El registro queda `PROMOTED` con su `lead_id`, el lead existe y es visible por `GET /leads/{id}`
5. **La bandeja sigue teniendo una sola fila para ese payload**, no dos: es lo que demuestra que el
   reintento reutilizó el registro
6. Promover el mismo registro otra vez → `INVALID_INTAKE_TRANSITION`, y no aparece un segundo lead

Y aparte:

| Caso | Esperado |
|---|---|
| Promover con un payload que vuelve a fallar | `400`, el registro sigue `REJECTED` y sus errores son los nuevos |
| Descartar un registro rechazado | `204`, y pasa a `DISCARDED` |
| Descartar uno ya promovido | `INVALID_INTAKE_TRANSITION` |
| Carga masiva mixta (una fila buena, una mala) | Un registro `PROMOTED` y uno `REJECTED` |
| Las tres rutas contra un registro de otra organización | **404** |
| Un asesor (`AGENT`) llama a cualquiera de las tres | `403` |

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q      # el dominio cambió: debe seguir verde sin base de datos
cd .. && ./scripts/verify-e2e.sh
git commit -m "feat(api): open the manager's inbox over what could not be read"
```
