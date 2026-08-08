# F2b — Ingesta unificada: plan de implementación

**Spec:** [F2b — Ingesta unificada](../../specs/2026-08-08-f2b-ingesta-unificada-design.md).
**Precede a:** [F2c — Reglas componibles](../../specs/2026-08-08-f2c-reglas-componibles-design.md).

**Objetivo en una frase:** que nada de lo que entra se pierda, y que nadie ingeste sin credencial.

**Arquitectura:** tres entidades nuevas —`LeadSource`, `IntakeRecord`, `IntakeError`— y un único
recorrido de ingesta que persiste el payload **antes** de intentar interpretarlo. El formulario y la
carga masiva dejan de tener caminos propios. `LeadStatus.FAILED` desaparece y su papel lo asume
`IntakeRecord.REJECTED`, que sí se persiste y sí se revisa.

**Stack:** FastAPI, psycopg 3 con SQL crudo (marcadores `%s`), PostgreSQL 16, pytest.

## Estado

Una tarea por fichero. Cada una se despacha a un subagente, deja la suite en verde y hace **un
commit**. Este README es la parte que vincula a todas: se lee junto al fichero de la tarea, no en
lugar de él.

| # | Tarea | Estado |
|---|---|---|
| 1 | [Migración 005, `LeadSource` y el origen del lead](01-lead-source.md) | ✅ `b5e2923` |
| 2 | [El correo deja de ser obligatorio](02-correo-opcional.md) | ✅ `91f4807` |
| 3 | [`IntakeRecord` e `IntakeError`](03-intake-record.md) | ✅ `6d24369` |
| 4 | [El pipeline unificado y la retirada de `FAILED`](04-pipeline-unificado.md) | ✅ `0be1127` |
| 5a | [La organización sale del token](05a-autenticacion.md) | ✅ `b34a534`, `34e84aa` |
| 5b | [CRUD de orígenes](05b-crud-origenes.md) | ✅ `921ec8c` |
| 5c | [La bandeja de entrada](05c-bandeja.md) | ✅ `f4f9ea6` |
| 6 | [Harness y cierre](06-harness-y-cierre.md) | ✅ `c79a6cb`, `2af6265` |

Trabajo previo, fuera de las tareas: `edba1cc` desacopla el harness del orden de importación,
`f1d7ffa` fija el intérprete local a 3.12, `0a095e4` mueve la configuración de Pyright a la raíz y
`4844cd2` expone el identificador de registro que los esquemas HTTP descartaban.

**Por qué 5a, 5b y 5c y no una sola tarea:** 5a es el único despacho que rompe comportamiento
existente —cambia rutas y actualiza cuatro pruebas de extremo a extremo—; 5b y 5c sólo añaden. Un
revisor puede rechazar uno sin bloquear los otros dos.

---

## Nota operativa: esta fase exige base limpia

La migración `005` añade `leads.source_id` como `NOT NULL` con clave foránea. Sobre una base con
leads anteriores **la migración falla en el arranque**, y debe fallar: un lead sin origen es
exactamente el dato incoherente que la columna existe para impedir.

No hay backfill que escribir — el spec §9 lo fija: *«No hay datos que preservar»*. Al validar:

```bash
docker compose down -v && docker compose up -d      # o ./scripts/verify-e2e.sh --reset
```

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
| C7 | Los comentarios explican **por qué**, no qué. Sin verborrea |
| C8 | **No se añade ninguna exigencia de contactabilidad** al hacer el correo opcional. Nada de «al menos una vía de contacto»: reproduciría el problema con otro nombre y dejaría la bandeja de descalificados vacía justo en el caso que la justifica |
| C9 | **Toda migración tiene que ser idempotente.** `test_migration_runner.py` dropea `schema_migrations` dejando las tablas en pie, así que reejecuta cada fichero entero. `CREATE TABLE` y `ADD COLUMN` llevan `IF NOT EXISTS`; `ADD CONSTRAINT` no admite esa sintaxis y necesita una guarda manual contra `pg_constraint` |

## Harness

```bash
# Suite completa. NO lleva --build: src/, tests/ y migrations/ están montados.
# Reconstruir sólo si cambian pyproject.toml o uv.lock.
docker compose --profile test run --rm backend-test

# Subconjunto: `run` REEMPLAZA el CMD, no lo extiende.
docker compose --profile test run --rm backend-test pytest -q tests/unit

# Unitarios sin variables de entorno (deben pasar fuera de Docker)
cd backend && uv run pytest -m unit -q

# Verificación de negocio (~3 s). El contenedor recarga en caliente lo que
# cambies en src/, así que no hace falta ni --build ni restart.
./scripts/verify-e2e.sh
```

`tests/conftest.py` **no se toca**: fija `DATABASE_URL` y `JWT_SECRET` una sola vez y trunca leyendo
las tablas del catálogo, así que una tabla nueva entra sola. No declares variables de entorno en
ningún fichero de test.

Dentro de `verify-e2e.sh`, `bootstrap` exporta las variables sobre las que se construye todo lo
demás: `ADMIN_TOKEN`, `TENANT_A`, `MGR_A`, `AGENT_1`, `AGENT_2`, `TOKEN_1`, `TOKEN_2` (los dos
asesores de A), `MGR_B` y `AGENT_B`. Los helpers son `req`, `code`, `body`, `f`, `check` y `section`.
Se **amplía, nunca se reescribe**: cada fase añade su `verify_fN` y la llama desde `main`.

## Criterio de aceptación de la fase

Del spec §10, con dónde se comprueba cada uno:

| # | Criterio | Dónde |
|---|---|---|
| 1 | Un payload sin correo genera un lead que existe y es visible | `verify_f2b` 4 |
| 2 | Un payload ininterpretable queda en la bandeja con el detalle, y el gestor lo corrige y lo promueve | `verify_f2b` 6-9, `test_intake_inbox.py` |
| 3 | Una petición de ingesta sin credencial es rechazada | `verify_f2b` 1-2, `test_intake_authentication.py` |
| 4 | Formulario y carga masiva recorren el mismo pipeline | `verify_f2b` 10, `test_unified_intake_pipeline.py` |
| 5 | El gestor responde «¿de dónde vienen mis leads?» | `verify_f2b` 3, 5, 11-12 |
| 6 | Suite en verde sin banderas, guardián 4/4, `pytest -m unit` sin variables de entorno | Validación de cierre |

## Lo que esta fase NO hace

Escribirlo evita que un subagente lo añada por iniciativa propia:

- **Reglas de descalificación** que aprovechen el correo opcional → F2c
- **Retirada de los dos umbrales del código** → F2c. No se hacen configurables: desaparecen
- **Resolución de identidad** (el mismo contacto entrando dos veces) → fuera del alcance del MVP,
  ver [mejoras futuras](../../product/mejoras-futuras/01-identidad-del-contacto.md)
- **Adaptador de webhook entrante** → F3b. Aquí sólo se crean el valor `WEBHOOK` del enum y la
  columna `secret_hash`
- **Notificaciones** → F3a
- **Frontend** → F4
