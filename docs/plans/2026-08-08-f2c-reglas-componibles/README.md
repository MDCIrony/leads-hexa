# F2c — Reglas componibles: plan de implementación

**Spec:** [F2c — Reglas componibles](../../specs/2026-08-08-f2c-reglas-componibles-design.md).
**Contrato de los motores:** §7.0, §7.1 y §7.2 del [spec maestro](../../specs/2026-08-07-lead-router-mvp-design.md).
**Fundamento de negocio:** [El modelo de decisión](../../product/02-el-modelo-de-decision.md).
**Sucede a:** F2d, que partió `IngestLeadUseCase` en dos fases. Esta fase toca **sólo la fase 2**.

**Objetivo en una frase:** que ningún criterio comercial quede escrito en el código.

**Arquitectura:** un value object nuevo —`Criterion`— extraído de `ScoringRule`, y las tres etapas
del recorrido pasando a consumirlo. La puntuación deja de ser la única herramienta: la viabilidad
gana reglas propias que cortan el flujo, y el reparto gana condiciones además de la banda.

**Stack:** FastAPI, psycopg 3 con SQL crudo (marcadores `%s`), PostgreSQL 16, pytest.

## Estado

Una tarea por fichero, **un commit por tarea**. Este README es la parte que vincula a todas: se lee
junto al fichero de la tarea, no en lugar de él.

| # | Tarea | Rompe | Estado |
|---|---|---|---|
| 1 | [El esquema y `Criterion`](01-criterion-y-esquema.md) | Nada | ✅ `4f8f47b` |
| 2 | [La puntuación compone condiciones](02-puntuacion-componible.md) | Tests de `ScoringRule` y del CRUD | ✅ `e84da77` |
| 3 | [La etapa de viabilidad](03-viabilidad.md) | Nada, aditiva | ✅ `5a44810` |
| 4 | [Reparto por condiciones y retirada del umbral](04-reparto-y-umbral.md) | Tests del motor de asignación y de `qualify` | ✅ `ccc6a4f` |
| 5 | [Harness y cierre](05-harness-y-cierre.md) | — | ✅ `2b830f0` |

**Fase cerrada el 2026-08-08.** 462 tests, guardián 4/4, harness con 105 comprobaciones, migraciones
reejecutadas desde volumen vacío. Un desvío del plan: **`verify-e2e.sh` nunca llegó a ponerse rojo**
al retirar el umbral, porque ningún lead del harness anota menos de 40 y ninguna sección crea reglas
de asignación, así que el corte de 30 no decidía nada observable. El Paso 1 de la Tarea 5 no tuvo
nada que reparar.

### Reparto en tres despachos

| Despacho | Tareas | Qué cierra |
|---|---|---|
| **A** | 1 + 2 | La gramática de condiciones existe y la puntuación ya la usa |
| **B** | 3 | La etapa que hoy no existe, con su CRUD y su corte del flujo |
| **C** | 4 + 5 | El reparto discrimina por atributo, el umbral desaparece y el harness lo demuestra |

---

## Tres decisiones que el spec deja abiertas y este plan cierra

Están aquí y no en una tarea porque vinculan a varias.

**Las condiciones se guardan en JSONB, no en una tabla aparte.** El spec §9 dice «tabla de
condiciones». Se descarta: un `Criterion` se lee siempre entero junto a su regla y nunca se consulta
por separado —no hay ninguna consulta del tipo «qué reglas usan este campo» en el alcance—, así que
una tabla por join añadiría tres esquemas, tres joins y tres órdenes de carga sin comprador. El
repositorio ya persiste `scoring_rules.value` y `assignment_rules.target_agent_ids` en JSONB: esta
decisión sigue el precedente en lugar de abrir uno nuevo.

**El motivo del descarte vive en el lead.** El maestro §7.0 dice que el lead queda `DISQUALIFIED`
«con el motivo de esa regla» y no dice dónde. Se añade `Lead.disqualification_reason: Optional[str]`
y su columna. Guardar el `rule_id` en su lugar haría que borrar la regla dejara al lead sin poder
explicarse, que es el mismo defecto que `ScoreBreakdown` resolvió persistiendo el nombre.

**`qualify()` se queda sin argumentos.** Al retirar los dos umbrales, su rama `DISQUALIFIED` pasa al
motor de viabilidad, que es quien tiene el motivo. Lo que queda es la transición `NEW → QUALIFIED`,
y es lo que vuelve cierto el criterio de aceptación 5: hoy un lead entre ambos umbrales no entra en
ninguna rama y se queda en `NEW` para siempre.

## Constraints globales

Vinculan a **todas** las tareas. Un incumplimiento es un fallo de la tarea, no un detalle menor.

