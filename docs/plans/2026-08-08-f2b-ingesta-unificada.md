# F2b — Ingesta unificada: plan de implementación

**Spec:** [F2b — Ingesta unificada](../specs/2026-08-08-f2b-ingesta-unificada-design.md).
**Precede a:** [F2c — Reglas componibles](../specs/2026-08-08-f2c-reglas-componibles-design.md).
**Base:** `repo-status-mvp` en `f1d7ffa`, árbol limpio, F2a cerrada y verificada.

**Trabajo previo ya commiteado** (no forma parte de las tareas de abajo):

| Commit | Qué dejó resuelto |
|---|---|
| `edba1cc` | El harness ya no depende del orden de import: `DATABASE_URL` y `JWT_SECRET` se fijan una vez en `conftest.py`, y el `TRUNCATE` lee las tablas del catálogo en vez de una lista escrita a mano — que es lo que habría dejado contaminación silenciosa al añadir las tres tablas de esta fase |
| `f1d7ffa` | El intérprete local queda fijado a 3.12, la versión que corre la imagen |

**Objetivo en una frase:** que nada de lo que entra se pierda, y que nadie ingeste sin credencial.

**Arquitectura:** tres entidades nuevas —`LeadSource`, `IntakeRecord`, `IntakeError`— y un único
recorrido de ingesta que persiste el payload **antes** de intentar interpretarlo. El formulario y la
carga masiva dejan de tener caminos propios. `LeadStatus.FAILED` desaparece y su papel lo asume
`IntakeRecord.REJECTED`, que sí se persiste y sí se revisa.

**Stack:** FastAPI, psycopg 3 con SQL crudo (marcadores `%s`), PostgreSQL 16, pytest.

---

## Nota operativa: esta fase exige base limpia

La migración `005` añade `leads.source_id` como `NOT NULL` con clave foránea. Sobre una base con
leads de F2a **la migración falla en el arranque**, y debe fallar: un lead sin origen es
exactamente el dato incoherente que la columna existe para impedir.

No es una regresión ni hay backfill que escribir — el spec §9 lo fija: *«No hay datos que
preservar»*, y los datos actuales son de pruebas. Al validar cada tarea:

```bash
docker compose down -v && docker compose up -d      # o ./scripts/verify-e2e.sh --reset
```

---

## Constraints globales

Vinculan a **todas** las tareas. Un incumplimiento es un fallo de la tarea, no un detalle menor.

| # | Constraint |
|---|---|
| C1 | **Código, docstrings, comentarios y mensajes de commit en inglés.** Los documentos de `docs/` van en español |
| C2 | **Guardián de arquitectura 4/4.** `domain/` no importa nada de fuera ni terceros; `application/` no importa `infrastructure/` ni frameworks web. `tests/architecture/test_dependency_rule.py` lo comprueba por AST |
| C3 | **SQL crudo con marcadores `%s`.** Sin ORM, sin f-strings en consultas |
| C4 | **La organización sale del token, nunca de la URL ni del cuerpo** |
| C5 | **404, no 403**, al leer una entidad de otra organización |
| C6 | **Un commit por tarea**, formato `type(scope): description`, sin `Co-authored-by` |
| C7 | Los comentarios explican **por qué**, no qué. Sin verborrea |
| C8 | **No se añade ninguna exigencia de contactabilidad** al hacer el correo opcional. Nada de «al menos una vía de contacto»: reproduciría el problema con otro nombre y dejaría la bandeja de descalificados vacía justo en el caso que la justifica |

### Harness (cambió en F2a — no uses el procedimiento viejo)

```bash
# Suite completa. NO lleva --build: src/, tests/ y migrations/ están montados.
# Reconstruir sólo si cambian pyproject.toml o uv.lock.
docker compose --profile test run --rm backend-test

# Subconjunto
docker compose --profile test run --rm backend-test pytest -q tests/unit

# Unitarios sin variables de entorno (deben pasar fuera de Docker)
cd backend && uv run pytest -m unit -q

# Verificación de negocio (~3 s, no necesita base limpia salvo en esta fase)
./scripts/verify-e2e.sh --reset
```

---

## Mapa de ficheros

Rutas relativas a `backend/` salvo indicación.

### Se crean

| Fichero | Responsabilidad |
|---|---|
| `migrations/005_lead_sources_and_intake.sql` | Las tres tablas nuevas y las dos alteraciones de `leads` |
| `src/domain/value_objects/lead_source_id.py` | Identidad de la fuente |
| `src/domain/value_objects/intake_record_id.py` | Identidad del registro de ingesta |
| `src/domain/entities/lead_source.py` | El origen como entidad del gestor |
| `src/domain/entities/intake_record.py` | El payload persistido y su ciclo, con `IntakeError` |
| `src/application/ports/output/lead_source_repository_port.py` | Puerto de persistencia de fuentes |
| `src/application/ports/output/intake_record_repository_port.py` | Puerto de persistencia de registros |
| `src/application/ports/input/lead_source_use_case_ports.py` | Puertos de entrada del CRUD de fuentes |
| `src/application/ports/input/intake_record_use_case_ports.py` | Puertos de entrada de la bandeja |
| `src/application/use_cases/lead_source_use_cases.py` | CRUD de fuentes |
| `src/application/use_cases/intake_record_use_cases.py` | Bandeja: listar, promover, descartar |
| `src/infrastructure/adapters/output/persistence/raw_sql_lead_source_repository.py` | Repositorio de fuentes |
| `src/infrastructure/adapters/output/persistence/raw_sql_intake_record_repository.py` | Repositorio de registros y sus errores |
| `src/infrastructure/adapters/input/api/source_router.py` | `/api/v1/sources` |
| `tests/unit/domain/test_lead_source.py` | Invariantes de la fuente |
| `tests/unit/domain/test_intake_record.py` | Ciclo del registro de ingesta |
| `tests/unit/application/test_unified_intake_pipeline.py` | El pipeline: nada se pierde |
| `tests/integration/test_lead_source_repo.py` | Persistencia de fuentes |
| `tests/integration/test_intake_record_repo.py` | Persistencia de registros y errores |
| `tests/e2e/test_intake_authentication.py` | Nadie ingesta sin credencial |
| `tests/e2e/test_intake_inbox.py` | La bandeja: rechazo, corrección y promoción |

