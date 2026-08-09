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
