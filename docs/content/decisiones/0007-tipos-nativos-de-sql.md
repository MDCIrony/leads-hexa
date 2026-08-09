# ADR-0007 · Tipos nativos de SQL

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-07 |
| **Ámbito** | Backend · Persistencia |

## Contexto

El esquema de partida guardaba identificadores como `TEXT`, fechas como `TEXT` con formato ISO,
importes como `DOUBLE PRECISION`, booleanos como `INTEGER` con `1`/`0`, y atributos o payloads como
`TEXT` con JSON serializado a mano. Con `DOUBLE PRECISION` para dinero, un presupuesto pierde
precisión en el viaje de ida y vuelta entre la aplicación y la base de datos: es coma flotante
binaria representando una cantidad decimal.

## Decisión

Cada columna usa el tipo nativo de PostgreSQL que corresponde a su naturaleza: `UUID` para
identificadores, `TIMESTAMPTZ` para fechas, `NUMERIC(14,2)` para importes —el dominio ya usa
`Decimal`—, `BOOLEAN` para indicadores, y `JSONB` para atributos libres y payloads, que además
permite consultar por atributo en vez de tratarlos como texto opaco.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Mantener `TEXT` / `DOUBLE PRECISION` / `INTEGER` como en el esquema de partida | Cambiar el esquema por completo ya era parte del rediseño; conservar tipos débiles habría heredado sus defectos sin necesidad |
| `FLOAT` / `DOUBLE PRECISION` para importes, con redondeo en la aplicación | El redondeo en la capa de aplicación es una corrección que hay que acordarse de aplicar siempre; `NUMERIC` hace la representación exacta desde la columna, sin depender de que nadie lo recuerde |

## Consecuencias

**Fácil:** un presupuesto no pierde precisión entre el dominio y la base de datos. Los atributos
libres de un lead se pueden indexar y consultar por clave sin parsear texto. Las comparaciones de
fecha usan el tipo de fecha del motor, con zona horaria, en vez de comparar cadenas.

**Difícil:** el tipo nativo hay que elegirlo bien desde la primera migración de cada tabla; migrar
una columna de `TEXT` a `UUID` o de `INTEGER` a `BOOLEAN` después exige una migración de conversión
explícita, no un cambio trivial.

## Ver también

- [ADR-0002 · SQL crudo sin ORM](0002-sql-crudo-sin-orm.md)
- [Modelo de datos](../arquitectura/modelo-de-datos.md)
