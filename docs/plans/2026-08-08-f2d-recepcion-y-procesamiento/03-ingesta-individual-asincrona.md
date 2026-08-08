# Tarea 3 — La ingesta individual responde 202

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

**La única tarea de la fase que rompe un contrato público.** La ingesta pasa de devolver el lead ya
puntuado a devolver un identificador de trabajo. Siete ficheros de pruebas dependen de lo primero.

## Ficheros

**Crear:**

| Fichero | Contenido |
|---|---|
| `backend/tests/e2e/_intake_helpers.py` | Helper compartido: ingerir y esperar el resultado |

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/infrastructure/adapters/input/api/intake_router.py` | El endpoint usa las dos fases y responde `202` |
| `backend/src/infrastructure/adapters/input/api/schemas.py` | `IntakeAcceptedResponse`; **fuera la validación de correo** |
| `backend/tests/e2e/test_lead_endpoints.py` | Ruta y forma de respuesta |
| `backend/tests/e2e/test_system_e2e.py` | Ídem |
| `backend/tests/e2e/test_assignment_flow_e2e.py` | Ídem |
| `backend/tests/e2e/test_lead_lifecycle_api.py` | Ídem — **21 aserciones dependen del lead procesado** |
| `backend/tests/e2e/test_intake_authentication.py` | Ídem |
| `backend/tests/e2e/test_intake_inbox.py` | Ídem |
| `backend/tests/e2e/test_source_endpoints.py` | Sólo donde ingiere para probar `SOURCE_IN_USE` |

**Consume de la Tarea 2:** `ReceiveIntakeUseCase` con `execute(ReceiveIntakeCommand) ->
ReceiveIntakeResult`, `ProcessIntakeJobUseCase` con `execute(tenant_id, job_id)`, y sus proveedores
`get_receive_intake_use_case` y `get_process_intake_job_use_case`.

`scripts/verify-e2e.sh` **no se toca aquí**: lo hace la Tarea 6, que reescribe sus comprobaciones de
ingesta de una vez para las dos rutas.

## Paso 1: el esquema pierde la validación de correo

En `schemas.py`, borra el validador de `IngestLeadRequest` y la función `_validate_email_format`:

```python
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        ...
```

**Por qué (V1):** duplica la validación de `EmailAddress` con una regla más laxa, y es la que producía
un `422` que descartaba el payload **antes de que nada se persistiera**. Al quitarla, un correo mal
formado llega al dominio, que lo rechaza dejando el registro en la bandeja con su detalle.

`email: Optional[str] = None` se queda tal cual. **No añadas ninguna validación en su lugar.**

Y el esquema de respuesta:

```python
class IntakeAcceptedResponse(BaseModel):
    job_id: str
    record_ids: List[str]
    status: str
