# F2d — Recepción y procesamiento separados: plan de implementación

**Spec:** [F2d — Recepción y procesamiento separados](../../specs/2026-08-08-f2d-recepcion-y-procesamiento-design.md).
**Fundamento conceptual:** [Dónde se valida lo que entra](../../conceptos/01-donde-se-valida-lo-que-entra.md).
**Precede a:** [F2c — Reglas componibles](../../specs/2026-08-08-f2c-reglas-componibles-design.md), que
reescribe el motor de reglas dentro del mismo caso de uso que esta fase parte en dos.

**Objetivo en una frase:** que recibir un lead y procesarlo dejen de compartir transacción, para que
ningún fallo al procesar pueda destruir la constancia de haber recibido.

**Arquitectura:** una entidad nueva —`IntakeJob`— y el recorrido partido en dos fases con
transacciones distintas. La fase 1 persiste y responde `202`; la fase 2 corre en segundo plano y
marca lo que persistió la fase 1. `IngestLeadUseCase` deja de crear el registro y pasa a recibirlo.

**Stack:** FastAPI, psycopg 3 con SQL crudo (marcadores `%s`), PostgreSQL 16, pytest.

## Estado

Una tarea por fichero. Cada una se despacha a un subagente, deja la suite en verde y hace **un
commit**. Este README es la parte que vincula a todas: se lee junto al fichero de la tarea, no en
lugar de él.

| # | Tarea | Rompe | Estado |
|---|---|---|---|
| 1 | [El modelo: `IntakeJob`](01-modelo-intake-job.md) | Nada | ⏳ **siguiente** |
| 2 | [Las dos fases en la aplicación](02-las-dos-fases.md) | Tests unitarios del pipeline | ⏳ |
| 3 | [La ingesta individual responde 202](03-ingesta-individual-asincrona.md) | **7 ficheros e2e** | ⏳ |
| 4 | [La carga masiva responde 202](04-carga-masiva-asincrona.md) | Tests del batch | ⏳ |
| 5 | [Consulta y reproceso](05-consulta-y-reproceso.md) | Nada, aditiva | ⏳ |
| 6 | [Harness y cierre](06-harness-y-cierre.md) | — | ⏳ |

**Por qué la 3 va sola:** es la única que rompe un contrato público. Aislarla permite revisarla
aparte de las cuatro que sólo añaden.

---

## El dato que abarata toda la fase

Comprobado empíricamente contra la versión de FastAPI instalada:

```
status: 202
background ya corrio cuando el test recupera el control: True
```

**`TestClient` ejecuta las tareas de fondo antes de devolver el control.** Las pruebas de extremo a
extremo no necesitan sondeo ni `sleep`: hacen una petición más y el resultado ya está.

**`scripts/verify-e2e.sh` sí necesita sondear**, porque habla HTTP real contra el contenedor. Sondeo
con límite de intentos, nunca un `sleep` fijo.

## Constraints globales

Vinculan a **todas** las tareas. Un incumplimiento es un fallo de la tarea, no un detalle menor.

| # | Constraint |
|---|---|
| C1 | **Código, docstrings, comentarios y mensajes de commit en inglés.** Los documentos de `docs/` van en español |
| C2 | **Guardián de arquitectura 4/4.** `domain/` no importa nada de fuera ni terceros; `application/` no importa `infrastructure/` ni frameworks web |
| C3 | **SQL crudo con marcadores `%s`.** Sin ORM, sin f-strings en consultas |
| C4 | **La organización sale del token, nunca de la URL ni del cuerpo** |
| C5 | **404, no 403**, al leer una entidad de otra organización |
| C6 | **Un commit por tarea**, formato `type(scope): description`, sin `Co-authored-by` |
| C7 | Los comentarios explican **por qué**, no qué |
| C9 | **Toda migración idempotente.** `test_migration_runner.py` dropea `schema_migrations` dejando las tablas, así que reejecuta cada fichero entero. `CREATE TABLE` y `ADD COLUMN` llevan `IF NOT EXISTS`; `ADD CONSTRAINT` no admite esa sintaxis y necesita guarda manual contra `pg_constraint` |
| **V1** | **No se añade ninguna validación nueva al esquema HTTP de ingesta.** Cada regla ahí habrá que arrancarla cuando la definición del lead sea por organización, y mientras tanto descarta datos en silencio |
| **V2** | **El payload se guarda tal como llega, sin normalizar** |
| **V3** | **El rechazo no es terminal.** Un registro rechazado debe poder reinterpretarse sin reenviar nada. El modelo ya lo cumple desde F2b |

