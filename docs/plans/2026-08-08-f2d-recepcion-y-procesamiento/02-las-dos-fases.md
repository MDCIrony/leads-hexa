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
        # ...recorrer los registros PENDING del job, invocar la ingesta por cada uno,
        #    contar y, al final, completar el job.
```

El recorrido, punto por punto:

1. Carga los registros `PENDING` del job (`list_by_tenant` filtrando por `job_id`; ver Paso 4)
2. Por cada uno, llama a `self.ingest.execute(command, existing_record=record)`
3. **Envuelve cada llamada en `try/except Exception`**: si un item revienta de forma imprevista, se
   cuenta como fallo y el recorrido sigue. Sin eso, un item malo aborta el job entero y deja los
   demás en `PENDING` para siempre
4. `job.record_success()` o `job.record_failure()` según el resultado
5. Al terminar, `job.complete()` y `save`

**Cada item en su propia transacción.** `IngestLeadUseCase` ya abre la suya; no envuelvas el bucle en
un `with self.uow` que las anide. Si necesitas el precedente, `ProcessBatchUseCase` compone
`IngestLeadUseCase` exactamente así.

El `IngestLeadCommand` de cada item se reconstruye desde `record.payload`, con las mismas claves que
`IngestLeadUseCase._payload_of` escribe: `first_name`, `last_name`, `email`, `company`, `budget`,
`industry`, `custom_attributes`, `phone`.

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

Y el que justifica la fase entera:

| Caso | Esperado |
|---|---|
| **La ingesta revienta con una excepción imprevista** (no una `DomainException`) | El registro **sigue existiendo** con su payload intacto, el job cuenta el fallo, y el recorrido continúa con los demás items |

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