| # | Constraint |
|---|---|
| C1 | **Código, docstrings, comentarios y mensajes de commit en inglés.** Los documentos de `docs/` van en español |
| C2 | **Guardián de arquitectura 4/4.** `domain/` no importa nada de fuera ni terceros; `application/` no importa `infrastructure/` ni frameworks web |
| C3 | **SQL crudo con marcadores `%s`.** Sin ORM, sin f-strings en consultas |
| C4 | **La organización sale del token**, nunca de la URL ni del cuerpo |
| C5 | **404, no 403**, al leer una entidad de otra organización |
| C6 | **Un commit por tarea**, formato `type(scope): description`, sin `Co-authored-by` |
| C7 | Los comentarios explican **por qué**, no qué |
| C9 | **Toda migración idempotente.** `test_migration_runner.py` dropea `schema_migrations` dejando las tablas, así que reejecuta cada fichero entero. `CREATE TABLE` y `ADD COLUMN` llevan `IF NOT EXISTS`; `ADD CONSTRAINT` no admite esa sintaxis y necesita guarda manual contra `pg_constraint` |
| **R1** | **La lista blanca de campos evaluables se conserva y se comparte.** No es una limitación de negocio sino una frontera de seguridad: sin ella una regla podría condicionar sobre `tenant_id`, convirtiendo un dato de sistema en criterio comercial |
| **R2** | **Una regla se cumple cuando se cumplen TODAS sus condiciones.** No hay operador `OR`, ni modo configurable por regla, ni anidamiento. Las alternativas se escriben como reglas separadas |
| **R3** | **Una lista de condiciones vacía se rechaza en `DisqualificationRule`.** Una regla que siempre se cumple descalificaría todo. En `AssignmentRule` la lista vacía **sí** es válida: significa que la regla sólo discrimina por banda |

## La migración es la 007, no la 006

El spec §9 dice «Migración 006». **Ya la ocupó F2d** (`006_intake_jobs.sql`). Esta fase escribe
`007_composable_rules.sql`, y es la **única** migración de la fase: la crea entera la Tarea 1 y las
demás sólo la consumen.

## Todo código de error nuevo necesita fila en la tabla de estados

`exception_handlers.py` traduce códigos de dominio a HTTP con `STATUS_BY_ERROR_CODE`, y lo que no
está en ella cae en `_DEFAULT_STATUS = 400`. Un código de «no encontrado» sin fila devuelve `400` en
vez de `404` y rompe C5 **en silencio**. Ya pasó en F2b.

En esta fase el único que lo necesita es `DISQUALIFICATION_RULE_NOT_FOUND` → `404` (Tarea 3). Los
demás (`INVALID_RULE_CONDITIONS`, `FIELD_NOT_SCORABLE`, `INVALID_RULE_VALUE`) quieren `400`, que es
el valor por defecto: **no los añadas**.

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
`check`, `section` y `await_job`. Se **amplía, nunca se reescribe**.

**Cuidado con `f()`:** sólo captura el fallo de `json.load`. Una expresión como `d["campo"]` sobre una
respuesta que no lleva esa clave lanza `KeyError`, la variable queda vacía **sin ningún mensaje**, y
el fallo aparece mucho más abajo. Usa `d.get(...)` en las expresiones nuevas.

## Criterio de aceptación de la fase

Del spec §10, con dónde se comprueba cada uno:

| # | Criterio | Dónde |
|---|---|---|
| 1 | «Sin teléfono **y** sin correo → descartar», y un lead con sólo teléfono **no** se descarta | Tarea 3, test explícito + `verify_f2c` |
| 2 | El lead descartado por regla muestra el **motivo de la regla**, no una puntuación | Tarea 3 |
| 3 | «Los de este canal, a este equipo» se cumple sin tocar puntuaciones | Tarea 4 |
| 4 | Ningún corte de puntuación queda fuera de la interfaz | Tarea 4 |
| 5 | No existe ningún lead procesado en estado `NEW` | Tarea 4 |
| 6 | Las reglas escritas antes de esta fase siguen funcionando sin intervención | Tarea 2, la migración rellena `conditions` |
| 7 | Suite en verde sin banderas, guardián 4/4, `pytest -m unit` sin variables de entorno | Validación de cierre |

## Lo que esta fase NO hace

Escribirlo evita que un subagente lo añada por iniciativa propia:

- **El constructor visual de reglas.** El valor está en el modelo de composición; el lienzo es una
  capa encima, y va en F4 como mucho
- **La biblioteca de reglas predefinidas** por sector
- **El rango acotado de puntuación.** Hoy nada impide una regla de ±9999 y así se queda; catalogado
  en [`product/03 §6`](../../product/03-dominio-y-organizacion.md)
- **Anidamiento de condiciones** (`(A y B) o (C y D)` dentro de una regla). La forma normal
  disyuntiva ya lo expresa con dos reglas
- **Un modo configurable por regla** (`todas / alguna`). Añade un concepto que el gestor debe
  aprender para cubrir un caso que ya cubren dos reglas
- **`PATCH` y `DELETE` de reglas de puntuación.** Hoy no existen y esta fase no los añade: el
  alcance es la composición, no completar el CRUD
- **Deduplicación de contactos** → fuera del MVP, con su razón en `product/mejoras-futuras/`
- **Notificaciones** → F3a
