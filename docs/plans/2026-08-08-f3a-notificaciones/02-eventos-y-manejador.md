# Tarea 2 — Los eventos y el manejador

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Crea los cuatro eventos con consumidor y el manejador que los convierte en avisos. **Es la tarea que
demuestra los criterios de aceptación 1 a 4 y el 8**, que es el que justifica que el manejador abra
su propia transacción.

## Ficheros

**Crear:**

| Fichero | Contenido |
|---|---|
| `backend/src/domain/events/notification_events.py` | Los cuatro eventos |
| `backend/src/application/handlers/notification_handler.py` | El manejador |
| `backend/tests/unit/application/test_notification_handler.py` | Los tests |

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/application/use_cases/ingest_lead_use_case.py` | Publica tres de los cuatro |
| `backend/src/application/use_cases/lead_lifecycle_use_cases.py` | `AssignLeadUseCase` publica asignación y reasignación |
| `backend/src/application/ports/input/lead_lifecycle_use_case_ports.py` | Si la firma del constructor está en el ABC |
| `backend/src/infrastructure/adapters/input/api/dependencies.py` | `AssignLeadUseCase` recibe el publicador |
| `backend/src/infrastructure/main.py` | Suscribe el manejador a los cuatro eventos |

**Consume de la Tarea 1:** `Notification.create`, `uow.notifications.save`, `NotificationKind`.

**Lee sólo como patrón, si lo necesitas:** `domain/events/lead_events.py`,
`application/handlers/webhook_event_handler.py`.

## Paso 1: los cuatro eventos

`notification_events.py`, con la forma de `lead_events.py` —`@dataclass(kw_only=True)` heredando de
`DomainEvent`—:

```python
@dataclass(kw_only=True)
class LeadAssigned(DomainEvent):
    tenant_id: str
    lead_id: str
    agent_id: str


@dataclass(kw_only=True)
class LeadReassigned(DomainEvent):
    tenant_id: str
    lead_id: str
    agent_id: str
    previous_agent_id: Optional[str] = None


@dataclass(kw_only=True)
class LeadLeftUnassigned(DomainEvent):
    tenant_id: str
    lead_id: str


@dataclass(kw_only=True)
class IntakeRejected(DomainEvent):
    tenant_id: str
    intake_record_id: str
    reason: str
```

Los identificadores viajan como `str`, igual que en `LeadProcessedEvent`: un evento es un mensaje,
no una referencia a objetos vivos.

**No crees los otros cuatro de §6.15** (`LeadQualified`, `LeadDisqualified`, `LeadDiscarded`,
`IntakePromoted`). Nadie los escucha (N3).

## Paso 2: el manejador

`notification_handler.py`. Recibe una **factoría** de unidad de trabajo, no una unidad ya abierta:
se suscribe una vez en el arranque y vive tanto como el proceso, así que no puede quedarse con la
transacción de una petición.

```python
class NotificationHandler:
    """Turns the events of a run into notices for whoever must act.

    Opens its own unit of work on purpose: the event arrives once the use
    case's transaction already committed, and that is the point — a notice
    that fails must not undo a lead that was saved."""

    def __init__(self, uow_factory: Callable[[], UnitOfWorkPort]) -> None:
        self.uow_factory = uow_factory

    def handle_lead_assigned(self, event: LeadAssigned) -> None:
        self._notify(
            tenant_id=event.tenant_id,
            recipient_ids=[event.agent_id],
            kind=NotificationKind.LEAD_ASSIGNED,
            message="Tienes un lead nuevo asignado",
            lead_id=event.lead_id,
        )

    def handle_lead_reassigned(self, event: LeadReassigned) -> None:
        self._notify(
            tenant_id=event.tenant_id,
            recipient_ids=[event.agent_id],
            kind=NotificationKind.LEAD_REASSIGNED,
            message="Te han reasignado un lead",
            lead_id=event.lead_id,
        )

    def handle_lead_left_unassigned(self, event: LeadLeftUnassigned) -> None:
        self._notify(
            tenant_id=event.tenant_id,
            recipient_ids=self._managers_of(event.tenant_id),
            kind=NotificationKind.LEAD_LEFT_UNASSIGNED,
            message="Un lead no encontró asesor y espera asignación manual",
            lead_id=event.lead_id,
        )

    def handle_intake_rejected(self, event: IntakeRejected) -> None:
        self._notify(
            tenant_id=event.tenant_id,
            recipient_ids=self._managers_of(event.tenant_id),
            kind=NotificationKind.INTAKE_REJECTED,
            message=f"Un registro de entrada no se pudo interpretar: {event.reason}",
            intake_record_id=event.intake_record_id,
        )
```

`_managers_of` resuelve los destinatarios del gestor:

```python
    def _managers_of(self, tenant_id: str) -> List[str]:
        with self.uow_factory() as uow:
            # Filtered here rather than in a new repository method: an
            # organization has a handful of managers, and the port already
            # answers "everyone in this organization".
            agents = uow.agents.list_by_tenant(UUID(tenant_id), limit=10_000)
        return [
            str(agent.id.value)
            for agent in agents
            if agent.role == AgentRole.MANAGER and agent.is_active
        ]