### Se modifican

| Fichero | Cambio |
|---|---|
| `src/domain/entities/lead.py` | `source_id` obligatorio; `email` opcional |
| `src/domain/value_objects/enums.py` | `LeadSourceKind`, `IntakeRecordStatus`; retirada de `LeadStatus.FAILED` |
| `src/domain/value_objects/__init__.py` | Exportar lo nuevo |
| `src/domain/events/lead_events.py` | `LeadProcessedEvent.email: Optional[str]` |
| `src/application/dtos/commands.py` | `IngestLeadCommand` gana `source_id`, `email` opcional; `LeadProcessedResult` gana `intake_record_id` |
| `src/application/ports/output/unit_of_work_port.py` | `sources` e `intake_records` |
| `src/application/use_cases/ingest_lead_use_case.py` | Pipeline unificado |
| `src/application/use_cases/process_batch_use_case.py` | Recorre el mismo pipeline |
| `src/application/use_cases/tenant_use_cases.py` | Dos fuentes automáticas al crear la organización |
| `src/infrastructure/adapters/output/persistence/raw_sql_lead_repository.py` | `source_id` y correo nulo |
| `src/infrastructure/adapters/output/persistence/postgres_unit_of_work.py` | Instanciar los repositorios nuevos |
| `src/infrastructure/adapters/output/parsers/pandas_file_parser.py` | Celda vacía → `None`; aplicar `field_mapping` |
| `src/infrastructure/adapters/input/api/intake_router.py` | Autenticado; bandeja |
| `src/infrastructure/adapters/input/api/schemas.py` | Esquemas de fuente, registro y correo opcional |
| `src/infrastructure/adapters/input/api/dependencies.py` | Proveedores de los casos de uso nuevos |
| `src/infrastructure/main.py` | Montar `source_router`; prefijo de `intake_router` sin `{tenant_id}` |
| `scripts/verify-e2e.sh` | Ruta y token en `verify_f2a`; `verify_f2b` nueva |
| `docs/specs/2026-08-07-lead-router-mvp-design.md` | §15: F2b cerrada |

---

## Secuencia y agrupación

Seis tareas, **una por subagente**, en orden estricto. Cada una deja la suite en verde y hace un
commit. Agrupadas de modo que cada despacho comparte una sola validación.

| # | Tarea | Por qué va junto |
|---|---|---|
| T1 | Migración 005 + `LeadSource` de punta a punta + `source_id` en el lead + fuentes automáticas | **Atómica por necesidad.** No hay estado intermedio con la suite en verde: la columna es `NOT NULL`, así que la entidad, el repositorio, los 12 puntos de construcción y las fuentes automáticas tienen que entrar a la vez |
| T2 | Correo opcional, transversal | Un solo cambio conceptual que atraviesa cinco capas. Partirlo deja el dominio y la base en desacuerdo |
| T3 | `IntakeRecord` + `IntakeError` de punta a punta | Dominio y persistencia del mismo agregado |
| T4 | Pipeline unificado + retirada de `FAILED` | La retirada sólo es posible cuando el pipeline ya tiene dónde poner lo rechazado |
| T5 | API: cierre de autenticación, CRUD de fuentes, bandeja | Los tres tocan el mismo router y los mismos esquemas |
| T6 | Harness `verify_f2b` + documentación | Cierre de fase |

---

# Tarea 1 — Migración 005, `LeadSource` y el origen del lead

**Ficheros:**
- Crear: `migrations/005_lead_sources_and_intake.sql`, `src/domain/value_objects/lead_source_id.py`,
  `src/domain/entities/lead_source.py`,
  `src/application/ports/output/lead_source_repository_port.py`,
  `src/infrastructure/adapters/output/persistence/raw_sql_lead_source_repository.py`,
  `tests/unit/domain/test_lead_source.py`, `tests/integration/test_lead_source_repo.py`
- Modificar: `src/domain/value_objects/enums.py`, `src/domain/value_objects/__init__.py`,
  `src/domain/entities/lead.py`, `src/application/dtos/commands.py`,
  `src/application/ports/output/unit_of_work_port.py`,
  `src/application/use_cases/ingest_lead_use_case.py`,
  `src/application/use_cases/tenant_use_cases.py`,
  `src/infrastructure/adapters/output/persistence/raw_sql_lead_repository.py`,
  `src/infrastructure/adapters/output/persistence/postgres_unit_of_work.py`,
  `src/infrastructure/adapters/output/parsers/pandas_file_parser.py`,
  `src/infrastructure/adapters/input/api/intake_router.py`
- Tests a actualizar (todos los que construyen un `Lead`): `tests/unit/domain/test_entities.py`,
  `tests/unit/domain/test_lead_state_machine.py`, `tests/unit/domain/test_scoring_rule.py`,
  `tests/unit/domain/test_scoring_engine.py`, `tests/unit/domain/test_assignment_engine.py`,
  `tests/unit/application/test_lead_lifecycle_use_cases.py`,
  `tests/integration/test_raw_sql_lead_repo.py`, `tests/integration/test_lead_lifecycle_persistence.py`

**Produce (lo usan T3–T5):** `LeadSourceId`, `LeadSource`, `LeadSourceKind`,
`LeadSourceRepositoryPort`, `uow.sources`, `Lead.source_id`, `IngestLeadCommand.source_id`.

