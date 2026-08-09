# ADR-0002 · SQL crudo sin ORM

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-07 |
| **Ámbito** | Backend · Persistencia |

## Contexto

El proyecto reescribe por completo su esquema y sus repositorios como parte del rediseño. Con la
pizarra en blanco, adoptar un ORM era una opción real y no un cambio de última hora.

## Decisión

Se conserva SQL crudo sobre PostgreSQL con `psycopg` 3, sentencias parametrizadas con marcadores
`%s` —nunca `f-strings` ni concatenación dentro de una consulta—. Las migraciones son ficheros SQL
numerados en `backend/migrations/`, aplicados al arrancar por un runner propio de pocas líneas que
registra lo ya ejecutado en una tabla `schema_migrations`.

La prohibición de ORM es una restricción autoimpuesta, y deliberadamente didáctica: obliga a que
cada puerto de persistencia oculte de verdad el detalle del almacenamiento, en vez de dejar pasar
un objeto de sesión o un modelo de ORM hasta el dominio.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Un ORM (SQLAlchemy u otro) | Arrastra una abstracción propia que tiende a filtrarse por el puerto —un repositorio construido sobre una sesión de ORM deja de ser un contrato limpio— y diluye el ejercicio de que el puerto esconda el SQL de verdad |
| Alembic para las migraciones | Depende de SQLAlchemy aunque no se use su capa de mapeo objeto-relacional, así que reintroduce por la puerta de atrás justo lo que se decidió no tener |

## Consecuencias

**Fácil:** control total sobre el SQL generado y sus índices, sin capa de traducción intermedia que
depurar. Una migración es un fichero `.sql` que se lee sin conocer ninguna API propia de un ORM.

**Difícil:** no hay compilador que valide una consulta escrita a mano —un error de sintaxis o un
marcador de menos sólo aparece al ejecutarla—, así que la red de seguridad son los tests de
integración por repositorio, no un chequeo estático. Cada consulta nueva es código explícito que
escribir y mantener, sin generación automática.

## Ver también

- [Modelo de datos](../arquitectura/modelo-de-datos.md)
- [ADR-0006 · Migraciones idempotentes](0006-migraciones-idempotentes.md)
- [ADR-0007 · Tipos nativos de SQL](0007-tipos-nativos-de-sql.md)
