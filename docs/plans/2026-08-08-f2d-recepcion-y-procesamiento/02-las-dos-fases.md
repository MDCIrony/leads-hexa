# Tarea 2 — Las dos fases en la aplicación

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Construye los dos casos de uso que parten el recorrido en dos, **con sus tests, pero sin que ningún
router los use todavía**. Las tareas 3 y 4 los enchufan. Al terminar ésta, la aplicación se comporta
exactamente igual que antes.

**Es la tarea que demuestra el criterio de aceptación 5 de la fase**: que un fallo durante el
procesamiento no borre el registro creado en la recepción. Ese test es el motivo de que la fase
exista; no lo dejes para el final.

## Ficheros

**Crear:**

| Fichero | Contenido |
|---|---|
| `backend/src/application/ports/input/intake_phase_use_case_ports.py` | Los dos ABC |
| `backend/src/application/use_cases/receive_intake_use_case.py` | Fase 1 |
| `backend/src/application/use_cases/process_intake_job_use_case.py` | Fase 2 |
| `backend/tests/unit/application/test_intake_phases.py` | Tests de ambas |

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/application/dtos/commands.py` | `ReceiveIntakeCommand`, `ReceiveIntakeResult` |
| `backend/src/infrastructure/adapters/input/api/dependencies.py` | Dos proveedores |
| `backend/src/application/ports/output/intake_record_repository_port.py` | `list_by_tenant` y `count_by_tenant` ganan `job_id` |
| `backend/src/infrastructure/adapters/output/persistence/raw_sql_intake_record_repository.py` | Ídem, en SQL |
| `backend/tests/unit/mocks/in_memory_uow.py` | Ídem, en memoria |
| `backend/src/application/dtos/queries.py` | `GetIntakeRecordsQuery` gana `job_id` |
| `backend/src/application/use_cases/intake_record_use_cases.py` | `GetIntakeRecordsUseCase` lo propaga |
| `backend/src/infrastructure/adapters/input/api/intake_router.py` | `GET /records` acepta `?job_id=` |
| `backend/src/application/use_cases/ingest_lead_use_case.py` | `_payload_of` pasa a función de módulo y gana su inverso `command_from_record` |

**Consume de la Tarea 1:** `IntakeJob` con `start`, `set_total`, `record_success`, `record_failure`,
`complete` y `fail`; `uow.intake_jobs` con `save`, `get_by_id_and_tenant`, `list_by_tenant` y
`count_by_tenant`; `IntakeRecord` con `job_id`.

**Lee sólo como patrón, si lo necesitas:** `ingest_lead_use_case.py`, `intake_record_use_cases.py`.

## Paso 1: DTOs

En `commands.py`:

```python
@dataclass(frozen=True)
class ReceiveIntakeCommand:
    tenant_id: UUID
    kind: str                      # IntakeJobKind, como str: los DTO no importan enums del dominio
    # Una lista, no un dict: la ingesta unitaria manda un payload y la masiva
    # ninguno todavía, porque el fichero se parsea en la fase 2.
    payloads: List[Dict[str, Any]]


@dataclass(frozen=True)
class ReceiveIntakeResult:
    job_id: str
    record_ids: List[str]
    status: str
```

## Paso 2: fase 1 — `ReceiveIntakeUseCase`

Persiste el job y sus registros **en una transacción propia que confirma antes de que nadie intente
interpretar nada**. Es el punto entero de la fase:

```python
class ReceiveIntakeUseCase(ReceiveIntakeInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: ReceiveIntakeCommand) -> ReceiveIntakeResult:
        kind = IntakeJobKind(command.kind)
        source_kind = (
            LeadSourceKind.MANUAL_FORM if kind == IntakeJobKind.SINGLE else LeadSourceKind.FILE_UPLOAD
        )
        with self.uow:
            source = self.uow.sources.get_by_kind(command.tenant_id, source_kind)
            if source is None:
                raise DomainException(
                    f"No active source of kind {source_kind.value} found for this organization",
                    error_code="SOURCE_NOT_FOUND",
                )
            job = self.uow.intake_jobs.save(IntakeJob.create(
                tenant_id=command.tenant_id,
                source_id=source.id.value,
                kind=kind,
                total_items=len(command.payloads) or None,
            ))
            records = [
                self.uow.intake_records.save(IntakeRecord.create(
                    tenant_id=command.tenant_id,
                    source_id=source.id.value,
                    job_id=job.id.value,
                    payload=payload,
                ))
                for payload in command.payloads
            ]
        return ReceiveIntakeResult(
            job_id=str(job.id),
            record_ids=[str(r.id) for r in records],
            status=job.status.value,
        )
