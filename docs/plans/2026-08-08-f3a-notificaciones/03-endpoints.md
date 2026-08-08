# Tarea 3 — Los endpoints y el contador

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Aditiva: tres rutas nuevas, ninguna existente cambia. Es lo que convierte las notificaciones que la
Tarea 2 guarda en la campana que el usuario mira.

Demuestra los criterios de aceptación 5, 6 y 7.

## Ficheros

**Crear:**

| Fichero | Contenido |
|---|---|
| `backend/src/application/ports/input/notification_use_case_ports.py` | Los tres ABC |
| `backend/src/application/use_cases/notification_use_cases.py` | Los tres casos de uso |
| `backend/src/infrastructure/adapters/input/api/notification_router.py` | Las tres rutas |
| `backend/tests/e2e/test_notifications.py` | Los tests |

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/application/dtos/queries.py` | `GetNotificationsQuery` |
| `backend/src/application/dtos/commands.py` | `NotificationsPageResult`, `MarkNotificationReadCommand` |
| `backend/src/infrastructure/adapters/input/api/schemas.py` | Dos esquemas |
| `backend/src/infrastructure/adapters/input/api/dependencies.py` | Tres proveedores |
| `backend/src/infrastructure/adapters/input/api/exception_handlers.py` | `NOTIFICATION_NOT_FOUND` → 404 |
| `backend/src/infrastructure/main.py` | Monta el router |

**Consume de tareas previas:** `uow.notifications` con sus cinco métodos.

**Lee sólo como patrón, si lo necesitas:** `source_router.py` y `lead_source_use_cases.py` para la
forma canónica del CRUD, y `lead_router.py` en su ruta `/mine` para cómo se filtra por el actor.

## Paso 1: los DTOs

```python
# queries.py
@dataclass(frozen=True)
class GetNotificationsQuery:
    recipient_id: UUID
    unread_only: bool = False
    limit: int = 100
    offset: int = 0


# commands.py
@dataclass(frozen=True)
class NotificationsPageResult:
    items: List["Notification"]
    total: int
    unread_count: int


@dataclass(frozen=True)
class MarkNotificationReadCommand:
    recipient_id: UUID
    notification_id: UUID
```

**No llevan `tenant_id`.** El aislamiento aquí es por destinatario: `recipient_id` sale del token y
es más restrictivo que la organización. Añadir el tenant daría la falsa impresión de que dos asesores
de la misma organización pueden verse las notificaciones.

## Paso 2: los casos de uso

`GetNotificationsUseCase` devuelve la página **y** el contador de no leídas, que es siempre el total
sin leer del destinatario, **no el de la página**:

```python
    def execute(self, query: GetNotificationsQuery) -> NotificationsPageResult:
        with self.uow:
            items = self.uow.notifications.list_by_recipient(
                query.recipient_id,
                unread_only=query.unread_only,
                limit=query.limit,
                offset=query.offset,
            )
            total = self.uow.notifications.count_by_recipient(
                query.recipient_id, unread_only=query.unread_only
            )
            # Always the recipient's full unread count, never the page's: the
            # bell shows one number and it must not change with pagination.
            unread = self.uow.notifications.count_by_recipient(
                query.recipient_id, unread_only=True
            )
        return NotificationsPageResult(items=items, total=total, unread_count=unread)
```

`MarkNotificationReadUseCase`, con el helper de C5 delante:

```python
def _get_own_notification(uow: UnitOfWorkPort, recipient_id: UUID, notification_id: UUID) -> Notification:
    """La notificación de otro destinatario debe leerse como inexistente."""
    notification = uow.notifications.get_by_id_and_recipient(notification_id, recipient_id)
    if notification is None:
        raise DomainException("La notificación no existe", error_code="NOTIFICATION_NOT_FOUND")
    return notification
```

`MarkAllNotificationsReadUseCase` delega en `mark_all_read` y devuelve cuántas marcó.

## Paso 3: los esquemas y el router

```python
class NotificationResponse(BaseModel):
    id: str
    kind: str
    message: str
    lead_id: Optional[str] = None
    intake_record_id: Optional[str] = None
    is_read: bool
    created_at: datetime


class NotificationsPageResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
    # Travels with the page rather than in its own endpoint: the bell needs
    # the list and the badge at once, and two requests to paint one icon is
    # what turns polling into a problem.
    unread_count: int
```

`NotificationResponse` **no expone `recipient_id` ni `tenant_id`**: quien pregunta ya sabe quién es,
y devolverlos sólo daría material a quien inspeccione la respuesta.

Router nuevo, `notification_router.py`, montado en `main.py` con
`prefix="/api/v1/notifications", tags=["Notifications"]`:

| Método | Ruta en el decorador | Qué hace |
|---|---|---|
| `GET` | `""` y `"/"` | Lista paginada con contador |
| `POST` | `/{notification_id}/read` | Marca una, responde `204` |
| `POST` | `/read-all` | Marca todas, responde `204` |

Los tres con `context: RequestContext = Depends(require_organization_member)` y
`recipient_id=context.actor.id.value`. **No hay parámetro de destinatario en ninguna ruta** (C4).

**Declara `/read-all` ANTES que `/{notification_id}/read`.** FastAPI resuelve por orden de
declaración; al revés, `read-all` entraría por la paramétrica y fallaría al convertir el UUID.

El doble decorador `""` y `"/"` con `include_in_schema=False` en el segundo replica lo que hace
`source_router.py`.

`exception_handlers.py` necesita `"NOTIFICATION_NOT_FOUND": 404` en `STATUS_BY_ERROR_CODE`, **o C5 se
rompe en silencio** devolviendo 400.

## Tests — `test_notifications.py`

La ingesta es asíncrona desde F2d: usa `ingest_and_resolve` de `backend/tests/e2e/_intake_helpers.py`
para provocar los avisos. `TestClient` ejecuta las tareas de fondo antes de devolver el control, así
que la notificación ya existe cuando el `POST` retorna.

| Caso | Esperado |
|---|---|
| Un asesor con un lead asignado consulta sus notificaciones | Una, no leída, con el `lead_id` |
| `unread_count` con tres no leídas y una leída | **3**, y `total` refleja el filtro aplicado |
| `unread_only=true` | Sólo las no leídas |
| Marcar una como leída | `204`, y `unread_count` baja en uno |
| Marcar todas | `204`, y `unread_count` queda en **cero** |
| Marcar todas dos veces | `204` las dos veces, sin error |
| Un asesor consulta y sólo ve las suyas | Las del compañero no aparecen |
| Marcar como leída una notificación de otro asesor | **404**, nunca 403 |
| Un gestor consulta las suyas | Ve las de lead sin asignar y las de ingesta rechazada |
| El administrador de plataforma llama a `GET /notifications` | `403`: no pertenece a ninguna organización |
| Paginar con `limit=1` sobre tres avisos | `has_more` verdadero, y `unread_count` **no** cambia con la página |

El último es el que fija la semántica del contador: es del destinatario, no de la página.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q
cd .. && ./scripts/verify-e2e.sh            # debe seguir verde: nada existente cambia
git commit -m "feat(api): let each user read and clear their own notices"
```
