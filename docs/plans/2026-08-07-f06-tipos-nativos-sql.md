# F0.6 — Tipos nativos de PostgreSQL: Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el esquema use los tipos que PostgreSQL ofrece —`UUID`, `TIMESTAMPTZ`, `NUMERIC`, `JSONB`, `BOOLEAN`— en lugar de guardarlo todo como `TEXT`, y que los repositorios dejen de traducir en cada lectura y cada escritura.

**Architecture:** El esquema actual es una traducción literal de uno de SQLite: todo `TEXT`, los booleanos como `0`/`1`, las fechas como cadenas ISO y los atributos como JSON serializado a mano. Eso obliga a cada repositorio a convertir en ambos sentidos, y desactiva las garantías que la base de datos podría dar por sí sola. Como no hay datos que preservar, las migraciones `001` y `002` se **corrigen en su sitio** en vez de encadenar una `003` con `ALTER TABLE ... USING`: el esquema nace bien tipado y se lee como lo que debería haber sido.

**Tech Stack:** Python 3.12+, psycopg 3 (raw SQL, sin ORM), PostgreSQL 16, pytest, uv, Docker Compose.

**Estado de partida:** F0.5 cerrada. 188 tests en verde, guardián de arquitectura 4/4, dos planos separados.

## Global Constraints

- Todo el código, nombres, docstrings y comentarios **en inglés**. La documentación en español.
- **Prohibido cualquier ORM.** SQL parametrizado sobre `psycopg` 3, marcadores `%s`.
- `domain/` no importa nada fuera de la biblioteca estándar.
- `application/` importa sólo de `domain/` y de la biblioteca estándar. **Nunca** de `infrastructure/`.
- **El guardián `tests/architecture/` debe permanecer en 4/4 en todo momento.**
- `pytest -m unit` debe pasar sin base de datos, sin red y sin variables de entorno.
- Los comentarios explican el **porqué**, nunca el qué.
- Mensajes de commit en inglés, `type(scope): description`. **Sin** `Co-authored-by`.
- No `git push`, no ramas nuevas. Rama de trabajo: `repo-status-mvp`.
- **Puertos del host:** PostgreSQL en **5433**, API en **8001**. Dentro de la red de compose siguen siendo 5432 y 8000.

```bash
export DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export TEST_DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export JWT_SECRET=test-secret-do-not-use-in-production
```

## Decisión de partida: se corrigen las migraciones, no se encadena una nueva

Los datos que hay en la base son residuo de pruebas. No hay nada que preservar, y cuando el proyecto se despliegue de verdad las migraciones se aplicarán todas juntas sobre una base vacía. Escribir una `003` con `ALTER TABLE ... USING` sería código de migración de datos que nunca migrará datos reales: sobreingeniería.

**Consecuencia operativa:** aplicar F0.6 exige `docker compose down -v`. El runner registra las migraciones aplicadas por nombre en `schema_migrations`, así que una base que ya tenga `001_baseline_schema.sql` anotada **no** la reaplicará aunque su contenido haya cambiado. Está asumido y es el flujo que ya usamos.

## Agrupación sugerida en despachos

Tres tareas, **un solo despacho**. Las tareas 1 y 2 forman un único ciclo rojo→verde: cambiar el esquema rompe los repositorios de inmediato, y no tiene sentido revisarlas por separado.

| Bloque | Tareas | Validación |
|---|---|---|
| A | 1 + 2 + 3 | **Docker + curl + base de datos**, circuito completo |

## Mapa de ficheros

**Se modifican:** `migrations/001_baseline_schema.sql` · `migrations/002_tenants.sql` · `infrastructure/adapters/output/persistence/raw_sql_{lead,agent,rule,tenant,webhook}_repository.py` · `tests/integration/` donde se inserten filas a mano.

**No se tocan:** el dominio, la aplicación, los routers. Los tipos de la base son un detalle del adaptador de salida, y que este cambio no obligue a tocar nada por encima es precisamente la prueba de que la inversión de dependencias funciona.

---

## Task 1: Migraciones con tipos nativos

**Files:**
- Modify: `backend/migrations/001_baseline_schema.sql` (completo)
- Modify: `backend/migrations/002_tenants.sql` (columnas `id`, `is_active`, `created_at`)

**Interfaces:**
- Produces: el esquema con `UUID`, `TIMESTAMPTZ`, `NUMERIC(14,2)`, `JSONB` y `BOOLEAN`, que la Task 2 consume desde los repositorios.

- [ ] **Step 1: Reescribir la migración base**

Sustituir el contenido completo de `backend/migrations/001_baseline_schema.sql` por:

```sql
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT NOT NULL,
    -- NUMERIC, not DOUBLE PRECISION: a budget is money, and binary floating
    -- point cannot represent it exactly.
    budget NUMERIC(14, 2) NOT NULL,
    industry TEXT NOT NULL,
    custom_attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    phone TEXT,
    score INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    assigned_agent_id UUID,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS scoring_rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    name TEXT NOT NULL,
    field TEXT NOT NULL,
    operator TEXT NOT NULL,
    value TEXT NOT NULL,
    score_delta INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS routing_rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    min_score INTEGER NOT NULL,
    target_team TEXT NOT NULL,
    assignment_strategy TEXT NOT NULL,
    target_agent_ids JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    team TEXT NOT NULL,
    active_leads_count INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    role TEXT NOT NULL DEFAULT 'AGENT',
    hashed_password TEXT,
    tenant_id UUID
);

CREATE TABLE IF NOT EXISTS webhook_configs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    target_url TEXT NOT NULL,
    secret_token TEXT NOT NULL
);
```

`routing_rules.target_agent_ids` queda como `JSONB` y no como `UUID[]` a propósito: F1 sustituye esta tabla entera por `assignment_rules`, y tiparla con más finura sería trabajo que F1 tira a la basura.

- [ ] **Step 2: Corregir la migración de organizaciones**

En `backend/migrations/002_tenants.sql`, sustituir sólo la definición de la tabla. Los tres índices que vienen después **se dejan intactos**:

```sql
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL
);
```

- [ ] **Step 3: Verificar que el esquema se aplica**

```bash
docker compose down -v
docker compose up -d db
docker compose exec -T db psql -U postgres -d leads_db -c "SELECT 1"
```

Luego, con el backend aún sin arrancar, aplicar las migraciones desde el host:

```bash
cd backend
export DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_db
uv run python -c "
import sys; sys.path.insert(0,'src')
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.migration_runner import run_migrations
db = RawSqlDatabase(dsn='postgresql://postgres:postgrespassword@localhost:5433/leads_db')
run_migrations(db)
db.close()
"
```

Expected: sin errores.

- [ ] **Step 4: Comprobar los tipos resultantes**

```bash
docker compose exec -T db psql -U postgres -d leads_db -c "
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='public' AND column_name IN ('id','tenant_id','created_at','budget','custom_attributes','is_active','assigned_agent_id')
ORDER BY table_name, column_name;"
```

Expected: `uuid` para los identificadores, `timestamp with time zone` para `created_at`, `numeric` para `budget`, `jsonb` para `custom_attributes`, `boolean` para `is_active`. Ni un solo `text` entre ellos.

- [ ] **Step 5: Verificar que los repositorios ahora fallan**

```bash
cd backend
export DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export TEST_DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/leads_test
export JWT_SECRET=test-secret-do-not-use-in-production
uv run pytest -m integration -q
```

Expected: FALLOS. Es lo que se busca en este paso — los repositorios siguen enviando cadenas donde la base espera `uuid`, `timestamptz` y `boolean`. Los errores típicos serán `invalid input syntax for type uuid` y `column "is_active" is of type boolean but expression is of type integer`.

