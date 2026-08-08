# Tarea 1 — El modelo: `IntakeJob`

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Aditiva por completo: crea la entidad y su persistencia, sin que nadie la use todavía. Nada existente
cambia de comportamiento.

## Ficheros

**Crear:**

| Fichero | Contenido |
|---|---|
| `backend/migrations/006_intake_jobs.sql` | Tabla `intake_jobs` y la columna `intake_records.job_id` |
| `backend/src/domain/value_objects/intake_job_id.py` | El identificador |
| `backend/src/domain/entities/intake_job.py` | La entidad y sus transiciones |
| `backend/src/application/ports/output/intake_job_repository_port.py` | El puerto |
| `backend/src/infrastructure/adapters/output/persistence/raw_sql_intake_job_repository.py` | El adaptador SQL |
| `backend/tests/unit/domain/test_intake_job.py` | Tests de la entidad |
| `backend/tests/integration/test_intake_job_repo.py` | Tests del adaptador |

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/domain/value_objects/enums.py` | `IntakeJobStatus` y `IntakeJobKind` |
| `backend/src/domain/entities/intake_record.py` | Gana `job_id` |
| `backend/src/application/ports/output/unit_of_work_port.py` | Declara `intake_jobs` |
| `backend/src/infrastructure/adapters/output/persistence/postgres_unit_of_work.py` | Instancia el repositorio |
| `backend/src/infrastructure/adapters/output/persistence/raw_sql_intake_record_repository.py` | Lee y escribe `job_id` |
| `backend/tests/unit/mocks/in_memory_uow.py` | `InMemoryIntakeJobRepository` y su registro en el UoW |

**Lee sólo como patrón, si lo necesitas:** `intake_record.py`, `lead_source_id.py`,
`raw_sql_intake_record_repository.py`, `migrations/005_lead_sources_and_intake.sql`.

## Paso 1: la migración

`006_intake_jobs.sql`, con el estilo de la 005 —comentarios que explican el porqué, no el qué— y
**idempotente** (C9):

```sql
-- One row per ingestion operation, whatever its size. A single lead is a job of
-- one item: without that, the unit and the bulk paths need two different
-- contracts and the manager's inbox two ways of showing the same thing.
CREATE TABLE IF NOT EXISTS intake_jobs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES lead_sources (id),
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    -- Null until the file is parsed: parsing happens in the background phase,
    -- after the response has already been sent.
    total_items INT,
    succeeded INT NOT NULL DEFAULT 0,
    failed INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ
);

