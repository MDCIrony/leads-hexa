# Tarea 4 — La carga masiva responde 202

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Lleva la carga masiva al mismo contrato que la Tarea 3 dejó en la ingesta unitaria, y cierra la
inversión: al terminar, **nadie crea un registro de entrada dentro del servicio de ingesta**.

## Ficheros

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/application/use_cases/process_batch_use_case.py` | Se reescribe: parsea, crea los registros y delega en la fase 2 |
| `backend/src/application/ports/input/process_batch_use_case_port.py` | El ABC sigue a su implementación |
| `backend/src/application/use_cases/ingest_lead_use_case.py` | `existing_record` pasa a **obligatorio** |
| `backend/src/application/ports/input/ingest_lead_use_case_port.py` | Ídem |
| `backend/src/infrastructure/adapters/input/api/intake_router.py` | El endpoint responde `202` |
| `backend/src/infrastructure/adapters/input/api/dependencies.py` | El proveedor del batch cambia de forma |
| `backend/tests/unit/application/test_unified_intake_pipeline.py` | Llama a `execute` sin registro y con `source_id` |
| `backend/tests/e2e/test_intake_inbox.py` | Su caso de carga masiva mixta |

**Consume de tareas previas:** `ReceiveIntakeUseCase`, `ProcessIntakeJobUseCase`, `IntakeJob` con
`set_total` y `fail`, y el helper `ingest_and_resolve` de la Tarea 3.

## Paso 1: `ProcessBatchUseCase` se reescribe

Deja de recorrer filas y producir un resultado. Ahora **parsea, materializa los registros y delega**:

```python
class ProcessBatchUseCase(ProcessBatchInputPort):
    def __init__(
        self,
        uow: UnitOfWorkPort,
        file_parser: FileParserPort,
        process_job: ProcessIntakeJobInputPort,
    ) -> None:
        self.uow = uow
        self.file_parser = file_parser
        self.process_job = process_job

    def execute(self, tenant_id: UUID, job_id: UUID, file_content: bytes, filename: str) -> None:
        with self.uow:
            job = self.uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
            if job is None:
                raise DomainException("El trabajo no existe", error_code="INTAKE_JOB_NOT_FOUND")
            source_id = job.source_id.value

        try:
            commands = self.file_parser.parse_leads_file(file_content, filename, tenant_id, source_id)
        except Exception:
            # Un fichero ilegible es un job que no pudo empezar, no uno con items
            # fallidos: no hay filas que registrar ni que reprocesar.
            with self.uow:
                job = self.uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
                job.fail()
                self.uow.intake_jobs.save(job)
            return

        with self.uow:
            job = self.uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
            for command in commands:
                self.uow.intake_records.save(IntakeRecord.create(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    job_id=job_id,
                    payload=_payload_of(command),
                ))
            job.set_total(len(commands))
            self.uow.intake_jobs.save(job)

        self.process_job.execute(tenant_id, job_id)