**Si en cambio pasan todos, detente y reporta**: significaría que la migración no se aplicó a la base de tests.

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/
git commit -m "refactor(db): give the schema native types instead of storing everything as text"
```

---

## Task 2: Repositorios sin traducción

**Files:**
- Modify: `backend/src/infrastructure/adapters/output/persistence/raw_sql_lead_repository.py`
- Modify: `backend/src/infrastructure/adapters/output/persistence/raw_sql_agent_repository.py`
- Modify: `backend/src/infrastructure/adapters/output/persistence/raw_sql_rule_repository.py`
- Modify: `backend/src/infrastructure/adapters/output/persistence/raw_sql_tenant_repository.py`
- Modify: `backend/src/infrastructure/adapters/output/persistence/raw_sql_webhook_repository.py`
- Modify: los tests de `backend/tests/integration/` que inserten filas a mano

**Interfaces:**
- Consumes: el esquema tipado de la Task 1.
- Produces: los mismos métodos de siempre, con las mismas firmas. **Ninguna interfaz cambia** — este es el punto: el dominio y la aplicación no se enteran.

- [ ] **Step 1: Entender qué desaparece**

Tres traducciones dejan de hacer falta, en ambos sentidos:

| Hoy, al escribir | Hoy, al leer | A partir de ahora |
|---|---|---|
| `str(lead.id)` | `UUID(row["id"])` implícito en `create()` | Pasar el `UUID` tal cual; psycopg lo adapta |
| `lead.created_at.isoformat()` | `datetime.fromisoformat(row["created_at"])` | Pasar el `datetime`; vuelve como `datetime` |
| `json.dumps(lead.custom_attributes)` | `json.loads(row["custom_attributes"])` | Pasar el `dict`; vuelve como `dict` |
| `1 if agent.is_active else 0` | `bool(row["is_active"])` | Pasar el `bool`; vuelve como `bool` |

Un `UUID` de Python, un `datetime`, un `dict` y un `bool` viajan directamente por psycopg 3 hacia columnas `uuid`, `timestamptz`, `jsonb` y `boolean`. La traducción manual era el precio de un esquema que fingía ser SQLite.

**Cuidado con los `dict`:** psycopg no adapta `dict` a `jsonb` por sí solo — hay que envolverlo en `Jsonb`. Importar `from psycopg.types.json import Jsonb` y pasar `Jsonb(lead.custom_attributes)`. Al leer, en cambio, `jsonb` vuelve como `dict` sin ayuda.

**Cuidado con los objetos de valor:** `lead.id` es un `LeadId`, no un `UUID`. Donde hoy hay `str(lead.id)` debe quedar `lead.id.value`, que es el `UUID` real. Lo mismo con `tenant_id`, `assigned_agent_id` y los identificadores de asesor. Comprobar en cada objeto de valor cuál es el nombre del atributo antes de asumirlo.

- [ ] **Step 2: Encontrar todos los puntos a tocar**

```bash
cd backend/src/infrastructure/adapters/output/persistence
rg -n "str\(|fromisoformat|isoformat|json\.|is_active = 1|is_active = 0|1 if .*is_active|bool\(row|bool\(r\[" raw_sql_*.py
```

Hay unas 34 apariciones repartidas en los cinco repositorios. Ninguna es opcional: cualquiera que quede provoca un error de tipo en cuanto se ejerza.

Las comparaciones en SQL también cambian: `WHERE is_active = 1` pasa a `WHERE is_active = TRUE`, y `SET is_active = 0` a `SET is_active = FALSE`. Hay diez en `raw_sql_agent_repository.py` y `raw_sql_tenant_repository.py`.

- [ ] **Step 3: Adaptar los cinco repositorios**

Ir de uno en uno, en este orden: `tenant` (el más pequeño, 5 conversiones), `webhook` (1), `agent` (8), `lead` (10), `rule` (10).

Ejemplo del cambio en `raw_sql_tenant_repository.py`, método `save`:

```python
    def save(self, tenant: Tenant) -> Tenant:
        self.connection.execute(
            """
            INSERT INTO tenants (id, name, slug, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                slug = EXCLUDED.slug,
                is_active = EXCLUDED.is_active
            """,
            (
                tenant.id.value,
                tenant.name,
                tenant.slug,
                tenant.is_active,
                tenant.created_at,
            ),
        )
        return tenant
