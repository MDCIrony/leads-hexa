# ADR-0013 · Condiciones en JSONB

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · Persistencia |

## Contexto

Al extraer la condición de una regla como pieza compartida, había que decidir cómo persistir la
lista de condiciones de una regla. La opción convencional en un esquema relacional sería una tabla
propia de condiciones, con una fila por condición y una clave foránea a la regla.

## Decisión

Las condiciones se guardan en una sola columna `JSONB` (`conditions`) en la propia tabla de la
regla, no en una tabla aparte con join. Sigue el mismo precedente que ya usaban otras columnas de
valor variable de las reglas antes de esta decisión, en vez de abrir uno nuevo.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Una tabla `conditions` con fila por condición y clave foránea a la regla | Una condición se lee siempre entera, junto a su regla, y nunca se consulta por separado —no existe ningún caso de uso del tipo «qué reglas condicionan sobre este campo»—. Una tabla por join añade un esquema, un join y un orden de carga que nadie necesita |
| Serializar las condiciones como texto (`TEXT` con JSON codificado) | Pierde exactamente lo que `JSONB` da gratis: poder inspeccionar o indexar por clave si algún día hiciera falta, sin tener que parsear una cadena a mano |

## Consecuencias

**Fácil:** leer o escribir una regla completa es una sola fila, sin joins ni ordenar fragmentos para
reconstruir la lista de condiciones en el orden correcto. Añadir un campo nuevo a una condición no
exige una migración de esquema relacional, sólo un valor más dentro del JSON.

**Difícil:** no hay forma barata de preguntarle a la base de datos «qué reglas usan el campo
presupuesto» sin recorrer el JSON de cada fila; si algún día apareciera ese caso de uso, una tabla
propia sería la migración natural.

## Ver también

- [ADR-0007 · Tipos nativos de SQL](0007-tipos-nativos-de-sql.md)
- [ADR-0011 · Una gramática de condiciones](0011-gramatica-de-condiciones.md)
- [Modelo de datos](../arquitectura/modelo-de-datos.md)
