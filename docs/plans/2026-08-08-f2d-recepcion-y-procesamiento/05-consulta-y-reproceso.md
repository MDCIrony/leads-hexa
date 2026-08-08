# Tarea 5 — Consulta y reproceso

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Aditiva: no cambia ninguna ruta existente. Es lo que convierte el `job_id` que las tareas 3 y 4
devuelven en algo que se puede consultar, y lo que da salida a un trabajo interrumpido.

## Ficheros

**Crear:**

| Fichero | Contenido |
|---|---|
| `backend/src/application/ports/input/intake_job_use_case_ports.py` | Los tres ABC |
| `backend/src/application/use_cases/intake_job_use_cases.py` | Los tres casos de uso |
| `backend/tests/e2e/test_intake_jobs.py` | Los tests |

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/application/dtos/queries.py` | `GetIntakeJobsQuery` |
| `backend/src/application/dtos/commands.py` | `IntakeJobsPageResult` |
| `backend/src/infrastructure/adapters/input/api/intake_router.py` | Los tres endpoints |
| `backend/src/infrastructure/adapters/input/api/schemas.py` | `IntakeJobResponse`, `IntakeJobsPageResponse` |
| `backend/src/infrastructure/adapters/input/api/dependencies.py` | Tres proveedores |

**Consume de tareas previas:** `uow.intake_jobs` con sus cuatro métodos, `ProcessIntakeJobUseCase`, y
`list_by_tenant`/`count_by_tenant` de registros con filtro por `job_id` (Tarea 2, Paso 4).

`main.py` **no se toca**: los tres endpoints cuelgan del router de intake, ya montado.

## Paso 1: casos de uso

En `intake_job_use_cases.py`, con el helper de C5 delante:

```python
def _get_owned_job(uow: UnitOfWorkPort, tenant_id: UUID, job_id: UUID) -> IntakeJob:
    """Un trabajo de otra organización debe leerse como inexistente."""
    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    if job is None:
        raise DomainException("El trabajo no existe", error_code="INTAKE_JOB_NOT_FOUND")
    return job
```

**`GetIntakeJobsUseCase`** — lista paginada con filtro opcional por estado. Un `status` desconocido
sale como `DomainException(error_code="INVALID_JOB_STATUS")`, no como un `ValueError` que acabe en
500.

**`GetIntakeJobUseCase`** — uno solo, con sus contadores. `404` si es de otra organización.

**`ReprocessIntakeJobUseCase`** — la razón de ser de esta tarea:

```python
class ReprocessIntakeJobUseCase(ReprocessIntakeJobInputPort):
    def __init__(self, uow: UnitOfWorkPort, process: ProcessIntakeJobInputPort) -> None:
        self.uow = uow
        self.process = process

    def execute(self, tenant_id: UUID, job_id: UUID) -> None:
        with self.uow:
            job = _get_owned_job(self.uow, tenant_id, job_id)
            if job.status in (IntakeJobStatus.COMPLETED, IntakeJobStatus.FAILED):
                raise DomainException(
                    "Un trabajo terminado no se reprocesa",
                    error_code="INVALID_JOB_TRANSITION",
                )
            # Los contadores se reinician: el recorrido va a volver a contar los
            # mismos items, y sumarlos dos veces daría totales imposibles.
            job.reset_counters()
            self.uow.intake_jobs.save(job)
        self.process.execute(tenant_id, job_id)
```

`reset_counters()` **ya existe** desde la Tarea 1: pone `succeeded` y `failed` a cero y devuelve el
estado a `PENDING`, para que `start()` de la fase 2 lo acepte. Aquí sólo se usa. Si no lo encuentras
en `intake_job.py`, eso es una discrepancia que reportar, no un método que improvisar.

**Sólo se reprocesan los registros que siguen en `PENDING`.** La fase 2 ya los filtra así, de modo que
un registro `PROMOTED` no genera un segundo lead. Eso es lo que hace el reproceso seguro de repetir, y
es la propiedad que la cola necesitará cuando exista.

## Paso 2: endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/v1/intake/jobs?status=&limit=&offset=` | Lista paginada |
| `GET` | `/api/v1/intake/jobs/{job_id}` | Estado y contadores de uno |
| `POST` | `/api/v1/intake/jobs/{job_id}/reprocess` | Relanza los items no terminales |

Los tres con `context: RequestContext = Depends(require_organization_manager)`.

`reprocess` corre **en segundo plano** igual que la ingesta, y responde `202` con el job:

```python
    background.add_task(reprocess.execute, context.tenant_id, job_id)
```

**Cuidado con el orden de las rutas.** `/jobs/{job_id}` y el ya existente `/records/{record_id}/...`
conviven en el mismo router; FastAPI resuelve por orden de declaración, así que declara las rutas
literales antes que las paramétricas si alguna pudiera solaparse.

## Paso 3: esquemas

```python
class IntakeJobResponse(BaseModel):
    id: str
    source_id: str
    kind: str
    status: str
    # Nulo hasta que el fichero se parsea: en una carga masiva el total no se
    # conoce al aceptar la petición.
    total_items: Optional[int] = None
    succeeded: int
    failed: int
    created_at: datetime
    completed_at: Optional[datetime] = None

class IntakeJobsPageResponse(BaseModel):
    items: List[IntakeJobResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
```

`INVALID_JOB_STATUS` quiere `400`, que es el valor por defecto de `STATUS_BY_ERROR_CODE`: no lo
añadas. `INTAKE_JOB_NOT_FOUND` ya debería tener su fila con `404` desde la Tarea 2; **compruébalo**.

## Tests — `test_intake_jobs.py`

| Caso | Esperado |
|---|---|
| Ingerir un lead y consultar su job | `COMPLETED`, `total_items=1`, `succeeded=1` |
| Listar jobs filtrando por estado | Sólo los de ese estado |
| Filtro con un estado inexistente | `INVALID_JOB_STATUS`, no un 500 |
| `GET` de un job de otra organización | **404** |
| `POST /reprocess` sobre un job de otra organización | **404** |
| Reprocesar un job ya `COMPLETED` | `INVALID_JOB_TRANSITION` |
| Un asesor (`AGENT`) llama a cualquiera de los tres | `403` |

Y el que demuestra el criterio de aceptación 4, que necesita un job a medias:

| Caso | Esperado |
|---|---|
| Un job con registros `PENDING` que nunca se procesaron, al reprocesarlo | Queda `COMPLETED` con sus contadores, y los registros pasan a estado terminal |
| **Reprocesar dos veces el mismo job** | **No aparece un segundo lead**, y los contadores no se duplican |

Para fabricar el job a medias, crea el job y sus registros directamente por el repositorio, sin pasar
por el endpoint: es exactamente el estado en que queda un proceso interrumpido, y no hay forma de
provocarlo por HTTP.

El caso de las dos ejecuciones es el importante: es la propiedad que hace el reproceso seguro y la que
la cola dará por supuesta.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q
cd .. && ./scripts/verify-e2e.sh    # sigue en rojo desde la Tarea 3: lo arregla la Tarea 6
git commit -m "feat(api): let the manager see and relaunch an ingestion that stalled"
```