```

`total_items` sale de `len(payloads) or None`: uno para la ingesta unitaria, **nulo** para la masiva,
que llega con la lista vacía porque el fichero aún no se ha parseado.

La resolución de la fuente vive aquí y no en el router: C4 y la separación de capas exigen que el
adaptador no consulte repositorios.

**El payload se guarda tal como llega (V2).** No lo normalices, no le quites claves desconocidas, no
lo reordenes.

## Paso 3: fase 2 — `ProcessIntakeJobUseCase`

Lee lo que la fase 1 dejó, lo procesa y actualiza el job. **Cada item se procesa de forma
independiente: un fallo en uno no puede impedir que se procesen los demás ni borrar lo persistido.**

```python
# A single run takes at most this many items. Beyond it the rest stay PENDING
# and a second reprocess picks them up, because only PENDING records are read.
_MAX_ITEMS_PER_RUN = 10_000


class ProcessIntakeJobUseCase(ProcessIntakeJobInputPort):
    def __init__(self, uow: UnitOfWorkPort, ingest: IngestLeadInputPort) -> None:
        self.uow = uow
        self.ingest = ingest

    def execute(self, tenant_id: UUID, job_id: UUID) -> None:
        with self.uow:
            job = self.uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
            if job is None:
                raise DomainException("El trabajo no existe", error_code="INTAKE_JOB_NOT_FOUND")
            job.start()
            self.uow.intake_jobs.save(job)
            pending = self.uow.intake_records.list_by_tenant(
                tenant_id,
                status=IntakeRecordStatus.PENDING,
                job_id=job_id,
                limit=_MAX_ITEMS_PER_RUN,
            )

        interrupted = False
        for record in pending:
            try:
                result = self.ingest.execute(command_from_record(record), existing_record=record)
            except Exception:
                # An unforeseen failure counts and the run carries on. The record
                # stays PENDING on purpose: it is the only state reprocessing
                # reads, so a failure here is recoverable instead of lost.
                job.record_failure()
                interrupted = True
                continue
            if result.status == IntakeRecordStatus.REJECTED.value:
                job.record_failure()
            else:
                job.record_success()

        with self.uow:
            # An interrupted run does NOT complete: a COMPLETED job refuses
            # reprocessing, which would strand its PENDING records forever.
            if not interrupted:
                job.complete()
            self.uow.intake_jobs.save(job)
```

Cinco decisiones que el código de arriba fija y conviene no deshacer:

1. **La ingesta no lanza cuando el dominio rechaza**: devuelve `LeadProcessedResult` con
   `status == "REJECTED"` y su `error_code`. El `try/except` es para lo **imprevisto**, no para el
   rechazo, y por eso hay dos ramas distintas.
2. **El job se muta en memoria durante el recorrido y se guarda una vez al final.** Los contadores no
   necesitan una transacción por item; si el proceso muere a mitad, el reproceso los recalcula desde
   cero con `reset_counters()`.
3. **Cada item va en su propia transacción**, la que `IngestLeadUseCase` ya abre. No envuelvas el
   bucle en un `with self.uow` que las anide. Si necesitas el precedente, `ProcessBatchUseCase`
   compone `IngestLeadUseCase` exactamente así.
4. **Un recorrido interrumpido deja el job en `PROCESSING`.** Es lo que el spec §5 describe como job
   interrumpido, y lo que hace que el criterio de aceptación 4 sea alcanzable: completarlo
   condenaría a sus registros `PENDING`, porque el reproceso rechaza los jobs terminales.
5. **Sólo se leen los registros `PENDING`**, y ésa es la propiedad que hace el reproceso seguro de
   repetir: un registro ya `PROMOTED` no genera un segundo lead.

### Reconstruir el comando desde el registro

`IngestLeadUseCase._payload_of` es hoy un `@staticmethod`. **Pásalo a función de módulo** en
`ingest_lead_use_case.py` —la Tarea 4 lo necesita desde `process_batch_use_case.py`, y un segundo
`_payload_of` con otra forma haría que un registro del batch y uno unitario no se parezcan— y añade
su inverso al lado:

```python
def payload_of(command: IngestLeadCommand) -> Dict[str, Any]:
    """El actual _payload_of, tal cual, como función de módulo."""


def command_from_record(record: IntakeRecord) -> IngestLeadCommand:
    """Rebuild the command from what was stored, without re-validating it.

    tenant_id and source_id come from the record, never from the payload: the
    organization is the one that was authenticated at reception (C4), and the
    payload is untrusted input that happens to carry a copy of both.
    """
    payload = record.payload or {}
    return IngestLeadCommand(
        tenant_id=record.tenant_id.value,
        source_id=record.source_id.value,
        first_name=payload.get("first_name"),
        last_name=payload.get("last_name"),
        company=payload.get("company"),
        budget=payload.get("budget"),
        industry=payload.get("industry"),
        custom_attributes=payload.get("custom_attributes") or {},
        phone=payload.get("phone"),
        email=payload.get("email"),
    )
