# Tarea 5c — La bandeja de entrada

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Aditiva. Es lo que convierte `IntakeRecord` de tabla en producto, y la que cumple el criterio de
aceptación 2, el que justifica la fase entera: *un payload ininterpretable queda en la bandeja con
el detalle del fallo, y el gestor lo corrige y lo promueve*.

**Ficheros:**
- Crear: `src/application/ports/input/intake_record_use_case_ports.py`,
  `src/application/use_cases/intake_record_use_cases.py`, `tests/e2e/test_intake_inbox.py`
- Modificar: `src/infrastructure/adapters/input/api/intake_router.py`,
  `src/infrastructure/adapters/input/api/schemas.py`,
  `src/infrastructure/adapters/input/api/dependencies.py`

**Consume de tareas previas:** `IntakeRecord` con `promote(lead_id)`, `reject(errors)` y
`discard()`; `uow.intake_records` con `get_by_id_and_tenant`, `list_by_tenant` y `count_by_tenant`;
el router de ingesta ya autenticado (5a); y `IngestLeadUseCase`, que es quien sabe interpretar un
payload.

## Paso 1: casos de uso

En `intake_record_use_cases.py`:

- **`GetIntakeRecordsUseCase`** — lista paginada con filtro opcional por estado. Responde con el
  payload **y los errores por campo** de cada registro: sin eso el gestor ve que algo falló pero no
  qué corregir, que es justo lo que la bandeja existe para evitar.
- **`PromoteIntakeRecordUseCase`** — recibe el registro y un payload corregido, reintenta la
  interpretación con el pipeline y, si sale bien, `record.promote(lead.id)`. Si vuelve a fallar,
  `record.reject(...)` con los errores nuevos y la respuesta lo dice: el gestor puede intentarlo otra
  vez sin perder nada.
- **`DiscardIntakeRecordUseCase`** — `record.discard()`.

`promote` acepta un registro que ya estaba `REJECTED`; la entidad lo permite a propósito. Un
registro `PROMOTED` o `DISCARDED` no vuelve atrás por ningún camino.

**C5 aplica:** un registro de otra organización devuelve **404** en las tres operaciones.

## Paso 2: endpoints

En `intake_router.py`, junto a los de ingesta que 5a dejó autenticados:

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/v1/intake/records?status=REJECTED` | Lista paginada, filtro opcional por estado |
| `POST` | `/api/v1/intake/records/{id}/promote` | Reintenta con el payload corregido |
| `POST` | `/api/v1/intake/records/{id}/discard` | El gestor decide no recuperarlo |

## Paso 3: esquemas

En `schemas.py`:

- `IntakeErrorResponse` — `field`, `message`, `received_value`, `error_code`
- `IntakeRecordResponse` — `id`, `source_id`, `status`, `payload`, `errors`, `received_at`,
  `processed_at`, `lead_id`
- `IntakeRecordsPageResponse` — `items`, `total`

## Tests — `test_intake_inbox.py`

Recorre el criterio de aceptación 2 completo, en un solo hilo:

1. Ingesta con correo mal formado → **400** con `intake_record_id` no vacío
2. Ese registro aparece en `GET /records?status=REJECTED`, con un error de campo `email` y el
   payload original
3. `POST /records/{id}/promote` con el correo corregido → **200**
4. El registro queda `PROMOTED` con su `lead_id`, y el lead existe y es visible
5. Promover el mismo registro otra vez → error de transición, no un segundo lead

Y dos casos aparte: una carga masiva mixta deja un registro `PROMOTED` y uno `REJECTED`, y un
registro de otra organización devuelve **404**.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
./scripts/verify-e2e.sh
git commit -m "feat(api): open the manager's inbox over what could not be read"
```
