# Convenciones

Cómo se escribe código en este repositorio. Las reglas de esta página no son preferencia de
estilo: la suite las hace cumplir.

## Las tres capas y qué puede importar cada una

| Capa | Ruta | Puede importar | No puede importar |
|---|---|---|---|
| Dominio | `backend/src/domain` | La biblioteca estándar de Python | `application`, `infrastructure`, cualquier framework o librería de terceros |
| Aplicación | `backend/src/application` | `domain` | `infrastructure`, FastAPI o cualquier otro framework web |
| Infraestructura | `backend/src/infrastructure` | `domain`, `application` | — es la única capa que conoce el mundo exterior |

Cuatro tests analizan esto por AST en cada corrida de la suite completa; ver
[Validación](validacion.md). El razonamiento completo está en
[ADR-0001](../decisiones/0001-arquitectura-hexagonal.md).

## Estructura y tamaño del código

El árbol de ficheros tiene que dejar ver la arquitectura hexagonal sin abrir ninguno. Cuatro
límites lo sostienen:

| Regla | Límite |
|---|---|
| Líneas por fichero `.py` fuente | 150, contando líneas en blanco y comentarios. Los tests no tienen límite de líneas |
| Ficheros `.py` por carpeta | 12, sin contar `__init__.py` ni las subcarpetas. Vale para fuentes **y para tests** |
| Anidamiento | `servicio → capa → contexto o responsabilidad`; los tests siguen el mismo árbol |
| Tests de dominio | `tests/unit/domain/**` sólo importa el dominio, la stdlib, `pytest` y sus propios helpers; un import relativo que sale de esa carpeta también falla |

Se agrupa por concepto en subcarpetas: ni una carpeta con decenas de ficheros de conceptos mezclados,
ni una carpeta por fichero salvo que el concepto lo pida. Al partir un módulo en un paquete, su
`__init__.py` reexporta los nombres públicos, para que nadie cambie sus imports.

Árbol modelo de un servicio:

```text
<servicio>/
├── src/
│   ├── domain/
│   │   └── <contexto>/                 # entidades, value objects, eventos y políticas de un concepto
│   ├── application/
│   │   ├── ports/{input,output}/<contexto>/
│   │   └── use_cases/<contexto>/
│   └── infrastructure/
│       ├── adapters/input/api/<contexto>/
│       ├── adapters/input/consumers/   # consumidores Kafka, uno por grupo, y su tabla de grupos
│       ├── adapters/output/persistence/<contexto>/
│       ├── main.py                     # proceso api
│       └── worker/                     # proceso worker: producers, relays, topics, lanes, main, __main__
└── tests/
    ├── architecture/                   # guardián de capas, de estructura y su lista base
    └── unit/{domain,application,infrastructure}/<contexto>/
```

Un ejemplo que ya cumple es `libs/chassis/src/chassis/`:

```text
chassis/
├── auth/         claims.py  jwks.py  service_tokens.py  signing.py  verifier.py
├── consumer/     envelope.py  kafka.py  lane.py  loop.py  topics.py
├── outbox/       envelope.py  kafka.py  relay.py  row.py
├── persistence/  database.py  migrations.py
├── testing/      cli.py  contracts.py  isolation.py  layers.py  structure.py   # los guardianes de esta sección
├── kafka_config.py
├── rabbit.py
└── web.py
```

**Cómo se comprueba.** Desde la raíz, para todo el repositorio y sin Docker:

```bash
./scripts/verify-structure.sh
```

El script recorre cada raíz Python declarada —`backend/src`, `backend/tests`, `libs/chassis/src`,
`libs/chassis/tests`, `services/notifications/src`, `services/notifications/tests`,
`services/identity/src`, `services/identity/tests`, `test-consumer/`, `demo/` y `tools/`— y aplica su lista base a las heredadas; en las de tests sólo mide carpetas. Los
servicios extraídos no tienen lista base. Además, `chassis.testing` ofrece `assert_structure` (con
`max_lines=None` para los tests), `assert_domain_tests_isolated` y, para el guardián de capas,
`layer_violations` y `stdlib_only_violations`, y cada servicio los llama desde
`tests/architecture/test_structure.py`, así que la suite tampoco deja pasar un incumplimiento.
`libs/chassis` se valida a sí mismo sin excepciones. Una raíz Python nueva se añade al script.