```

`payload.get(...)` sin valores por defecto ni conversiones: un `budget` que llegó como `"abc"` se
reconstruye como `"abc"` y es el dominio quien lo rechaza (V2). Poner un `0.0` aquí escondería el
error y produciría un lead con datos inventados.

## Paso 4: filtrar registros por job

`IntakeRecordRepositoryPort.list_by_tenant` no sabe filtrar por job. Añade el parámetro:

```python
    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeRecordStatus] = None,
        job_id: Optional[UUID] = None,          # NUEVO
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntakeRecord]: ...
```

Va con valor por defecto para no romper a quien ya lo llama. **Las tres implementaciones van juntas**
—el puerto, `raw_sql_intake_record_repository.py` y la in-memory de `in_memory_uow.py`—; dejar el ABC
sin una rompe la suite entera.

Añade el mismo parámetro a `count_by_tenant`, que la Tarea 5 necesita para paginar.

**El filtro tiene que llegar hasta HTTP, y son tres ficheros más.** La Tarea 3 construye su helper de
tests sobre `GET /api/v1/intake/records?job_id=...`: sin esta cadena el parámetro se ignora en
silencio, el helper devuelve todos los registros de la organización y sus aserciones de longitud
fallan por un motivo que no está donde lo buscarías.

```python
# queries.py — GetIntakeRecordsQuery, junto a status
    job_id: Optional[UUID] = None

# intake_record_use_cases.py — GetIntakeRecordsUseCase.execute, en las dos llamadas
            items = self.uow.intake_records.list_by_tenant(
                query.tenant_id, status=status, job_id=query.job_id,
                limit=query.limit, offset=query.offset,
            )
            total = self.uow.intake_records.count_by_tenant(
                query.tenant_id, status=status, job_id=query.job_id,
            )

# intake_router.py — list_intake_records, un parámetro de consulta más
def list_intake_records(
    status: Optional[str] = None,
    job_id: Optional[UUID] = None,
    ...
    query = GetIntakeRecordsQuery(
        tenant_id=context.tenant_id, status=status, job_id=job_id, limit=limit, offset=offset,
    )
```

Es aditivo: quien no manda `job_id` sigue viendo exactamente lo mismo que antes.

## Paso 5: cableado

Dos proveedores en `dependencies.py`, con el patrón de los existentes. El de la fase 2 compone:

```python
def get_process_intake_job_use_case(
    uow: UnitOfWorkPort = Depends(get_uow),
    ingest: IngestLeadInputPort = Depends(get_ingest_lead_use_case),
) -> ProcessIntakeJobInputPort:
    return ProcessIntakeJobUseCase(uow=uow, ingest=ingest)
```

`INTAKE_JOB_NOT_FOUND` necesita su fila en `STATUS_BY_ERROR_CODE` de `exception_handlers.py` con
valor `404`, o C5 se rompe en silencio. `INVALID_JOB_TRANSITION` quiere `400`, que es el valor por
defecto: no lo añadas.

## Tests — `test_intake_phases.py`

Marcador `unit`, con `InMemoryUnitOfWork`. Siembra una fuente de cada tipo: el UoW in-memory nace
vacío y `ReceiveIntakeUseCase` fallará con `SOURCE_NOT_FOUND` si no lo haces.

| Caso | Esperado |
|---|---|
| Recepción unitaria | Un job `PENDING` con `total_items=1` y un registro `PENDING` con su `job_id` |
| Recepción masiva (lista vacía) | Un job `PENDING` con `total_items` **nulo** y cero registros |
| Recepción sin fuente activa | `SOURCE_NOT_FOUND` |
| Procesar un job con un payload válido | Job `COMPLETED` con `succeeded=1`, registro `PROMOTED`, lead existente |
| Procesar un job con un payload inválido | Job `COMPLETED` con `failed=1`, registro `REJECTED` con error de campo |
| Procesar un job mixto (uno bueno, uno malo) | `succeeded=1`, `failed=1`, y **los dos registros en estado terminal** |
| Procesar un job de otra organización | `INTAKE_JOB_NOT_FOUND` |
| Listar registros filtrando por `job_id` con dos jobs sembrados | Sólo los del job pedido |

Y el que justifica la fase entera:

| Caso | Esperado |
|---|---|
| **La ingesta revienta con una excepción imprevista** (no una `DomainException`) | El registro **sigue existiendo** con su payload intacto y en `PENDING`, el job cuenta el fallo y queda en `PROCESSING`, y el recorrido continúa con los demás items |

Ese último se escribe con un doble de `IngestLeadInputPort` cuyo `execute` lanza `RuntimeError` para
un payload concreto. Es la única forma de demostrar lo que la fase promete: que el fallo al procesar
no destruye la constancia de haber recibido. **Si no puedes escribirlo, algo está mal en el diseño de
la fase 2, no en el test.**

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q
cd .. && ./scripts/verify-e2e.sh            # nada debería haber cambiado todavía
git commit -m "feat(application): split receiving an intake from processing it"
```