```

Y `_notify` persiste una notificación por destinatario, en una sola transacción:

```python
    def _notify(self, tenant_id, recipient_ids, kind, message, lead_id=None, intake_record_id=None) -> None:
        if not recipient_ids:
            return
        with self.uow_factory() as uow:
            for recipient_id in recipient_ids:
                uow.notifications.save(Notification.create(
                    tenant_id=tenant_id,
                    recipient_id=recipient_id,
                    kind=kind,
                    message=message,
                    lead_id=lead_id,
                    intake_record_id=intake_record_id,
                ))
```

**Comprueba la firma de `list_by_tenant` en `agent_repository_port.py`** antes de llamarla: tiene
varios parámetros opcionales y el nombre del de límite importa.

`AgentRole` se importa del dominio, que la aplicación sí puede importar. **No importes nada de
`infrastructure`** (C2).

## Paso 3: los puntos de publicación

En `ingest_lead_use_case.py`, tres, todos **fuera** del bloque `with self.uow` —donde ya vive la
publicación de `LeadProcessedEvent`—, para que el commit haya ocurrido:

| Evento | Cuándo |
|---|---|
| `LeadAssigned` | El motor devolvió asesor: `assigned_agent is not None` |
| `LeadLeftUnassigned` | Se llamó a `lead.leave_unassigned()` |
| `IntakeRejected` | Se llamó a `record.reject(...)`, en la rama del `except DomainException` |

El caso de `IntakeRejected` tiene una particularidad: esa rama hace `return` dentro del `with`.
**Guarda lo que necesites en variables locales y publica antes del `return`, después de que el
bloque haya cerrado** — o extrae ese `return` a una variable de resultado. Si publicas dentro del
`with`, un fallo del manejador haría rollback del rechazo, que es exactamente lo que F2d existe para
impedir.

En `lead_lifecycle_use_cases.py`, `AssignLeadUseCase` recibe `event_publisher` opcional en su
constructor —como hace `IngestLeadUseCase`— y publica según la rama que tomó: `LeadReassigned` si
llamó a `reassign_to`, `LeadAssigned` si llamó a `assign_to`. La distinción ya está escrita en el
código, con su comentario.

`dependencies.py` le pasa `container.event_publisher`, igual que a la ingesta.

## Paso 4: la suscripción

En `main.py`, junto a la del webhook que ya existe:

```python
        notification_handler = NotificationHandler(uow_factory=lambda: PostgresUnitOfWork(container.database))
        for event_type, handler in (
            (LeadAssigned, notification_handler.handle_lead_assigned),
            (LeadReassigned, notification_handler.handle_lead_reassigned),
            (LeadLeftUnassigned, notification_handler.handle_lead_left_unassigned),
            (IntakeRejected, notification_handler.handle_intake_rejected),
        ):
            container.event_publisher.subscribe(event_type, handler)
```

**Comprueba cómo construye `get_uow` la unidad de trabajo en `dependencies.py`** y usa la misma
forma: la factoría tiene que producir una unidad nueva por invocación, no reutilizar una.

`InMemoryEventPublisher` ya captura las excepciones de sus manejadores sin propagarlas, así que no
añadas otro `try/except` alrededor de la publicación (N1).

## Tests — `test_notification_handler.py`

Marcador `unit`, con `InMemoryUnitOfWork`. La factoría es `lambda: uow` sobre una instancia
compartida, que es lo que permite inspeccionar lo guardado.

| Caso | Esperado |
|---|---|
| `LeadAssigned` | Una notificación para el asesor, `LEAD_ASSIGNED`, con el `lead_id` |
| `LeadReassigned` | Una para el **nuevo** asesor, `LEAD_REASSIGNED` |
| `LeadLeftUnassigned` con dos gestores activos | **Dos** notificaciones, una por gestor |
| `LeadLeftUnassigned` con un gestor inactivo y otro activo | **Una**, la del activo |
| `LeadLeftUnassigned` sin ningún gestor | Ninguna, y **no lanza** |
| `IntakeRejected` | Una al gestor, con el `intake_record_id` y el motivo dentro del mensaje |
| Un asesor de la organización que no es gestor | **No** recibe los avisos de gestor |

Y el que justifica el diseño, criterio de aceptación 8:

| Caso | Esperado |
|---|---|
| **El repositorio de notificaciones lanza al guardar, durante una ingesta completa** | El lead **se guarda igual**, el registro queda `PROMOTED`, y la ingesta no propaga la excepción |

Ese se escribe con un doble de `NotificationRepositoryPort` cuyo `save` lanza `RuntimeError`,
publicando por el `InMemoryEventPublisher` real —no un `Mock`—, porque lo que se está probando es
justamente que el publicador absorba el fallo. **Si no puedes escribirlo, la publicación quedó dentro
de la transacción y eso es un fallo de esta tarea.**

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q
cd .. && ./scripts/verify-e2e.sh            # debe seguir verde: la ingesta no cambia de contrato
git commit -m "feat(application): tell whoever must act that something happened"
```