## Decisiones ya tomadas — no las reabras

1. **`source_id` es obligatorio en el dominio.** Un lead siempre vino de algún sitio: es coherencia
   del dato, no rentabilidad, así que es invariante y no regla de organización (criterio de
   [`docs/product/03`](../product/03-dominio-y-organizacion.md)). Sin él, «¿de dónde vienen mis
   leads?» no tiene respuesta.
2. **Con clave foránea — y de paso se cierra la de `leads.tenant_id`.** El baseline (`001`) creó
   `leads`, `scoring_rules`, `routing_rules`, `agents` y `webhook_configs` con `tenant_id` suelto;
   a partir de `003` sí se usan claves foráneas. Dejar `source_id` con restricción y `tenant_id` sin
   ella sería peor que cualquiera de las dos opciones puras, y **el coste ya está pagado**: esta
   tarea obliga igualmente a que los tests de integración creen una organización real, porque
   `source_id` la exige. Las otras cuatro tablas del baseline quedan como están: cerrarlas no tiene
   nada que ver con esta fase.
3. **`LeadSourceKind.WEBHOOK` y la columna `secret_hash` se crean ahora** aunque F3b las implemente.
   Cuestan una línea cada una y ahorran una migración entera después. El adaptador de webhook **no**
   se escribe en esta fase.
4. **`field_mapping` no es andamiaje:** es el mapeo de columnas que la carga masiva usa desde el
   primer día, así que la maquinaria se amortiza ya.

## Paso 1: la migración

`migrations/005_lead_sources_and_intake.sql` — el DDL completo de la fase, incluidas las tablas que
T3 usará. Una sola migración porque una fase es una unidad de despliegue.

```sql
-- Where a lead came in from. Without it, "where do my leads come from?" has
-- no answer, and F2c has nothing to condition a per-channel routing rule on.
CREATE TABLE IF NOT EXISTS lead_sources (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    -- The file-upload source stores its column mapping here, so the machinery
    -- pays for itself from day one instead of being scaffolding for F3b.
    field_mapping JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- F3b authenticates an external source by signature. The column exists now
    -- so webhooks will not need a migration of their own.
    secret_hash TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    -- Two sources with the same name are indistinguishable to the manager.
    UNIQUE (tenant_id, name)
);

-- Every payload that arrives is persisted before anyone tries to interpret it.
-- What cannot be interpreted stays here instead of vanishing, which is what
-- lets a manager answer "how many leads am I losing?".
CREATE TABLE IF NOT EXISTS intake_records (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES lead_sources (id),
    payload JSONB NOT NULL,
    status TEXT NOT NULL,
    -- Set once the record is promoted. SET NULL, not CASCADE: deleting a lead
    -- must not erase the evidence that it once arrived.
    lead_id UUID REFERENCES leads (id) ON DELETE SET NULL,
    received_at TIMESTAMPTZ NOT NULL,
    processed_at TIMESTAMPTZ
);

-- Per-field detail of why a record could not be interpreted: what field, what
-- arrived, what failed. A single message would not let the manager fix a CSV
-- column mapping.
CREATE TABLE IF NOT EXISTS intake_errors (
    id UUID PRIMARY KEY,
    intake_record_id UUID NOT NULL REFERENCES intake_records (id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    received_value TEXT,
    message TEXT NOT NULL,
    error_code TEXT
);

-- A lead always came in from somewhere.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS source_id UUID NOT NULL REFERENCES lead_sources (id);

-- The baseline left leads.tenant_id without a foreign key. A lead pointing at
-- an organization that does not exist is a row no tenant-filtered query ever
-- returns: invisible to every manager, and impossible to delete through the
-- application. Closed here because this migration already rewrites the same
-- tests the constraint affects.
-- PostgreSQL has no ADD CONSTRAINT IF NOT EXISTS; the migration runner applies
-- each file exactly once, so the guard is unnecessary.
ALTER TABLE leads ADD CONSTRAINT fk_leads_tenant
    FOREIGN KEY (tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

-- Contactability is an organization's rule, not an invariant of the data: a
-- lead with no email must be able to exist and be disqualified by a rule
-- (F2c), not be destroyed on arrival. See docs/product/03.
ALTER TABLE leads ALTER COLUMN email DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_lead_sources_tenant ON lead_sources (tenant_id);
CREATE INDEX IF NOT EXISTS idx_leads_source ON leads (tenant_id, source_id);
-- The inbox lists what needs the manager's attention, newest first.
CREATE INDEX IF NOT EXISTS idx_intake_records_inbox
    ON intake_records (tenant_id, status, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_intake_errors_record ON intake_errors (intake_record_id);
```

`ADD COLUMN ... NOT NULL` sin defecto falla si la tabla tiene filas. Es intencionado: ver la nota
operativa al principio de este plan.

## Paso 2: enums y value object

En `src/domain/value_objects/enums.py`, añade:

```python
class LeadSourceKind(str, Enum):
    """How a lead reaches the system.

    WEBHOOK is declared here and implemented in F3b: the enum value costs one
    line and avoids reopening the type when the adapter lands."""

    MANUAL_FORM = "MANUAL_FORM"
    FILE_UPLOAD = "FILE_UPLOAD"
    WEBHOOK = "WEBHOOK"
```

`src/domain/value_objects/lead_source_id.py` — copia el patrón exacto de
`src/domain/value_objects/lead_id.py`, cambiando el nombre de la clase a `LeadSourceId`. Léelo
primero; no inventes una variante.

Expórtalos en `src/domain/value_objects/__init__.py` junto a los ya existentes.

## Paso 3: la entidad

`src/domain/entities/lead_source.py`:

```python
@dataclass
class LeadSource:
    id: LeadSourceId
    tenant_id: TenantId
    name: str
    kind: LeadSourceKind
    field_mapping: Dict[str, str] = field(default_factory=dict)
    is_active: bool = True
    # Same idiom as Lead (lead.py:38-39), not a bare default: a mutable
    # datetime evaluated at class-definition time would freeze on import.
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID, TenantId],
        name: str,
        kind: Union[str, LeadSourceKind],
        field_mapping: Optional[Dict[str, str]] = None,
        is_active: bool = True,
        source_id: Optional[Union[str, UUID, LeadSourceId]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> "LeadSource":
        ...

    def rename(self, name: str) -> None: ...
    def update_mapping(self, field_mapping: Dict[str, str]) -> None: ...
    def deactivate(self) -> None: ...
```

Invariantes que `create` impone, cada uno con su test:

| Invariante | Excepción |
|---|---|
| El nombre no puede estar vacío ni ser sólo espacios | `DomainException("El origen exige un nombre", error_code="SOURCE_WITHOUT_NAME")` |
| Las claves y valores de `field_mapping` son cadenas no vacías | `DomainException(..., error_code="INVALID_FIELD_MAPPING")` |

`rename` y `update_mapping` revalidan e invocan `_touch()`, igual que `Lead._touch()`
(`lead.py:208`).

**No añadas** validación de que `kind` sea único por organización: eso es una consulta, no un
invariante de la entidad, y el índice `UNIQUE (tenant_id, name)` ya cubre lo que importa.

## Paso 4: puerto y repositorio

`src/application/ports/output/lead_source_repository_port.py` — clase abstracta al estilo de
`lead_repository_port.py`:

```python
class LeadSourceRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, source: LeadSource) -> LeadSource: ...

    @abc.abstractmethod
    def get_by_id_and_tenant(self, source_id: UUID, tenant_id: UUID) -> Optional[LeadSource]: ...

    @abc.abstractmethod
    def get_by_kind(self, tenant_id: UUID, kind: LeadSourceKind) -> Optional[LeadSource]: ...

    @abc.abstractmethod
    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[LeadSource]: ...

    @abc.abstractmethod
    def delete(self, source_id: UUID, tenant_id: UUID) -> bool: ...
```

`get_by_kind` es lo que el pipeline usa para resolver la fuente automática sin que el llamante
tenga que conocer su identificador.

El repositorio en
`src/infrastructure/adapters/output/persistence/raw_sql_lead_source_repository.py` sigue el patrón
de `raw_sql_sales_group_repository.py`: `INSERT ... ON CONFLICT (id) DO UPDATE SET`, marcadores
`%s`, `Jsonb(...)` para `field_mapping`, y un `_row_to_source` que llama a `LeadSource.create`.

Regístralo en el UoW:

```python
# postgres_unit_of_work.py, dentro de __enter__
self.sources = RawSqlLeadSourceRepository(self.connection)
```

```python
# unit_of_work_port.py, junto a los demás atributos de clase
sources: LeadSourceRepositoryPort
```

## Paso 5: el lead lleva su origen

En `src/domain/entities/lead.py`:

- Campo nuevo, **obligatorio, sin valor por defecto**, colocado justo después de `tenant_id`:
  `source_id: LeadSourceId`
- En `create`, parámetro obligatorio `source_id: Union[str, UUID, LeadSourceId]` situado
  inmediatamente después de `tenant_id`, con la conversión habitual:
  `source_id_vo = source_id if isinstance(source_id, LeadSourceId) else LeadSourceId(source_id)`

Propagación, en este orden:

1. `IngestLeadCommand` (`commands.py:13`) gana `source_id: UUID` tras `tenant_id`.
2. `IngestLeadUseCase.execute` lo pasa a `Lead.create` (`ingest_lead_use_case.py:38-48`).
3. `RawSqlLeadRepository.save` añade `source_id` a la lista de columnas, a los `%s`, al
   `ON CONFLICT DO UPDATE SET` y a la tupla de valores como `lead.source_id.value`
   (`raw_sql_lead_repository.py:26-73`).
4. `_row_to_lead` añade `source_id=row["source_id"]` (`raw_sql_lead_repository.py:78`).
5. `PandasFileParser.parse_leads_file` acepta un parámetro `source_id: UUID` y lo pone en cada
   `IngestLeadCommand`. `ProcessBatchUseCase.execute` se lo pasa.
6. `intake_router.ingest_lead` y `batch_upload` resuelven la fuente con
   `uow.sources.get_by_kind(tenant_id, MANUAL_FORM | FILE_UPLOAD)`. **T5 mueve esa resolución al
   caso de uso**; aquí basta con que funcione.

En los 8 ficheros de test listados arriba, añade `source_id=uuid.uuid4()` a cada `Lead.create`. En
los de integración (`test_raw_sql_lead_repo.py`, `test_lead_lifecycle_persistence.py`) **no vale un
UUID inventado**: la clave foránea lo rechaza. Inserta antes una organización y una fuente reales:

```python
tenant_id = uuid.uuid4()
connection.execute(
    "INSERT INTO tenants (id, name, slug, created_at) VALUES (%s, %s, %s, now())",
    (tenant_id, "Acme", f"acme-{tenant_id}"),
)
source = repo_sources.save(
    LeadSource.create(tenant_id=tenant_id, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
)
```

## Paso 6: fuentes automáticas al crear la organización

En `CreateTenantUseCase.execute` (`tenant_use_cases.py:32-55`), dentro del `with self.uow:` que ya
existe y **después** de guardar el tenant:

```python
for name, kind in (("Formulario manual", LeadSourceKind.MANUAL_FORM),
                   ("Carga de fichero", LeadSourceKind.FILE_UPLOAD)):
    self.uow.sources.save(
        LeadSource.create(tenant_id=tenant.id, name=name, kind=kind)
    )
```