```

**Los registros se materializan y se confirman antes de procesar ninguno.** Ése es el punto: si el
proceso muere a mitad del recorrido, las mil filas ya están persistidas y el reproceso las recupera.

`_payload_of` en el bloque de arriba es la función **`payload_of`** que la Tarea 2 extrajo a nivel de
módulo en `ingest_lead_use_case.py`. **Impórtala, no la copies:** un segundo `_payload_of` con otra
forma haría que un registro del batch y uno unitario no se parezcan, y el detalle por campo de la
bandeja dejaría de ser comparable entre ambos.

`job.set_total` va **después** de crear los registros, no antes: el total sólo se conoce al parsear, y
es el motivo de que nazca nulo.

## Paso 2: el endpoint

```python
@router.post("/leads/batch-upload", response_model=IntakeAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def batch_upload(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    context: RequestContext = Depends(require_organization_manager),
    receive: ReceiveIntakeInputPort = Depends(get_receive_intake_use_case),
    process_batch: ProcessBatchInputPort = Depends(get_process_batch_use_case),
):
    # Los bytes se leen aquí y no en la tarea de fondo: el fichero subido se
    # cierra al terminar la petición, y para entonces la tarea aún no ha corrido.
    content = await file.read()
    received = receive.execute(ReceiveIntakeCommand(
        tenant_id=context.tenant_id,
        kind=IntakeJobKind.BATCH.value,
        payloads=[],
    ))
    background.add_task(
        process_batch.execute,
        context.tenant_id, UUID(received.job_id), content, file.filename or "leads.csv",
    )
    return IntakeAcceptedResponse(
        job_id=received.job_id,
        record_ids=[],
        status=received.status,
    )
```

`payloads=[]` es lo que hace nacer el job con `total_items` nulo.

**El fichero entero queda en memoria** hasta que la tarea de fondo termina. Es asumible para el
tamaño de este MVP y es la consecuencia directa de no tener cola ni almacenamiento intermedio; no
inventes un fichero temporal para evitarlo.

`BatchProcessResponse`, `FailedRowResponse` y los DTOs `BatchProcessResult` y `FailedRow` dejan de
usarse en este camino. **No los borres**: la Tarea 5 decide si el detalle por fila se recupera desde
los registros. Bórralos allí si sobran.

## Paso 3: `existing_record` pasa a obligatorio

Ya nadie llama a `IngestLeadUseCase.execute` sin un registro: la fase 2 siempre lo pasa, y la
promoción desde la bandeja también. El parámetro deja de ser opcional:

```python
    def execute(self, command: IngestLeadCommand, existing_record: IntakeRecord) -> LeadProcessedResult:
        assigned_agent = None
        with self.uow:
            record = existing_record
            ...
```

Con eso **el servicio de ingesta ya no conoce la creación de registros**: los recibe y los marca. Es
la inversión completa que el spec §6 describe, y el motivo de toda la fase.

El ABC de `ingest_lead_use_case_port.py` replica la firma.

`resolve_source_id` deja de tener llamadores —la fase 1 resuelve la fuente— pero **no lo borres**:
`PromoteIntakeRecordUseCase` puede usarlo. Compruébalo antes de tocarlo y dilo en tu respuesta.

## Paso 4: los tests unitarios del pipeline

`test_unified_intake_pipeline.py` llama a `execute` con la firma vieja. Actualiza cada llamada
construyendo el registro primero:

```python
record = uow.intake_records.save(IntakeRecord.create(
    tenant_id=tenant_id, source_id=source_id, payload={...},
))
result = use_case.execute(command, existing_record=record)
```

**No cambies lo que los tests afirman.** Siguen comprobando el mismo pipeline; sólo cambia cómo se les
entrega el registro.

## Tests

En `test_intake_inbox.py`, el caso de carga masiva mixta pasa a:

| Paso | Esperado |
|---|---|
| Subir un CSV con una fila buena y una mala | `202` con `job_id` y `record_ids` vacío |
| Consultar el job | `COMPLETED`, `total_items=2`, `succeeded=1`, `failed=1` |
| Consultar sus registros | Uno `PROMOTED` con `lead_id`, uno `REJECTED` con error de campo |

Y dos casos nuevos:

| Caso | Esperado |
|---|---|
| Subir un fichero ilegible (bytes que no son CSV ni XLSX) | El job queda `FAILED`, sin registros, y **no revienta con un 500** |
| Subir un CSV vacío (sólo cabecera) | Job `COMPLETED` con `total_items=0` |

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q
cd .. && ./scripts/verify-e2e.sh    # sigue en rojo desde la Tarea 3: lo arregla la Tarea 6
git commit -m "feat(api): accept a file and materialise its rows before reading them"
```

`verify-e2e.sh` continúa en rojo, igual que al cerrar la Tarea 3. Anota en tu respuesta qué
comprobaciones fallan, para que la Tarea 6 sepa exactamente qué reescribir.
