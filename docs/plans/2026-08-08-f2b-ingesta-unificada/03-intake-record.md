# Tarea 3 — `IntakeRecord` e `IntakeError`

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

**Estado: ✅ cerrada en `6d24369`.** Se conserva como registro de lo que se pidió.

**Ficheros:**
- Crear: `src/domain/value_objects/intake_record_id.py`,
  `src/domain/entities/intake_record.py`,
  `src/application/ports/output/intake_record_repository_port.py`,
  `src/infrastructure/adapters/output/persistence/raw_sql_intake_record_repository.py`,
  `tests/unit/domain/test_intake_record.py`, `tests/integration/test_intake_record_repo.py`
- Modificar: `src/domain/value_objects/enums.py`, `src/domain/value_objects/__init__.py`,
  `src/application/ports/output/unit_of_work_port.py`,
  `src/infrastructure/adapters/output/persistence/postgres_unit_of_work.py`

**Consume de T1:** las tablas `intake_records` e `intake_errors` ya existen en la migración 005; no
escribas una migración nueva.

**Produce (lo usa T4 y T5):** `IntakeRecord`, `IntakeError`, `IntakeRecordStatus`,
`uow.intake_records`.

## Paso 1: el estado

En `enums.py`:

```python
class IntakeRecordStatus(str, Enum):
    """What happened to a payload after it arrived."""

    PENDING = "PENDING"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    DISCARDED = "DISCARDED"
```

`src/domain/value_objects/intake_record_id.py` — mismo procedimiento que `LeadSourceId` en T1:
copia el patrón exacto de `src/domain/value_objects/lead_id.py` cambiando el nombre de la clase a
`IntakeRecordId`. Léelo primero; no inventes una variante. Expórtalo en
`src/domain/value_objects/__init__.py`.

## Paso 2: `IntakeError`

Value object inmutable, en el mismo fichero que la entidad porque no se usa fuera de ella:

```python
@dataclass(frozen=True)
class IntakeError:
    """Why one field of a payload could not be interpreted.

    Per-field rather than one message per record: a manager fixing a CSV column
    mapping needs to know which column, not that "the row failed"."""

    field: str
    message: str
    received_value: Optional[str] = None
    error_code: Optional[str] = None
```

## Paso 3: la entidad

```python
@dataclass
class IntakeRecord:
    id: IntakeRecordId
    tenant_id: TenantId
    source_id: LeadSourceId
    payload: Dict[str, Any]
    status: IntakeRecordStatus = IntakeRecordStatus.PENDING
    errors: List[IntakeError] = field(default_factory=list)
    lead_id: Optional[LeadId] = None
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None

    @classmethod
    def create(cls, tenant_id, source_id, payload, record_id=None, status=PENDING,
               errors=None, lead_id=None, received_at=None, processed_at=None) -> "IntakeRecord":
        ...

    def promote(self, lead_id: Union[str, UUID, LeadId]) -> None: ...
    def reject(self, errors: List[IntakeError]) -> None: ...
    def discard(self) -> None: ...
```

Transiciones, con la misma disciplina que `Lead` estrenó en F2a (`lead.py:134-189`):

| Método | Desde | Hacia | Rechazo |
|---|---|---|---|
| `promote` | `PENDING`, `REJECTED` | `PROMOTED` | `DomainException(error_code="INVALID_INTAKE_TRANSITION")` |
| `reject` | `PENDING` | `REJECTED` | ídem, y `DomainException(error_code="REJECTION_WITHOUT_ERRORS")` si la lista viene vacía |
| `discard` | `PENDING`, `REJECTED` | `DISCARDED` | `DomainException(error_code="INVALID_INTAKE_TRANSITION")` |

`promote` acepta venir de `REJECTED` a propósito: es el criterio de aceptación 2 del spec —el
gestor corrige lo que falló y lo promueve—. Los tres fijan `processed_at`.

Un registro `PROMOTED` o `DISCARDED` no vuelve atrás por ningún camino: escribe un test por cada
transición prohibida.

## Paso 4: puerto y repositorio

```python
class IntakeRecordRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, record: IntakeRecord) -> IntakeRecord: ...

    @abc.abstractmethod
    def get_by_id_and_tenant(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]: ...

    @abc.abstractmethod
    def list_by_tenant(
        self, tenant_id: UUID, status: Optional[IntakeRecordStatus] = None,
        limit: int = 100, offset: int = 0,
    ) -> List[IntakeRecord]: ...

    @abc.abstractmethod
    def count_by_tenant(self, tenant_id: UUID, status: Optional[IntakeRecordStatus] = None) -> int: ...
```

`save` escribe las dos tablas: `INSERT ... ON CONFLICT (id) DO UPDATE` sobre `intake_records`, y
para los errores **borra e inserta** —`DELETE FROM intake_errors WHERE intake_record_id = %s`
seguido de los `INSERT`—. Es lo correcto aquí: los errores son una lista de valores que pertenece
al registro, no entidades con identidad propia, así que reconciliar fila a fila sería trabajo sin
beneficio.

La lectura recupera los errores con una consulta por registro. **No optimices a un `JOIN`**: la
bandeja pagina de 100 en 100 y el gestor la abre unas pocas veces al día.

Regístralo en el UoW como `self.intake_records` y en el puerto como
`intake_records: IntakeRecordRepositoryPort`.

## Tests

Unitarios: una transición válida y una prohibida por cada método, más el rechazo sin errores.
Integración: guardar un registro con dos errores, releerlo y comprobar que vuelven ambos; volver a
guardar con un solo error y comprobar que quedan uno, no tres.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
git commit -m "feat(domain): persist every payload that arrives, valid or not"
```

---