Va en la misma transacción por la razón que el docstring de la clase ya explica para el gestor: una
organización que no puede recibir leads no es un estado intermedio útil.

## Paso 7: conftest — no toques nada

`tests/conftest.py` **no necesita ningún cambio**. Su fixture `clean_tables` lee las tablas del
catálogo (`SELECT tablename FROM pg_tables`), así que las tres tablas nuevas entran en el `TRUNCATE`
solas. Si encuentras una tupla `_TABLES` enumerada a mano, estás mirando una versión anterior al
commit `edba1cc`: haz `git pull` antes de seguir.

Las variables `DATABASE_URL` y `JWT_SECRET` también se fijan una sola vez ahí. **No las declares en
ningún fichero de test nuevo**, ni copies un preámbulo `os.environ.setdefault(...)` de otro fichero:
esas copias se eliminaron precisamente porque hacían que un test pasara o fallara según el orden de
import.

## Validación y commit

```bash
docker compose down -v && docker compose up -d
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q
```

Los cuatro tests de `tests/architecture/` deben pasar.

```bash
git add -A
git commit -m "feat(domain): give the lead the source it came in from"
```

---

# Tarea 2 — El correo deja de ser obligatorio

**Ficheros:**
- Modificar: `src/domain/entities/lead.py`, `src/domain/events/lead_events.py`,
  `src/application/dtos/commands.py`,
  `src/infrastructure/adapters/output/persistence/raw_sql_lead_repository.py`,
  `src/infrastructure/adapters/output/parsers/pandas_file_parser.py`,
  `src/infrastructure/adapters/input/api/schemas.py`
- Test: `tests/unit/domain/test_entities.py`, `tests/integration/test_raw_sql_lead_repo.py`,
  `tests/integration/test_pandas_file_parser.py`

**Consume de T1:** `Lead.source_id` ya existe y es obligatorio.

## El razonamiento, para que no lo deshagas a mitad

*«Sin correo no vale la pena»* es una **regla de la organización**, no un invariante: hay quien
contacta por teléfono, por mensajería o por redes profesionales. Escrita como invariante produce el
peor resultado posible — el lead **se destruye** en vez de quedar marcado, y el gestor no puede
contar lo que pierde.

Lo que **no** cambia: si viene un correo, sigue teniendo que tener forma de correo. `EmailAddress`
no se toca.

**C8 es la trampa de esta tarea.** No añadas «al menos una vía de contacto» en sustitución. Un lead
sin ninguna vía tiene que poder existir; F2c escribirá la regla que lo descalifica. Si lo bloqueas
aquí, la bandeja de descalificados queda vacía justo en el caso que la justifica.

## Paso 1: dominio

En `lead.py`:

```python
email: Optional[EmailAddress] = None
```

Ojo con el orden de los campos del `dataclass`: al ganar valor por defecto, `email` tiene que
moverse por debajo del último campo sin defecto. Colócalo junto a `phone` (`lead.py:28`), que ya es
opcional — quedan los dos canales de contacto juntos, que es como se leen.

En `create`, la firma pasa a `email: Optional[Union[str, EmailAddress]] = None` y la conversión a:

```python
if email is None or email == "":
    email_vo = None
elif isinstance(email, EmailAddress):
    email_vo = email
else:
    email_vo = EmailAddress(email)
```

La cadena vacía se trata como ausencia: un CSV con la celda en blanco y un formulario con el campo
sin rellenar significan lo mismo, y distinguirlos produciría un `InvalidEmailException` por un dato
que nadie escribió.

## Paso 2: persistencia

`raw_sql_lead_repository.py:58` — `str(lead.email)` convierte `None` en la cadena `"None"`:

```python
str(lead.email) if lead.email else None,
```

`_row_to_lead` no necesita cambio: `create` ya acepta `None`. Confírmalo leyendo la línea, no lo
supongas.

## Paso 3: evento

`lead_events.py:13` → `email: Optional[str] = None`. Al ser `kw_only=True`, el orden no importa.

En `ingest_lead_use_case.py:96`, la construcción del evento:

```python
email=str(saved_lead.email) if saved_lead.email else None,
```

## Paso 4: API y comando

- `commands.py:17` → `email: Optional[str] = None`. Igual que con el dataclass del lead, vigila el
  orden de los campos sin defecto.
- `schemas.py:17` → `email: Optional[str] = None`, y el validador `validate_email` (`schemas.py:24`)
  devuelve `None` tal cual sin llamar a `_validate_email_format`:

```python
@field_validator("email")
@classmethod
def validate_email(cls, v: Optional[str]) -> Optional[str]:
    if v is None or not v.strip():
        return None
    return _validate_email_format(v)
```

- `LeadResponse.email` (`schemas.py:44`) → `Optional[str]`. Revisa el resto de `schemas.py` por si
  algún otro esquema expone el correo del lead; el del **asesor** no se toca, ahí es la credencial
  de acceso y sigue siendo obligatorio de verdad.

## Paso 5: parser

`pandas_file_parser.py` — hoy `str(row_dict.get("email", "")).strip()` convierte una celda vacía en
`""` y un `NaN` en la cadena `"nan"`. Aplica el mismo tratamiento que ya usa `phone`:

```python
email = str(row_dict["email"]).strip() if "email" in row_dict and pd.notna(row_dict["email"]) else None
if email == "":
    email = None
```

## Tests