ALTER TABLE intake_records ADD COLUMN IF NOT EXISTS job_id UUID REFERENCES intake_jobs (id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_intake_records_job ON intake_records (job_id);
CREATE INDEX IF NOT EXISTS idx_intake_jobs_tenant_status ON intake_jobs (tenant_id, status);
```

`job_id` entra **nullable**: la tabla ya puede tener filas de F2b, y una columna `NOT NULL` sin valor
por defecto las rompería. La Tarea 2 garantiza que todo registro nuevo lleve job.

## Paso 2: los enums

En `enums.py`, junto a `IntakeRecordStatus`:

```python
class IntakeJobKind(str, Enum):
    SINGLE = "SINGLE"
    BATCH = "BATCH"


class IntakeJobStatus(str, Enum):
    """How far along an ingestion operation is."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    # Terminal: no work left. NOT a claim that everything succeeded — a job with
    # ten rejected items is COMPLETED with failed=10. "Finished" and "went well"
    # are different questions and the counters answer the second one.
    COMPLETED = "COMPLETED"
    # The job could not even start: unreadable file, missing source.
    FAILED = "FAILED"
```

## Paso 3: el identificador y la entidad

`intake_job_id.py` copia exactamente el patrón de `lead_source_id.py`.

`intake_job.py`, con la forma de `intake_record.py` —`@dataclass`, factoría `create`, métodos de
transición que validan el estado de origen—:

```python
_TERMINAL = (IntakeJobStatus.COMPLETED, IntakeJobStatus.FAILED)


@dataclass
class IntakeJob:
    id: IntakeJobId
    tenant_id: TenantId
    source_id: LeadSourceId
    kind: IntakeJobKind
    status: IntakeJobStatus = IntakeJobStatus.PENDING
    total_items: Optional[int] = None
    succeeded: int = 0
    failed: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
```

Métodos, cada uno rechazando la transición desde un estado terminal con
`DomainException(error_code="INVALID_JOB_TRANSITION")`:

| Método | Qué hace |
|---|---|
| `start()` | `PENDING` → `PROCESSING` |
| `set_total(total: int)` | Fija `total_items`. Sólo desde `PROCESSING`, y sólo si aún es nulo |
| `record_success()` | `succeeded += 1` |
| `record_failure()` | `failed += 1` |
| `complete()` | → `COMPLETED`, sella `completed_at` |
| `fail()` | → `FAILED`, sella `completed_at` |
| `reset_counters()` | `succeeded` y `failed` a cero, y el estado vuelve a `PENDING` |

`record_success` y `record_failure` **no** cambian el estado: contar y terminar son decisiones
distintas, y quien recorre los items no siempre sabe si queda trabajo.

`reset_counters()` lo usa el reproceso de la Tarea 5, que vuelve a recorrer los mismos items: sin
poner los contadores a cero, sumarlos otra vez daría totales imposibles. Vuelve a `PENDING` porque
`start()` sólo acepta ese estado. **Se admite desde `PENDING` y desde `PROCESSING`** —un job que
nunca llegó a arrancar también se relanza, y ahí es idempotente— y se rechaza desde los terminales
con `INVALID_JOB_TRANSITION`: un job `COMPLETED` no se reprocesa.

La factoría, con la firma exacta que usa la Tarea 2:

```python
    @staticmethod
    def create(
        tenant_id: UUID,
        source_id: UUID,
        kind: IntakeJobKind,
        total_items: Optional[int] = None,
    ) -> "IntakeJob":
```

`total_items` va en la firma porque la recepción unitaria lo conoce (`1`) y la masiva no (`None`).
`kind` se acepta como `str` o enum, igual que `IntakeRecord.create` hace con `status`.

## Paso 4: `IntakeRecord` gana `job_id`

En `intake_record.py`, campo nuevo **opcional** para no romper las llamadas existentes:

```python
    job_id: Optional[IntakeJobId] = None
```

Y en `create()`, el parámetro correspondiente con la misma conversión que ya usa `lead_id`:

```python
        job_id=job_id if (job_id is None or isinstance(job_id, IntakeJobId)) else IntakeJobId(job_id),
```

**No toques ningún otro método de la entidad.** `promote`, `reject` y `discard` quedan como están.

## Paso 5: puerto y adaptadores

`intake_job_repository_port.py`, con la forma de `intake_record_repository_port.py`:

```python
class IntakeJobRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, job: IntakeJob) -> IntakeJob: ...

    @abc.abstractmethod
    def get_by_id_and_tenant(self, job_id: UUID, tenant_id: UUID) -> Optional[IntakeJob]: ...

    @abc.abstractmethod
    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeJobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntakeJob]: ...

    @abc.abstractmethod
    def count_by_tenant(self, tenant_id: UUID, status: Optional[IntakeJobStatus] = None) -> int: ...
```

`save` es *upsert* por clave primaria, como el de registros: la fase 2 lo llama varias veces sobre el
mismo job para ir actualizando contadores.

Tres implementaciones van juntas, y **omitir una rompe la suite entera**:

1. `raw_sql_intake_job_repository.py` — SQL crudo, marcadores `%s` (C3)
2. `InMemoryIntakeJobRepository` en `in_memory_uow.py`, junto a la de registros
3. El registro en ambos UoW: `unit_of_work_port.py` declara `intake_jobs: IntakeJobRepositoryPort`,
   `postgres_unit_of_work.py` lo instancia en `__enter__` con los demás

`raw_sql_intake_record_repository.py` pasa a leer y escribir la columna `job_id`. Es el fichero que
más fácil se olvida: sin ese cambio el campo existe en la entidad, existe en la tabla, y se pierde en
cada ida y vuelta.

## Tests

**`tests/unit/domain/test_intake_job.py`** (marcador `unit`, sin base de datos):

| Caso | Esperado |
|---|---|
| `create` deja el job `PENDING` con contadores a cero | Estado inicial correcto |
| `start` desde `PENDING` | `PROCESSING` |
| `start` desde `COMPLETED` o `FAILED` | `INVALID_JOB_TRANSITION` |
| `set_total` desde `PROCESSING` | Fija el total |
| `set_total` dos veces | `INVALID_JOB_TRANSITION` |
| `record_success` / `record_failure` | Suben el contador y **no** cambian el estado |
| `complete` y `fail` | Sellan `completed_at` |
| Cualquier transición desde un estado terminal | `INVALID_JOB_TRANSITION` |
| `reset_counters` sobre un job `PROCESSING` con contadores | Vuelve a `PENDING` con `succeeded=0`, `failed=0` |
| `reset_counters` sobre un job `COMPLETED` | `INVALID_JOB_TRANSITION` |

**`tests/integration/test_intake_job_repo.py`** (marcador `integration`):

| Caso | Esperado |
|---|---|
| Guardar y recuperar un job | Todos los campos sobreviven, incluido `total_items` nulo |
| `save` dos veces sobre el mismo id | Actualiza, no duplica |
| `list_by_tenant` con filtro de estado | Sólo los de ese estado |
| `get_by_id_and_tenant` con otra organización | `None` |
| Un registro guardado con `job_id` lo recupera | El vínculo sobrevive |

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q      # el dominio creció: verde sin base de datos
cd .. && ./scripts/verify-e2e.sh            # nada debería haber cambiado
git commit -m "feat(domain): give every ingestion an operation it belongs to"
```