**Lo heredado.** Lo que ya incumplía al llegar la regla está en tres listas base, con lo que medía
cada fichero y cada carpeta:

| Lista | Raíz |
|---|---|
| `backend/tests/architecture/structure_baseline.py` | `backend/src` |
| `backend/tests/architecture/tests_structure_baseline.py` | `backend/tests`, sólo carpetas |
| `scripts/structure_baseline.py` | `test-consumer/` y `demo/` |

Las listas sólo encogen: fallan si una entrada crece, si queda por encima de lo que mide el árbol y si
ya cumple el límite. Quien adelgaza algo heredado actualiza su lista en el mismo commit; los valores
se imprimen con:

```bash
cd libs/chassis && uv run python -m chassis.testing measure ../../backend/src
cd libs/chassis && uv run python -m chassis.testing measure ../../backend/tests --no-line-limit
```

El código nuevo cumple sin entrar en la lista. El porqué y las alternativas están en
[ADR-0037](../decisiones/0037-estructura-y-tamano-del-codigo.md).

## SQL crudo, sin ORM

Toda consulta usa marcadores `%s` de psycopg — nunca f-strings ni `.format()` sobre el texto SQL,
que abrirían la puerta a una inyección. Ejemplo real, de
`raw_sql_lead_repository.py`:

```python
cursor = self.connection.execute(
    "SELECT * FROM leads WHERE id = %s AND tenant_id = %s", (lead_id, tenant_id)
)
```

El porqué de prescindir de un ORM está en [ADR-0002](../decisiones/0002-sql-crudo-sin-orm.md).

## Migraciones idempotentes

La suite reejecuta las migraciones a propósito, contra un esquema que puede ya tenerlas aplicadas,
así que cada fichero en `backend/migrations/` debe poder correr dos veces sin fallar.

`CREATE TABLE` y `ALTER TABLE … ADD COLUMN` aceptan `IF NOT EXISTS` de forma nativa. `ADD
CONSTRAINT` no: PostgreSQL no tiene esa sintaxis, y la guarda se escribe a mano contra el catálogo
`pg_constraint`. Ejemplo real, de `backend/migrations/005_lead_sources_and_intake.sql`:

```sql
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_leads_tenant'
    ) THEN
        ALTER TABLE leads ADD CONSTRAINT fk_leads_tenant
            FOREIGN KEY (tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;
    END IF;
END $$;
```

Ver [ADR-0006](../decisiones/0006-migraciones-idempotentes.md).

## Idioma

- Código, comentarios, nombres de variables, funciones, clases y mensajes de commit: **inglés**.
- Documentación —esto que estás leyendo—: **español**.

## Comentarios

Explican el porqué, nunca el qué. Un comentario que narra la línea siguiente sobra: si el código ya
lo dice con claridad, el comentario no aporta nada y se retira en revisión. Aparece sólo cuando hay
una decisión detrás que el código por sí solo no explica.

## Mensajes de commit

Formato `type(scope): description`, sin `Co-authored-by`.

| Tipo | Uso |
|---|---|
| `feat` | Funcionalidad nueva |
| `fix` | Corrección de un defecto |
| `refactor` | Cambio de código sin alterar comportamiento |
| `docs` | Documentación |
| `chore` | Cambios que no son de código |

El cuerpo del commit se añade sólo si aporta valor: motivación en una o dos líneas, nunca una
narración del estado previo. Si el asunto ya se explica solo, se omite el cuerpo. Si la rama está
ligada a una incidencia, se referencia en el pie con `Refs #N` o `Closes #N` si la cierra.

Ver [Cómo contribuir](contribuir.md) para el resto del flujo.
