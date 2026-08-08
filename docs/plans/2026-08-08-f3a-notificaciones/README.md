# F3a — Notificaciones: plan de implementación

**Spec:** [F3a — Notificaciones](../../specs/2026-08-08-f3a-notificaciones-design.md).
**Modelo:** §6.11 y §6.15 del [spec maestro](../../specs/2026-08-07-lead-router-mvp-design.md).
**Sucede a:** F2c. El pipeline que publica los eventos es el que F2c dejó con tres etapas.

**Objetivo en una frase:** que quien tiene que actuar sobre un lead se entere sin ir a buscarlo.

**Arquitectura:** cuatro eventos de dominio nuevos y un manejador suscrito a ellos que persiste
avisos. El manejador abre su propia transacción, porque el evento se publica cuando la del caso de
uso ya confirmó — y ése es justo el punto: notificar no puede deshacer un lead guardado.

**Stack:** FastAPI, psycopg 3 con SQL crudo (marcadores `%s`), PostgreSQL 16, pytest.

## Estado

| # | Tarea | Rompe | Estado |
|---|---|---|---|
| 1 | [La entidad y su persistencia](01-entidad-y-persistencia.md) | Nada | ✅ `f730604` |
| 2 | [Los eventos y el manejador](02-eventos-y-manejador.md) | Nada, aditiva | ✅ `0d59d18` |
| 3 | [Los endpoints y el contador](03-endpoints.md) | Nada, aditiva | ✅ `f97a12b` |
| 4 | [Retirada de `webhook_dispatched`, harness y cierre](04-webhook-harness-y-cierre.md) | El campo sale de dos respuestas | ✅ `075c69e` |

**Fase cerrada el 2026-08-08.** 491 tests, guardián 4/4, harness con 130 comprobaciones, migraciones
007 y 008 reejecutadas desde volumen vacío. `webhook_dispatched` no aparece ya en `backend/` ni en
`docs/api/`.

**Un desvío del plan, con su motivo:** para dejar un lead sin asesor, la Tarea 4 proponía desactivar
temporalmente a los asesores y volver a activarlos. **No se puede: no existe endpoint de
reactivación.** `DELETE /agents/{id}` sólo desactiva y `AgentUpdate` admite únicamente `name` y
`group_id`, así que desactivar a `AGENT_1` habría dejado el harness sin forma de revertirlo. El
ejecutor creó en su lugar un asesor desechable con una regla de asignación condicionada que no
interfiere con el resto del bloque. Queda anotado como hueco del producto, no del plan.

**Nota de la Tarea 2, para quien lea el código después:** la publicación de `IntakeRejected` no puede
ir donde estaba el `return` de la rama de rechazo —dentro del bloque transaccional—, porque
publicaría antes del commit y un rollback posterior dejaría un aviso describiendo un rechazo que
nunca ocurrió. El resultado se guarda en `rejection_result` y se publica al cerrar el bloque. Pyright
marca `lead` como *possibly unbound* en ese camino: es un falso positivo, `lead` sólo se usa cuando
`rejection_result is None`, y el analizador no puede correlacionar las dos variables.

### Reparto en dos despachos

| Despacho | Tareas | Qué cierra |
|---|---|---|
| **A** | 1 + 2 | El aviso se crea y se guarda cuando pasa algo |
| **B** | 3 + 4 | El aviso se consulta, el campo que mentía desaparece y el harness lo demuestra |

## Constraints globales

| # | Constraint |
|---|---|
| C1 | **Código, docstrings, comentarios y mensajes de commit en inglés.** Los documentos de `docs/` van en español |
| C2 | **Guardián de arquitectura 4/4.** `domain/` no importa nada de fuera ni terceros; `application/` no importa `infrastructure/` ni frameworks web |
| C3 | **SQL crudo con marcadores `%s`.** Sin ORM, sin f-strings en consultas |
| C4 | **El destinatario sale del token**, nunca de la URL ni del cuerpo |
| C5 | **404, no 403**, al leer una notificación de otro destinatario |
| C6 | **Un commit por tarea**, formato `type(scope): description`, sin `Co-authored-by` |
| C7 | Los comentarios explican **por qué**, no qué |
| C9 | **Toda migración idempotente.** `CREATE TABLE` y `ADD COLUMN` con `IF NOT EXISTS` |
| **N1** | **Un fallo al notificar nunca puede hacer fallar la operación que lo disparó.** El manejador abre su propia unidad de trabajo y el publicador ya captura sus excepciones |
| **N2** | **El mensaje se compone al crear el aviso y se guarda hecho.** Componerlo al leer obligaría a cargar el lead de cada notificación y rompería la vista cuando el lead ya no exista |
| **N3** | **Sólo se crean los cuatro eventos que tienen consumidor.** Un evento que nadie escucha es una clase y un test que mantener para nada |

## El fallo que este repositorio comete una y otra vez

