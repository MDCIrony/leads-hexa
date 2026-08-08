# Tarea 1 — Migración 005, `LeadSource` y el origen del lead

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

**Estado: ✅ cerrada en `b5e2923`.** Se conserva como registro de lo que se pidió.

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
   [`docs/product/03`](../../product/03-dominio-y-organizacion.md)). Sin él, «¿de dónde vienen mis
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
-- PostgreSQL has no ADD CONSTRAINT IF NOT EXISTS, and the guard is NOT
-- optional: test_migration_runner.py drops schema_migrations on purpose while
-- leaving the tables in place, which replays every file. Without this check the
-- replay dies with DuplicateObject.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_leads_tenant'
    ) THEN
        ALTER TABLE leads ADD CONSTRAINT fk_leads_tenant
            FOREIGN KEY (tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;
    END IF;
END $$;

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