`C8` era de F2b y se cumplió; no se renumera para que las referencias cruzadas sigan valiendo.

**V1 tiene una consecuencia activa en esta fase:** la validación de formato de correo del esquema de
entrada **se retira** en la Tarea 3. Es una copia peor de la del dominio y es la que producía un `422`
que descartaba el payload sin dejar rastro.

## Todo código de error nuevo necesita fila en la tabla de estados

`exception_handlers.py` traduce códigos de dominio a HTTP con `STATUS_BY_ERROR_CODE`, y lo que no
está en ella cae en `_DEFAULT_STATUS = 400`. Un código de «no encontrado» sin fila devuelve `400` en
vez de `404` y rompe C5 **en silencio**, con el test fallando por un motivo que no está donde lo
buscarías. Ya pasó una vez en F2b.

## Harness

```bash
# Suite completa. NO lleva --build: src/, tests/ y migrations/ están montados.
docker compose --profile test run --rm backend-test

# Subconjunto: `run` REEMPLAZA el CMD, no lo extiende.
docker compose --profile test run --rm backend-test pytest -q tests/unit

# Unitarios sin variables de entorno (deben pasar fuera de Docker)
cd backend && uv run pytest -m unit -q

# Verificación de negocio. La API recarga en caliente: no hace falta --build ni restart.
./scripts/verify-e2e.sh
```

`tests/conftest.py` **no se toca**: fija `DATABASE_URL` y `JWT_SECRET` una sola vez y trunca leyendo
las tablas del catálogo, así que una tabla nueva entra sola.

Dentro de `verify-e2e.sh`, `bootstrap` exporta `ADMIN_TOKEN`, `TENANT_A`, `MGR_A`, `AGENT_1`,
`AGENT_2`, `TOKEN_1`, `TOKEN_2`, `MGR_B` y `AGENT_B`. Los helpers son `req`, `code`, `body`, `f`,
`check` y `section`. Se **amplía, nunca se reescribe**.

## Criterio de aceptación de la fase

Del spec §9, con dónde se comprueba cada uno:

| # | Criterio | Dónde |
|---|---|---|
| 1 | La ingesta individual responde `202` con un `job_id`, y por ese job se llega al lead | `verify_f2d` 1-3, Tarea 3 |
| 2 | Una carga masiva responde `202` antes de parsear, y al terminar tiene contadores correctos | `verify_f2d` 4-6, Tarea 4 |
| 3 | Un payload ininterpretable deja su registro `REJECTED` con detalle por campo, y el job `COMPLETED` con `failed ≥ 1` | `verify_f2d` 7-8 |
| 4 | Un job interrumpido queda visible y `reprocess` lo termina sin duplicar leads | Tarea 5 |
| 5 | Ningún fallo durante el procesamiento borra el registro creado en la recepción | Tarea 2, test explícito |
| 6 | Suite en verde sin banderas, guardián 4/4, `pytest -m unit` sin variables de entorno | Validación de cierre |

## Lo que esta fase NO hace

Escribirlo evita que un subagente lo añada por iniciativa propia:

- **Colas ni trabajadores externos.** El trabajo de fondo es el del framework, en proceso
- **Reintento automático.** Un job atascado se relanza a mano
- **Registrar peticiones que no superan la validación de esquema.** Sin arreglo dentro de este
  modelo; ver [mejoras futuras](../../product/mejoras-futuras/02-la-definicion-del-lead-por-organizacion.md)
- **Notificar al emisor cuando el trabajo termina.** El cliente consulta; nadie le avisa
- **Reprocesar por cambio de configuración** («relanza todo lo de esta fuente con el mapeo nuevo»).
  El modelo queda preparado; la operación masiva por fuente no se construye aquí
- **Retirada de los dos umbrales** → F2c
- **Frontend** → F4