| Test | Aserción |
|---|---|
| `test_entities.py` | `Lead.create(..., email=None)` construye y `lead.email is None` |
| `test_entities.py` | `Lead.create(..., email="")` deja `email is None` |
| `test_entities.py` | `Lead.create(..., email="no-es-correo")` sigue elevando `InvalidEmailException` |
| `test_raw_sql_lead_repo.py` | Un lead sin correo se guarda y se relee con `email is None`, no con la cadena `"None"` |
| `test_pandas_file_parser.py` | Una fila con la celda de correo vacía produce un comando con `email is None` |

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
git commit -m "feat(domain): let a lead exist without an email address"
```

---

# Tarea 3 — `IntakeRecord` e `IntakeError`

**Ficheros:**
- Crear: `src/domain/value_objects/intake_record_id.py`,
  `src/domain/entities/intake_record.py`,
  `src/application/ports/output/intake_record_repository_port.py`,
  `src/infrastructure/adapters/output/persistence/raw_sql_intake_record_repository.py`,
  `tests/unit/domain/test_intake_record.py`, `tests/integration/test_intake_record_repo.py`
- Modificar: `src/domain/value_objects/enums.py`, `src/domain/value_objects/__init__.py`,
  `src/application/ports/output/unit_of_work_port.py`,
  `src/infrastructure/adapters/output/persistence/postgres_unit_of_work.py`

**Consume de T1:** las tablas `intake_records` e `intake_errors` ya existen en la migración 005; no
escribas una migración nueva.

**Produce (lo usa T4 y T5):** `IntakeRecord`, `IntakeError`, `IntakeRecordStatus`,
`uow.intake_records`.

## Paso 1: el estado

En `enums.py`:

```python
class IntakeRecordStatus(str, Enum):
    """What happened to a payload after it arrived."""

    PENDING = "PENDING"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    DISCARDED = "DISCARDED"
```

`src/domain/value_objects/intake_record_id.py` — mismo procedimiento que `LeadSourceId` en T1:
copia el patrón exacto de `src/domain/value_objects/lead_id.py` cambiando el nombre de la clase a
`IntakeRecordId`. Léelo primero; no inventes una variante. Expórtalo en
`src/domain/value_objects/__init__.py`.

## Paso 2: `IntakeError`

Value object inmutable, en el mismo fichero que la entidad porque no se usa fuera de ella:

```python
@dataclass(frozen=True)
class IntakeError:
    """Why one field of a payload could not be interpreted.

    Per-field rather than one message per record: a manager fixing a CSV column
    mapping needs to know which column, not that "the row failed"."""

    field: str
    message: str
    received_value: Optional[str] = None
    error_code: Optional[str] = None
```

## Paso 3: la entidad

```python
@dataclass
class IntakeRecord:
    id: IntakeRecordId
    tenant_id: TenantId
    source_id: LeadSourceId
    payload: Dict[str, Any]
    status: IntakeRecordStatus = IntakeRecordStatus.PENDING
    errors: List[IntakeError] = field(default_factory=list)
    lead_id: Optional[LeadId] = None
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None

    @classmethod
    def create(cls, tenant_id, source_id, payload, record_id=None, status=PENDING,
               errors=None, lead_id=None, received_at=None, processed_at=None) -> "IntakeRecord":
        ...

    def promote(self, lead_id: Union[str, UUID, LeadId]) -> None: ...
    def reject(self, errors: List[IntakeError]) -> None: ...
    def discard(self) -> None: ...
```

Transiciones, con la misma disciplina que `Lead` estrenó en F2a (`lead.py:134-189`):

| Método | Desde | Hacia | Rechazo |
|---|---|---|---|
| `promote` | `PENDING`, `REJECTED` | `PROMOTED` | `DomainException(error_code="INVALID_INTAKE_TRANSITION")` |
| `reject` | `PENDING` | `REJECTED` | ídem, y `DomainException(error_code="REJECTION_WITHOUT_ERRORS")` si la lista viene vacía |
| `discard` | `PENDING`, `REJECTED` | `DISCARDED` | `DomainException(error_code="INVALID_INTAKE_TRANSITION")` |

`promote` acepta venir de `REJECTED` a propósito: es el criterio de aceptación 2 del spec —el
gestor corrige lo que falló y lo promueve—. Los tres fijan `processed_at`.

Un registro `PROMOTED` o `DISCARDED` no vuelve atrás por ningún camino: escribe un test por cada
transición prohibida.

## Paso 4: puerto y repositorio

```python
class IntakeRecordRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, record: IntakeRecord) -> IntakeRecord: ...

    @abc.abstractmethod
    def get_by_id_and_tenant(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]: ...

    @abc.abstractmethod
    def list_by_tenant(
        self, tenant_id: UUID, status: Optional[IntakeRecordStatus] = None,
        limit: int = 100, offset: int = 0,
    ) -> List[IntakeRecord]: ...

    @abc.abstractmethod
    def count_by_tenant(self, tenant_id: UUID, status: Optional[IntakeRecordStatus] = None) -> int: ...
```

`save` escribe las dos tablas: `INSERT ... ON CONFLICT (id) DO UPDATE` sobre `intake_records`, y
para los errores **borra e inserta** —`DELETE FROM intake_errors WHERE intake_record_id = %s`
seguido de los `INSERT`—. Es lo correcto aquí: los errores son una lista de valores que pertenece
al registro, no entidades con identidad propia, así que reconciliar fila a fila sería trabajo sin
beneficio.

La lectura recupera los errores con una consulta por registro. **No optimices a un `JOIN`**: la
bandeja pagina de 100 en 100 y el gestor la abre unas pocas veces al día.

Regístralo en el UoW como `self.intake_records` y en el puerto como
`intake_records: IntakeRecordRepositoryPort`.

## Tests

Unitarios: una transición válida y una prohibida por cada método, más el rechazo sin errores.
Integración: guardar un registro con dos errores, releerlo y comprobar que vuelven ambos; volver a
guardar con un solo error y comprobar que quedan uno, no tres.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
git commit -m "feat(domain): persist every payload that arrives, valid or not"
```

