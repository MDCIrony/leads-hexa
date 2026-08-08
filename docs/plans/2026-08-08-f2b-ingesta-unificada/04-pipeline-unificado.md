# Tarea 4 — El pipeline unificado y la retirada de `FAILED`

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

**Estado: ✅ cerrada en `0be1127`.** Se conserva como registro de lo que se pidió.

**Ficheros:**
- Modificar: `src/application/use_cases/ingest_lead_use_case.py`,
  `src/application/use_cases/process_batch_use_case.py`,
  `src/application/dtos/commands.py`, `src/domain/value_objects/enums.py`,
  `src/infrastructure/adapters/input/api/intake_router.py`
- Crear: `tests/unit/application/test_unified_intake_pipeline.py`
- Test a revisar: `tests/unit/application/test_ingest_lead_use_case.py`

**Consume de T1 y T3:** `uow.sources`, `uow.intake_records`, `IntakeRecord`, `IntakeError`.

## El recorrido

```
payload ─→ IntakeRecord(PENDING) persistido ─→ interpretar ─┬─ falla ─→ reject(errores) ─→ REJECTED
                                                            │
                                                            └─ ok ─→ Lead ─→ scoring ─→ reparto
                                                                      └─→ promote(lead.id) ─→ PROMOTED
```

Lo que hoy pasa y deja de pasar: `ingest_lead_use_case.py:49-56` captura la `DomainException` y
devuelve `LeadStatus.FAILED` **sin persistir nada**. Ése es el agujero por el que se pierden los
leads y la razón de ser de la fase.

## Paso 1: la firma del resultado

`LeadProcessedResult` (`commands.py:139`) gana un campo:

```python
intake_record_id: str = ""
```

Se rellena **siempre**, tanto en el camino bueno como en el rechazo: es lo que permite al gestor ir
del error al registro guardado.

## Paso 2: el caso de uso

Reescribe `IngestLeadUseCase.execute` con esta estructura. Todo dentro del `with self.uow:`, en una
sola transacción — al capturar la `DomainException` la transacción llega a `commit`, así que el
registro sí queda persistido.

```python
def execute(self, command: IngestLeadCommand) -> LeadProcessedResult:
    with self.uow:
        record = self.uow.intake_records.save(
            IntakeRecord.create(
                tenant_id=command.tenant_id,
                source_id=command.source_id,
                payload=self._payload_of(command),
            )
        )

        try:
            lead = Lead.create(...)   # los mismos argumentos de hoy, más source_id
        except DomainException as exc:
            record.reject([IntakeError(
                field=self._field_of(exc),
                message=str(exc),
                error_code=exc.error_code,
            )])
            self.uow.intake_records.save(record)
            return LeadProcessedResult(
                lead_id="",
                intake_record_id=str(record.id),
                status=IntakeRecordStatus.REJECTED.value,
                score=0,
                error=str(exc),
                error_code=exc.error_code,
            )

        # ... scoring, qualify, reparto y save: idénticos a las líneas 58-90 de hoy ...

        record.promote(saved_lead.id)
        self.uow.intake_records.save(record)

    # ... publicación del evento y resultado, con intake_record_id=str(record.id) ...
```

`_payload_of(command)` devuelve un `dict` serializable con los campos del comando —convierte
`UUID` a `str` y `Decimal` a `float`—, porque va a una columna `JSONB`.

`_field_of(exc)` mapea el código de error al campo culpable, para que el gestor sepa qué columna
corregir:

```python
# Verified against domain/exceptions.py: these are the codes the entity's
# value objects actually raise. Do not invent new ones.
_FIELD_BY_ERROR_CODE = {
    "INVALID_EMAIL": "email",
    "INVALID_BUDGET": "budget",
    "INVALID_UUID": "_record",
}
# default: "_record" — the payload as a whole, when nothing narrower is known
```

## Paso 3: la carga masiva recorre lo mismo

`ProcessBatchUseCase.execute` (`process_batch_use_case.py:23-31`) ya llama al mismo caso de uso por
fila, así que hereda el pipeline sin cambios de fondo. Dos cosas que sí toca:

**1. `FailedRow.email` → `Optional[str]`, y `FailedRowResponse.email` también.** No es cosmético:
desde T2 el correo puede faltar, y `process_batch_use_case.py:30` pasa `cmd.email` —que ya puede ser
`None`— a un campo declarado `str`. El dataclass lo traga en silencio, pero `FailedRowResponse` es
un modelo de Pydantic y **eleva `ValidationError`**, que sale por HTTP como un 500. Se dispara con
un CSV cuya fila no traiga correo y falle por otra cosa, por ejemplo un presupuesto no numérico.
Escribe ese caso como test.

**2. `intake_record_id: str = ""` en `FailedRow`**, rellenado desde `res.intake_record_id`: es lo
que convierte una fila fallida en algo recuperable desde la bandeja.

## Paso 4: retirar `FAILED`

Borra `LeadStatus.FAILED` de `enums.py:18-20`, con su comentario. Después:

```bash
rg -n "FAILED" backend/src backend/tests
```

No debe quedar ninguna referencia a `LeadStatus.FAILED`. En `intake_router.py:42`, la comparación
`result.status == "FAILED"` pasa a `result.status == IntakeRecordStatus.REJECTED.value`, y el
cuerpo del 400 gana el identificador del registro:

```python
content={
    "error": True,
    "error_code": result.error_code,
    "message": result.error,
    "intake_record_id": result.intake_record_id,
}
```

**Sigue siendo 400, no 201.** El gestor que rellena un formulario tiene que ver el fallo al
momento; que el payload quede guardado es una garantía adicional, no una razón para fingir éxito.
El comentario de `intake_router.py:43-47` explica el criterio viejo: reescríbelo, no lo borres sin
más.

## Tests — `test_unified_intake_pipeline.py`

| Caso | Aserción |
|---|---|
| Payload válido | Existe un `IntakeRecord` en `PROMOTED` con `lead_id` apuntando al lead creado |
| Correo con formato inválido | Existe un `IntakeRecord` en `REJECTED`, con un `IntakeError` de campo `email`, y **no** se creó ningún lead |
| Payload sin correo | Se crea el lead; el registro queda `PROMOTED`. Es la comprobación de que T2 y T4 no se pisan |
| Rechazo | `result.intake_record_id` no está vacío |
| Carga masiva de dos filas, una válida y otra no | Un registro `PROMOTED` y uno `REJECTED`; `successful_ingestions == 1` |

Usa los dobles de `tests/unit/mocks/`. Revisa `test_ingest_lead_use_case.py`: lo que ahí afirmaba
`FAILED` hay que reescribirlo contra el pipeline nuevo.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
git commit -m "feat(application): route every intake through one pipeline that keeps what it cannot read"
```

---