Un campo nuevo llega hasta el borde y **el adaptador lo tira**. Ha pasado ya cuatro veces: `email` se
serializaba como la cadena `"None"`, `source_id` no salía en la respuesta del lead, `intake_record_id`
tampoco, y `disqualification_reason` se quedó fuera de `LeadDetailResponse` hasta que un test lo
necesitó.

Ninguna lo cazó la suite: los tests comprueban códigos de estado y almacenamiento, casi nunca el
cuerpo completo de la respuesta.

**Al terminar cada tarea de esta fase, comprueba que todo campo nuevo aparece en la respuesta HTTP**,
no sólo en la entidad y en la tabla. Si un test no lo lee de vuelta por `GET`, no está probado.

## La migración es la 008

F2c ocupa la `007`. Esta fase escribe `008_notifications.sql`, y es la **única** migración de la
fase: la crea entera la Tarea 1.

## Todo código de error nuevo necesita fila en la tabla de estados

`exception_handlers.py` traduce códigos de dominio a HTTP con `STATUS_BY_ERROR_CODE`, y lo que no
está cae en `_DEFAULT_STATUS = 400`. En esta fase el único que lo necesita es
`NOTIFICATION_NOT_FOUND` → `404` (Tarea 3), **o C5 se rompe en silencio**.

## Harness

```bash
docker compose --profile test run --rm backend-test     # suite completa, sin --build
cd backend && uv run pytest -m unit -q                  # sin base de datos ni variables de entorno
./scripts/verify-e2e.sh                                 # negocio sobre HTTP real
```

`tests/conftest.py` **no se toca**: trunca leyendo las tablas del catálogo, así que `notifications`
entra sola.

Dentro de `verify-e2e.sh`, `bootstrap` exporta `ADMIN_TOKEN`, `TENANT_A`, `MGR_A`, `AGENT_1`,
`AGENT_2`, `TOKEN_1`, `TOKEN_2`, `MGR_B` y `AGENT_B`. Los helpers son `req`, `code`, `body`, `f`,
`check`, `section` y `await_job`. Se **amplía, nunca se reescribe**.

**Cuidado con `f()`:** sólo captura el fallo de `json.load`. Una clave ausente lanza `KeyError` y
deja la variable vacía sin ningún mensaje. Usa `d.get(...)`.

**La ingesta es asíncrona desde F2d.** Una notificación producida por una ingesta no existe hasta
que el trabajo termina: en el harness, espera con `await_job` antes de consultarla; en los tests de
Python no hace falta, porque `TestClient` ejecuta las tareas de fondo antes de devolver el control.

## Criterio de aceptación de la fase

Del spec §9, con dónde se comprueba cada uno:

| # | Criterio | Dónde |
|---|---|---|
| 1 | Al asignarse un lead, el asesor tiene una notificación no leída con el id del lead | Tarea 2 |
| 2 | Al reasignarse, la recibe el **nuevo** asesor | Tarea 2 |
| 3 | Un lead sin asesor notifica a **todos** los gestores activos | Tarea 2 |
| 4 | Un registro rechazado notifica al gestor con el id del registro | Tarea 2 |
| 5 | `GET /notifications` devuelve sólo las del que llama, con `unread_count` correcto | Tarea 3 |
| 6 | Marcar una baja el contador; marcarlas todas lo deja en cero | Tarea 3 |
| 7 | La notificación de otro destinatario da **404** | Tarea 3 |
| 8 | Un fallo en el manejador **no** hace fallar la ingesta | Tarea 2, test con un doble que lanza |
| 9 | `webhook_dispatched` no aparece en ninguna respuesta ni DTO | Tarea 4 |
| 10 | Suite en verde, guardián 4/4, `pytest -m unit` sin variables de entorno | Validación de cierre |

## Lo que esta fase NO hace

- **Mover la emisión de eventos a las entidades.** El maestro §6.15 lo pide; es una refactorización
  de patrón sin comportamiento observable, y mezclarla con la primera fase que consume eventos haría
  imposible saber cuál de los dos cambios rompió algo
- **Los otros cuatro eventos de §6.15** (`LeadQualified`, `LeadDisqualified`, `LeadDiscarded`,
  `IntakePromoted`): nadie los escucha todavía
- **SSE ni WebSocket.** Decisión D5 del maestro: el cliente sondea
- **Notificaciones por correo**, preferencias por usuario, agrupación de avisos repetidos
- **Reintento de un aviso perdido.** Sin cola no lo hay; queda en el log
- **Purga o caducidad** de notificaciones viejas
- **El webhook entrante** → F3b
- **Arreglar la conexión en autocommit compartida entre hilos.** El maestro §11.4 dice que se
  elimina y sigue ahí. Esta fase suscribe un segundo manejador al mismo publicador, así que **no la
  empeora ni la resuelve**: queda anotada