```

Y su lector:

```python
    @staticmethod
    def _to_tenant(row) -> Tenant:
        return Tenant.create(
            name=row["name"],
            tenant_id=row["id"],
            slug=row["slug"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )
```

El resto sigue el mismo patrón. `Tenant.create` y las demás factorías aceptan ya tanto `UUID` como cadena, así que los lectores no necesitan convertir nada.

- [ ] **Step 4: Ejecutar los tests de integración**

```bash
cd backend
uv run pytest -m integration -q
```

Expected: PASS. Si algún test inserta filas a mano con cadenas ISO o con `0`/`1`, actualízalo: el test estaba acoplado al esquema viejo.

- [ ] **Step 5: Ejecutar la suite completa**

```bash
uv run pytest -q
```

Expected: **188 passed**, el mismo número que antes de empezar. Este cambio no añade ni quita comportamiento; si el número baja, algo se rompió, y si sube, alguien añadió un test que no tocaba.

- [ ] **Step 6: Commit**

```bash
git add backend/src/infrastructure/adapters/output/persistence/ backend/tests/
git commit -m "refactor(persistence): let psycopg map values instead of translating by hand"
```

---

## Task 3: Verificación del circuito y documentación

**Files:**
- Modify: `docs/api/endpoints.md` (sección de persistencia, si menciona los tipos)

**Interfaces:**
- Consumes: todo lo anterior. No produce interfaces nuevas.

- [ ] **Step 1: Arrancar desde volumen vacío**

```bash
docker compose down -v
docker compose up -d --build db backend
docker compose logs backend | tail -30
```

Expected: sin errores de migración, backend `healthy`.

- [ ] **Step 2: Comprobar el circuito funcional con `curl`**

Bootstrap del administrador, creación de una organización con su gestor, alta de un asesor, ingesta de un lead y listado. El objetivo es ejercer los cuatro tipos nuevos de una pasada: `UUID` en los identificadores, `TIMESTAMPTZ` en `created_at`, `NUMERIC` en `budget` y `JSONB` en `custom_attributes`.

```bash
API=http://localhost:8001/api/v1
PW='Str0ngPass!'

curl -s -X POST "$API/agents" -H 'Content-Type: application/json' \
  -d "{\"name\":\"Platform Admin\",\"email\":\"admin@platform.test\",\"team\":\"Platform\",\"password\":\"$PW\",\"role\":\"ADMIN\"}"

ADMIN=$(curl -s -X POST "$API/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "username=admin@platform.test" --data-urlencode "password=$PW" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s -X POST "$API/tenants" -H 'Content-Type: application/json' -H "Authorization: Bearer $ADMIN" \
  -d "{\"name\":\"Acme Corp\",\"manager\":{\"name\":\"Ana\",\"email\":\"ana@acme.test\",\"password\":\"$PW\"}}"

ANA=$(curl -s -X POST "$API/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "username=ana@acme.test" --data-urlencode "password=$PW" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

TENANT=$(curl -s "$API/auth/me" -H "Authorization: Bearer $ANA" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["tenant_id"])')

curl -s -X POST "$API/intake/$TENANT/leads/ingest" -H 'Content-Type: application/json' \
  -d '{"first_name":"Laura","last_name":"Diaz","email":"laura@example.com","company":"Globex","budget":15750.55,"industry":"Tech","custom_attributes":{"origen":"feria","prioridad":3}}'

curl -s "$API/leads" -H "Authorization: Bearer $ANA"
```

Expected: el lead aparece con `budget` de `15750.55` **sin pérdida de precisión** y con `custom_attributes` como objeto, no como cadena escapada.

- [ ] **Step 3: Comprobar en la base que los valores son nativos**

```bash
docker compose exec -T db psql -U postgres -d leads_db -c "
SELECT id, budget, custom_attributes, custom_attributes->>'origen' AS origen, created_at
FROM leads;"
```

Expected: `origen` devuelve `feria`. Que `->>` funcione es la prueba de que la columna es `jsonb` de verdad y no una cadena que lo parece: sobre `TEXT` ese operador ni siquiera existe.

```bash
docker compose exec -T db psql -U postgres -d leads_db -c "
SELECT count(*) FROM agents WHERE is_active;"
```

Expected: cuenta sin necesidad de comparar con `1`. Un booleano se usa como condición directamente.

- [ ] **Step 4: Suite completa dentro del contenedor**

```bash
docker compose --profile test run --rm --build backend-test
```

Expected: **188 passed**. El `--build` no es opcional: sin él, compose reutiliza la imagen en caché y valida código viejo.

- [ ] **Step 5: Actualizar la documentación**

En `docs/api/endpoints.md`, si alguna sección describe los tipos de columna como `TEXT`, corregirla. Si no menciona la persistencia, no inventar una sección: este paso es para no dejar documentación mintiendo, no para añadir documentación.

- [ ] **Step 6: Commit**

```bash
git add docs/
git commit -m "docs(db): describe the schema with its real column types"
```

---

## Criterio de aceptación de F0.6

- [ ] Ninguna columna de identificador, fecha, importe o atributo sigue siendo `TEXT`.
- [ ] `rg "fromisoformat|json.dumps|json.loads|is_active = 1"` no devuelve nada en `adapters/output/persistence/`.
- [ ] La suite sigue en **188 passed**, dentro y fuera de Docker.
- [ ] Guardián de arquitectura en 4/4.
- [ ] Un importe con decimales sobrevive el viaje de ida y vuelta sin perder precisión.
- [ ] `custom_attributes->>'clave'` funciona en SQL.
- [ ] El sistema arranca desde volumen vacío.
- [ ] **Ni el dominio ni la aplicación han cambiado.** `git diff --stat` no debe mostrar ficheros de `src/domain/` ni de `src/application/`.

Ese último punto es el que da sentido a la fase: si cambiar el motor de persistencia obligara a tocar las reglas de negocio, la arquitectura hexagonal sería decorativa.

## Notas para quien ejecute el plan

**Orden.** La 1 antes que la 2, obligatoriamente: la 2 no puede pasar sus tests sin el esquema de la 1. La 3 al final.

**La Task 1 deja los tests de integración en rojo a propósito** y no se arreglan hasta la Task 2. Es el ciclo rojo→verde de un cambio de esquema.

**Criterio de parada.** Si un paso "verificar que falla" produce un fallo distinto del descrito, detenerse y reportar.