```

## Paso 2: el endpoint

En `intake_router.py`, `ingest_lead` cambia entero:

```python
@router.post("/leads/ingest", response_model=IntakeAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_lead(
    request: IngestLeadRequest,
    background: BackgroundTasks,
    context: RequestContext = Depends(require_organization_manager),
    receive: ReceiveIntakeInputPort = Depends(get_receive_intake_use_case),
    process: ProcessIntakeJobInputPort = Depends(get_process_intake_job_use_case),
):
    received = receive.execute(ReceiveIntakeCommand(
        tenant_id=context.tenant_id,
        kind=IntakeJobKind.SINGLE.value,
        payloads=[request.model_dump()],
    ))
    # Encolado después de que la recepción haya confirmado: si el proceso muere
    # aquí, el registro ya es durable y el job queda visible para reprocesar.
    background.add_task(process.execute, context.tenant_id, UUID(received.job_id))
    return IntakeAcceptedResponse(
        job_id=received.job_id,
        record_ids=received.record_ids,
        status=received.status,
    )
```

`request.model_dump()` es lo que guarda el payload **tal como llegó** (V2).

`BackgroundTasks` se declara como parámetro del endpoint; FastAPI lo inyecta. Los casos de uso se
resuelven por `Depends` como siempre: `get_uow` devuelve directamente, sin cerrar nada al terminar la
petición, así que la tarea de fondo toma conexión fresca del pool cuando corre.

**El endpoint ya no llama a `resolve_source_id`.** La fuente la resuelve la fase 1.

## Paso 3: el helper de los tests

En `_intake_helpers.py`, para no repetir el mismo baile en siete ficheros:

```python
def ingest_and_resolve(client, headers: dict, payload: dict) -> dict:
    """Ingests one lead and returns its intake record, already processed.

    TestClient runs background tasks before handing control back, so no polling
    is needed here — the work is done by the time the POST returns.
    """
    accepted = client.post("/api/v1/intake/leads/ingest", json=payload, headers=headers)
    assert accepted.status_code == 202, accepted.text
    job_id = accepted.json()["job_id"]

    records = client.get(f"/api/v1/intake/records?job_id={job_id}", headers=headers)
    assert records.status_code == 200, records.text
    items = records.json()["items"]
    assert len(items) == 1, items
    return items[0]
```

Devuelve el registro completo, que lleva `status`, `lead_id` y `errors`. Un test que necesitaba el
identificador del lead usa `ingest_and_resolve(...)["lead_id"]`.

El filtro `?job_id=` lo habilitó la Tarea 2 sobre el endpoint que ya existe.

## Paso 4: los siete ficheros

El patrón es siempre el mismo:

```python
# antes
resp = client.post("/api/v1/intake/leads/ingest", json=payload, headers=headers)
assert resp.status_code == 201
lead_id = resp.json()["lead_id"]

# después
lead_id = ingest_and_resolve(client, headers, payload)["lead_id"]
```

**No cambies lo que los tests afirman** — sólo cómo obtienen el lead. Un test que comprobaba el score,
el estado o el asesor asignado sigue comprobando exactamente lo mismo; lo único que cambia es de dónde
sale el identificador.

Casos que no encajan en el patrón y hay que mirar uno a uno:

| Fichero | Qué tiene de particular |
|---|---|
| `test_intake_authentication.py` | Sus casos de `401` y `403` **no cambian**: la autorización sigue ocurriendo antes de aceptar. Sólo cambia el caso del gestor, que ahora espera `202` |
| `test_intake_inbox.py` | Ya trabaja con registros. El caso del correo mal formado pasa de `400` a `202` + registro `REJECTED`; el detalle por campo se comprueba igual |
| `test_lead_lifecycle_api.py` | El grueso de las 21 aserciones. Su helper `_ingest_qualified_lead` es el único sitio que hay que reescribir; el resto llama a través de él |
| `test_source_endpoints.py` | Sólo ingiere para poder probar `SOURCE_IN_USE`. Basta con que el lead exista |

## Tests nuevos

En `test_intake_authentication.py`, dos casos que la fase habilita:

| Caso | Esperado |
|---|---|
| Un correo con formato inválido | `202` — se acepta, y el registro queda `REJECTED` con error de campo `email` |
| Ingesta con el token de otra organización | El job y el registro caen en **su** organización, no en la del cuerpo |

El primero es el que demuestra V1: lo que antes se perdía en un `422` ahora queda registrado.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q
cd .. && ./scripts/verify-e2e.sh    # F2a fallará en sus comprobaciones de ingesta: lo arregla la Tarea 6
git commit -m "feat(api): accept an intake and answer with the work it created"
```

**`verify-e2e.sh` quedará en rojo al terminar esta tarea, y es esperado.** Sus comprobaciones de
ingesta asumen `201` con el lead. La Tarea 6 las reescribe junto con las de la carga masiva, para no
tocar el mismo bloque dos veces. Déjalo anotado en tu respuesta con las comprobaciones concretas que
fallan.
