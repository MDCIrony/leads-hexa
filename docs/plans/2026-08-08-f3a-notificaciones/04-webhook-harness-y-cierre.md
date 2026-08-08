# Tarea 4 — Retirada de `webhook_dispatched`, harness y cierre

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Retira el campo que el spec maestro §2.2 marca como mentira, añade `verify_f3a` y cierra la fase.

## Ficheros

**Modificar:**

| Fichero | Qué cambia |
|---|---|
| `backend/src/application/dtos/commands.py` | `LeadProcessedResult` pierde `webhook_dispatched` |
| `backend/src/application/use_cases/ingest_lead_use_case.py` | Los dos `return` dejan de calcularlo |
| `backend/src/infrastructure/adapters/input/api/schemas.py` | `LeadProcessedResponse` pierde el campo |
| `backend/src/infrastructure/adapters/input/api/intake_router.py` | Los mapeos dejan de pasarlo |
| `backend/tests/unit/application/test_ingest_lead_use_case.py` | La aserción sobre el campo se sustituye |
| `scripts/verify-e2e.sh` | Añade `verify_f3a` |
| `docs/specs/2026-08-08-f3a-notificaciones-design.md` | `**Estado:** propuesto` → `implementado` |
| `docs/specs/2026-08-07-lead-router-mvp-design.md` | §15: F3a cerrada. §2.2: la fila de `webhook_dispatched` deja de estar pendiente |
| `docs/api/endpoints.md` | Las tres rutas de notificaciones; el campo retirado |
| `docs/api/error_handling.md` | `NOTIFICATION_NOT_FOUND` |

**No toques `docs/product/`.**

## Paso 1: el campo se va

`webhook_dispatched` se calcula hoy como `True if self.event_publisher else False`, que no comprueba
nada sobre el webhook: el publicador siempre se inyecta, así que el campo es `true` en toda ingesta
aunque la organización no tenga webhooks y aunque la entrega HTTP haya fallado.

**Se retira, no se corrige.** Para decir la verdad, el caso de uso tendría que conocer el resultado
de una entrega hecha por un manejador desacoplado, y eso deshace el patrón que el pub/sub existe
para sostener. Un campo que no se puede calcular con honestidad no debe estar en la respuesta.

Bórralo de los cuatro sitios de la tabla. En `test_ingest_lead_use_case.py` hay una aserción
`result.webhook_dispatched is True` **junto a** una sobre `len(dispatcher.dispatched_events) == 1`:
borra la primera y **conserva la segunda**, que es la que comprueba algo real. Esa pareja es
justamente la que demostraba que el campo era independiente de la entrega.

## Paso 2: `verify_f3a`

Función nueva, llamada desde `main` después de `verify_f2c`.

La ingesta es asíncrona: espera con `await_job` antes de consultar cualquier notificación, o
comprobarás la campana antes de que el trabajo la haya llenado.

| # | Comprobación | Esperado |
|---|---|---|
| 1 | Un asesor consulta sus notificaciones al empezar | `200`, con su contador de partida |
| 2 | Se ingiere un lead que se le asigna | Su `unread_count` sube |
| 3 | La notificación más reciente | `kind` es `LEAD_ASSIGNED` y trae el `lead_id` |
| 4 | El otro asesor | **No** ve esa notificación |
| 5 | Marcar una como leída | `204`, y el contador baja |
| 6 | Marcar como leída una del otro asesor | **404** |
| 7 | Marcar todas | `204`, y el contador queda en **cero** |
| 8 | Un lead que no encuentra asesor | El **gestor** recibe `LEAD_LEFT_UNASSIGNED` |
| 9 | Un correo mal formado ingerido | El gestor recibe `INTAKE_REJECTED` con el registro |
| 10 | El gestor de otra organización | No ve ninguna de las anteriores |

Para la 8, la forma fiable de dejar un lead sin asesor es **desactivar temporalmente a los asesores**
de la organización, ingerir, y volver a activarlos. Ingerir con una puntuación fuera de banda ya no
sirve: desde F2c no hay umbral fijo y el corte lo pone la banda más baja de las reglas.

**Cuidado con `f()`:** una clave ausente deja la variable vacía sin mensaje. Usa `d.get(...)`.

Como el harness comparte organización entre bloques, `verify_f3a` va **al final** y deja las
notificaciones marcadas como leídas al terminar, para no ensuciar a quien venga después.

## Paso 3: documentación

- El spec de F3a: `propuesto` → `implementado`
- Maestro §15: fila de F3a cerrada, con fecha
- Maestro §2.2: la fila «`webhook_dispatched` miente / ⏳ F3a» pasa a resuelta, anotando que **el
  campo se retiró** en vez de corregirse, con su motivo en una línea
- `docs/api/endpoints.md`: las tres rutas de notificaciones con su forma de respuesta, y que
  `LeadProcessedResponse` ya no lleva `webhook_dispatched`
- `docs/api/error_handling.md`: `NOTIFICATION_NOT_FOUND` → 404

## Validación de cierre

Desde base limpia: comprueba que las migraciones 007 y 008 son idempotentes (C9).

```bash
docker compose down -v && docker compose up -d
docker compose --profile test run --rm backend-test     # suite completa, sin banderas
cd backend && uv run pytest -m unit -q                  # sin base de datos ni variables de entorno
cd .. && ./scripts/verify-e2e.sh --reset                # F2a + F2b + F2d + F2c + F3a en verde
git commit -m "test: cover notifications in the business harness"
```

Comprobación final antes de dar la fase por cerrada:

```bash
rg -n 'webhook_dispatched' backend/ docs/api/
```

Debe devolver **cero resultados en `backend/src` y en `docs/api/`**. Una aparición superviviente
significa que el campo sigue vivo en algún camino.