---

# Tarea 4 — El pipeline unificado y la retirada de `FAILED`

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
_FIELD_BY_ERROR_CODE = {
    "INVALID_EMAIL": "email",
    "INVALID_MONEY": "budget",
}
# default: "_record" — the payload as a whole, when nothing narrower is known
```

Comprueba los códigos reales en `src/domain/exceptions.py` antes de escribir el diccionario; si
alguno no existe con ese nombre, usa el que haya y no inventes uno nuevo.

## Paso 3: la carga masiva recorre lo mismo

`ProcessBatchUseCase.execute` (`process_batch_use_case.py:23-31`) ya llama al mismo caso de uso por
fila, así que hereda el pipeline sin cambios de fondo. Lo único que toca: `FailedRow.email` es
`str` y ahora puede ser `None` (`commands.py:131`) → `Optional[str]`. Añade
`intake_record_id: str = ""` a `FailedRow` y rellénalo desde `res.intake_record_id`, que es lo que
convierte una fila fallida en algo recuperable.

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

# Tarea 5 — API: credencial, fuentes y bandeja

**Ficheros:**
- Crear: `src/application/ports/input/lead_source_use_case_ports.py`,
  `src/application/ports/input/intake_record_use_case_ports.py`,
  `src/application/use_cases/lead_source_use_cases.py`,
  `src/application/use_cases/intake_record_use_cases.py`,
  `src/infrastructure/adapters/input/api/source_router.py`,
  `tests/e2e/test_intake_authentication.py`, `tests/e2e/test_intake_inbox.py`
- Modificar: `src/infrastructure/adapters/input/api/intake_router.py`,
  `src/infrastructure/adapters/input/api/schemas.py`,
  `src/infrastructure/adapters/input/api/dependencies.py`, `src/infrastructure/main.py`
- Tests a actualizar: `tests/e2e/test_lead_endpoints.py`, `tests/e2e/test_system_e2e.py`,
  `tests/e2e/test_assignment_flow_e2e.py`, `tests/e2e/test_lead_lifecycle_api.py`

## Paso 1: la organización sale del token

En `main.py:77`:

```python
app.include_router(intake_router, prefix="/api/v1/intake", tags=["Intake"])
```

El `{tenant_id}` desaparece del prefijo. Las rutas quedan así:

| Antes | Ahora | Acceso |
|---|---|---|
| `POST /api/v1/intake/{tenant_id}/leads/ingest` | `POST /api/v1/intake/leads/ingest` | Gestor |
| `POST /api/v1/intake/{tenant_id}/leads/batch-upload` | `POST /api/v1/intake/leads/batch-upload` | Gestor |
| — | `GET /api/v1/intake/records` | Gestor |
| — | `POST /api/v1/intake/records/{id}/promote` | Gestor |
| — | `POST /api/v1/intake/records/{id}/discard` | Gestor |
| — | `GET·POST /api/v1/sources`, `PATCH·DELETE /api/v1/sources/{id}` | Gestor |

En `intake_router.py`, ambos endpoints cambian la firma: fuera el parámetro `tenant_id: UUID`,
dentro `context: RequestContext = Depends(require_organization_manager)`, y el identificador de la
organización sale de `context.tenant_id`. Borra los dos comentarios
`# Unauthenticated by design until F2...` (`intake_router.py:21-22` y `68-69`): esta tarea es
justamente lo que anunciaban.

La fuente se resuelve **dentro del caso de uso**, no en el router (C4 y separación de capas):
`IngestLeadUseCase` recibe el `kind` y hace `uow.sources.get_by_kind(tenant_id, kind)`. Si no
encuentra fuente activa, `DomainException(error_code="SOURCE_NOT_FOUND")`.

## Paso 2: CRUD de fuentes

Casos de uso en `lead_source_use_cases.py`, uno por operación, con el patrón exacto de
`sales_group_use_cases.py`: `Create`, `Get` (lista paginada), `Update`, `Delete`. Todos reciben el
`RequestContext` y filtran por `context.tenant_id`.

**C5 aplica:** leer, modificar o borrar una fuente de otra organización devuelve **404**, no 403.
Se consigue con `get_by_id_and_tenant`, que no encuentra nada y por tanto no confirma que exista.

`DELETE` sobre una fuente con leads asociados debe fallar con
`DomainException(error_code="SOURCE_IN_USE")` en vez de dejar la clave foránea reventar con un error
de base de datos. Una consulta de recuento antes de borrar basta.

Esquemas en `schemas.py`, al estilo de los de grupo: `LeadSourceCreate`, `LeadSourceUpdate`,
`LeadSourceResponse` (con `id`, `name`, `kind`, `field_mapping`, `is_active`, `created_at`).
`secret_hash` **no se expone nunca** en ninguna respuesta.

Router nuevo `source_router.py` y su montaje en `main.py`:

```python
app.include_router(source_router, prefix="/api/v1/sources", tags=["Sources"])
```

Proveedores en `dependencies.py` siguiendo el patrón de `get_create_sales_group_use_case`
(`dependencies.py:122`). Recuerda: `container.py` **no** construye casos de uso; todos viven aquí.

## Paso 3: la bandeja

`intake_record_use_cases.py`:

- `GetIntakeRecordsUseCase` — lista paginada con filtro opcional por estado. Responde con el payload
  y los errores de cada registro: sin eso el gestor no sabe qué corregir.
- `PromoteIntakeRecordUseCase` — recibe el registro y un payload corregido, reintenta la
  interpretación con el pipeline de T4 y, si sale bien, `record.promote(lead.id)`. Si vuelve a
  fallar, `record.reject(...)` con los errores nuevos y la respuesta lo dice.
