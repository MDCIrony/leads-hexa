# ADR-0006 · Migraciones idempotentes

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · Persistencia |

## Contexto

Sin ORM ([ADR-0002](0002-sql-crudo-sin-orm.md)), las migraciones son ficheros SQL planos aplicados
por un runner propio. La suite de integración vacía la tabla `schema_migrations` antes de reejecutar
las migraciones sobre un esquema que ya las tiene aplicadas, para comprobar que el sistema converge
igual desde cualquier punto de partida. Eso obliga a que cada sentencia de cada fichero tolere
ejecutarse dos veces.

## Decisión

Toda migración es idempotente de principio a fin. `CREATE TABLE` y `ADD COLUMN` llevan
`IF NOT EXISTS`. Dos operaciones que PostgreSQL no protege de forma nativa llevan una guarda manual.

**`ADD CONSTRAINT` no admite `IF NOT EXISTS`.** Se protege comprobando antes en `pg_constraint`:

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

**Un `DROP COLUMN` con un `UPDATE` que migra sus datos antes de soltarla.** Proteger sólo el `DROP`
no basta: en la segunda ejecución la columna ya no existe, y el `UPDATE` que la nombra fallaría. Se
protege comprobando la existencia de la columna en `information_schema.columns` antes de tocar los
datos, para que la segunda ejecución se salte el `UPDATE` en vez de romperse.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Confiar sólo en `schema_migrations` y no reejecutar nunca un fichero aplicado | Oculta una sentencia no idempotente hasta que alguien la reejecuta de verdad en un entorno real; la suite la reejecuta a propósito para sacarlo a la luz antes |
| Una herramienta con migraciones idempotentes nativas (Alembic) | La misma razón que en [ADR-0002](0002-sql-crudo-sin-orm.md): arrastra SQLAlchemy |

## Consecuencias

**Fácil:** la suite valida las migraciones desde un volumen vacío o parcialmente aplicado sin ningún
caso especial, y se puede reejecutar el conjunto completo en local sin borrar la base antes.

**Difícil:** quien escribe una migración tiene que razonar «¿y si esto ya se ejecutó?» sentencia por
sentencia. Los dos patrones de guarda de arriba no son algo que salga por costumbre, y olvidar uno
sólo se nota cuando la suite reejecuta el fichero, no al leerlo la primera vez.

## Ver también

- [ADR-0002 · SQL crudo sin ORM](0002-sql-crudo-sin-orm.md)
- [ADR-0007 · Tipos nativos de SQL](0007-tipos-nativos-de-sql.md)
- [Modelo de datos](../arquitectura/modelo-de-datos.md)
