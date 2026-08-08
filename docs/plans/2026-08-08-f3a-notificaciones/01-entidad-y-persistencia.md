# Tarea 1 — La entidad y su persistencia

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Aditiva por completo: crea la entidad, su tabla y su repositorio, sin que nadie la use todavía.

## Ficheros

**Crear:**

| Fichero | Contenido |
|---|---|
| `backend/migrations/008_notifications.sql` | La tabla y sus índices |
| `backend/src/domain/value_objects/notification_id.py` | El identificador |
| `backend/src/domain/entities/notification.py` | La entidad |
| `backend/src/application/ports/output/notification_repository_port.py` | El puerto |
| `backend/src/infrastructure/adapters/output/persistence/raw_sql_notification_repository.py` | El adaptador SQL |
| `backend/tests/unit/domain/test_notification.py` | Tests de la entidad |
| `backend/tests/integration/test_notification_repo.py` | Tests del adaptador |

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/domain/value_objects/enums.py` | `NotificationKind` |
| `backend/src/application/ports/output/unit_of_work_port.py` | Declara `notifications` |
| `backend/src/infrastructure/adapters/output/persistence/postgres_unit_of_work.py` | Instancia el repositorio |
| `backend/tests/unit/mocks/in_memory_uow.py` | `InMemoryNotificationRepository` y su registro |

**Lee sólo como patrón, si lo necesitas:** `lead_source_id.py`, `lead_source.py`,
`raw_sql_lead_source_repository.py`, `migrations/007_composable_rules.sql`.

## Paso 1: la migración

`008_notifications.sql`, idempotente (C9):

```sql
-- One row per notice. The message is stored already composed rather than
-- rebuilt on read: rendering the bell must not need the lead of every notice,
-- and a deleted lead must not break the view.
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    recipient_id UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    lead_id UUID,
    intake_record_id UUID,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL
);

-- The bell asks exactly this: my unread ones, newest first.
CREATE INDEX IF NOT EXISTS idx_notifications_recipient
    ON notifications (recipient_id, is_read, created_at DESC);
```

`lead_id` e `intake_record_id` van **sin `REFERENCES`**: un lead borrado debe dejar la notificación
en pie con su mensaje, y una clave ajena la borraría en cascada o impediría el borrado. Es la
consecuencia deliberada de N2.

## Paso 2: el enumerado y el identificador

En `enums.py`:

```python
class NotificationKind(str, Enum):
    """What happened. Drives the icon and the wording in the interface."""

    LEAD_ASSIGNED = "LEAD_ASSIGNED"
    LEAD_REASSIGNED = "LEAD_REASSIGNED"
    LEAD_LEFT_UNASSIGNED = "LEAD_LEFT_UNASSIGNED"
    INTAKE_REJECTED = "INTAKE_REJECTED"
```

`notification_id.py` copia exactamente el patrón de `lead_source_id.py`.

## Paso 3: la entidad

```python
@dataclass
class Notification:
    id: NotificationId
    tenant_id: TenantId
    recipient_id: AgentId
    kind: NotificationKind
    message: str
    lead_id: Optional[LeadId] = None
    intake_record_id: Optional[IntakeRecordId] = None
    is_read: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

`create()` con la forma de `LeadSource.create` —acepta `str`, `UUID` o el value object para cada
identificador— y valida que el mensaje no esté vacío con
`DomainException(error_code="INVALID_NOTIFICATION_MESSAGE")`: una notificación sin texto no se puede
mostrar, y es un fallo de programación que conviene ver en el test y no en la pantalla.

El comportamiento es uno solo:

```python
    def mark_as_read(self) -> None:
        # Idempotent on purpose: "mark all as read" walks every notice and
        # re-marking one already read is the normal case, not an error.
        self.is_read = True
```

## Paso 4: puerto y adaptadores

```python
class NotificationRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, notification: Notification) -> Notification: ...

    @abc.abstractmethod
    def get_by_id_and_recipient(
        self, notification_id: UUID, recipient_id: UUID
    ) -> Optional[Notification]: ...

    @abc.abstractmethod
    def list_by_recipient(
        self,
        recipient_id: UUID,
        unread_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Notification]: ...

    @abc.abstractmethod
    def count_by_recipient(self, recipient_id: UUID, unread_only: bool = False) -> int: ...

    @abc.abstractmethod
    def mark_all_read(self, recipient_id: UUID) -> int: ...
```

**`get_by_id_and_recipient`, no `get_by_id_and_tenant`.** El aislamiento aquí es por destinatario, no
por organización: dos asesores de la misma organización no deben leerse las notificaciones. C5 se
aplica sobre el destinatario.

`mark_all_read` es un `UPDATE` de una sola sentencia y devuelve `cursor.rowcount`; recorrer las filas
para marcarlas una a una haría N consultas por un contador.

Las tres implementaciones van juntas y **omitir una rompe la suite entera**:

1. `raw_sql_notification_repository.py` — SQL crudo, marcadores `%s` (C3)
2. `InMemoryNotificationRepository` en `in_memory_uow.py`
3. El registro en ambos UoW

En el SQL, `unread_only` se traduce concatenando un fragmento estático, nunca interpolando:

```python
        clauses = ["recipient_id = %s"]
        params: List[Any] = [recipient_id]
        if unread_only:
            clauses.append("is_read = FALSE")
        rows = self.connection.execute(
            f"SELECT * FROM notifications WHERE {' AND '.join(clauses)}"
            " ORDER BY created_at DESC, id LIMIT %s OFFSET %s",
            (*params, limit, offset),
        ).fetchall()
```

El `f-string` compone **sólo nombres de columna fijos escritos en este fichero**, nunca un valor:
todo valor viaja por `%s` (C3). Es el mismo patrón que `raw_sql_intake_record_repository` usa para
sus filtros opcionales.

## Tests

**`test_notification.py`** (marcador `unit`):

| Caso | Esperado |
|---|---|
| `create` deja el aviso sin leer y con su fecha | Estado inicial correcto |
| `create` con mensaje vacío o sólo espacios | `INVALID_NOTIFICATION_MESSAGE` |
| `mark_as_read` sobre uno sin leer | `is_read` verdadero |
| `mark_as_read` dos veces | Sigue verdadero, no lanza |
| `create` acepta `lead_id` como `str`, `UUID` o `LeadId` | Los tres construyen igual |
| `create` sin `lead_id` ni `intake_record_id` | Ambos nulos |

**`test_notification_repo.py`** (marcador `integration`):

| Caso | Esperado |
|---|---|
| Guardar y recuperar | Todos los campos sobreviven, incluidos los nulos |
| `list_by_recipient` con `unread_only` | Sólo las no leídas |
| `count_by_recipient` con y sin filtro | Los dos números |
| `get_by_id_and_recipient` con otro destinatario | `None` |
| `mark_all_read` | Devuelve cuántas marcó, y una segunda llamada devuelve cero |
| Orden de `list_by_recipient` | La más reciente primero |

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q
cd .. && ./scripts/verify-e2e.sh            # nada debería haber cambiado
git commit -m "feat(domain): give an organization somewhere to keep its notices"
```