- `DiscardIntakeRecordUseCase` — `record.discard()`.

Esquemas: `IntakeRecordResponse` (`id`, `source_id`, `status`, `payload`, `errors`, `received_at`,
`processed_at`, `lead_id`), `IntakeErrorResponse` (`field`, `message`, `received_value`,
`error_code`), `IntakeRecordsPageResponse` (`items`, `total`).

## Paso 4: los e2e existentes

Los cuatro ficheros de `tests/e2e/` que ingestan usan la ruta vieja y sin token. Actualízalos: ruta
nueva y cabecera `Authorization: Bearer` del gestor. **No cambies lo que afirman** — sólo cómo
llaman.

## Tests nuevos

`test_intake_authentication.py`:

| Caso | Esperado |
|---|---|
| `POST /api/v1/intake/leads/ingest` sin cabecera | 401 |
| Con token de asesor (rol `AGENT`) | 403 |
| Con token de gestor | 201, y el lead queda en **su** organización |
| El cuerpo trae un `tenant_id` de otra organización | Se ignora; el lead cae en la del token |

`test_intake_inbox.py` recorre el criterio de aceptación 2 completo: ingesta con correo mal formado
→ 400 con `intake_record_id` → el registro aparece en `GET /records?status=REJECTED` con el detalle
por campo → `POST /records/{id}/promote` con el correo corregido → 200, el registro queda
`PROMOTED` y el lead existe.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
git commit -m "feat(api): close the intake behind a credential and open the manager's inbox"
```

---

# Tarea 6 — Harness y documentación

**Ficheros:** `scripts/verify-e2e.sh`, `docs/specs/2026-08-07-lead-router-mvp-design.md`,
`docs/specs/2026-08-08-f2b-ingesta-unificada-design.md`, `docs/api/` si documenta las rutas de
ingesta.

## Paso 1: arreglar `verify_f2a`

`scripts/verify-e2e.sh:140` llama a `$API/intake/$TENANT_A/leads/ingest` sin token. Cambia **sólo la
ruta y la cabecera**, no las comprobaciones:

```bash
r=$(req -X POST "$API/intake/leads/ingest" -H 'Content-Type: application/json' \
      -H "Authorization: Bearer $TOKEN_MANAGER_A" -d '...')
```

## Paso 2: `verify_f2b`

Rellena la función que ya está esbozada en `scripts/verify-e2e.sh:191`, con el estilo de
`verify_f2a` —helpers `req`, `code`, `body`, `f`, `check`, `section`—. Añade la llamada en `main`
después de `verify_f2a`. **No reescribas nada de lo que ya hay.**

| # | Comprobación |
|---|---|
| 1 | Ingesta sin token → 401 |
| 2 | Ingesta con token de asesor → 403 |
| 3 | La organización recién creada ya tiene sus dos fuentes en `GET /sources` |
| 4 | Lead **sin correo** → 201, y `GET /leads/{id}` lo devuelve con `email: null` |
| 5 | Correo con formato inválido → 400 con `intake_record_id` no vacío |
| 6 | Ese registro aparece en `GET /intake/records?status=REJECTED` con el error de campo `email` |
| 7 | Promoverlo con el correo corregido → 200, y el lead existe |
| 8 | Carga masiva de un CSV con una fila buena y una mala → un `PROMOTED` y un `REJECTED` |
| 9 | Fuente de otra organización → **404** |
| 10 | El lead ingerido lleva el `source_id` de la fuente `MANUAL_FORM` |

## Paso 3: documentación

- `docs/specs/2026-08-07-lead-router-mvp-design.md` §15: F2b pasa a ✅ con la fecha.
- El spec de F2b: encabezado `**Estado:** propuesto` → `implementado`.
- Si `docs/api/` documenta `/intake/{tenant_id}/...`, actualiza las rutas y añade las nuevas.

**No toques `docs/product/`.** Esa documentación es de negocio y ya describe el modelo objetivo;
F2b lo implementa, no lo cambia.

## Validación de cierre

```bash
docker compose down -v && docker compose up -d
docker compose --profile test run --rm backend-test     # suite completa, sin banderas
cd backend && uv run pytest -m unit -q                  # sin variables de entorno
./scripts/verify-e2e.sh --reset                         # F2a + F2b en verde
git commit -m "test: cover the unified intake in the business harness"
```

---

## Criterio de aceptación de la fase

Del spec §10, con dónde se comprueba cada uno:

| # | Criterio | Dónde |
|---|---|---|
| 1 | Un payload sin correo genera un lead que existe y es visible | `verify_f2b` 4 |
| 2 | Un payload ininterpretable queda en la bandeja con el detalle, y el gestor lo corrige y lo promueve | `verify_f2b` 5-7, `test_intake_inbox.py` |
| 3 | Una petición de ingesta sin credencial es rechazada | `verify_f2b` 1-2, `test_intake_authentication.py` |
| 4 | Formulario y carga masiva recorren el mismo pipeline | `verify_f2b` 8, `test_unified_intake_pipeline.py` |
| 5 | El gestor responde «¿de dónde vienen mis leads?» | `verify_f2b` 3 y 10 |
| 6 | Suite en verde sin banderas, guardián 4/4, `pytest -m unit` sin variables de entorno | Validación de cierre |

## Lo que esta fase NO hace

Escribirlo evita que un subagente lo añada por iniciativa propia:

- **Reglas de descalificación** que aprovechen el correo opcional → F2c
- **Deduplicación por identidad** (el mismo DNI llegando dos veces) → sin fase asignada
- **Adaptador de webhook entrante** → F3b. Aquí sólo se crean el valor `WEBHOOK` del enum y la
  columna `secret_hash`
- **Umbral de calificación configurable** → F2c
- **Frontend** → F4
