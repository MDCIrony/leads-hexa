# ADR-0011 · Una gramática de condiciones

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · Dominio |

## Contexto

La condición de una regla —«este campo, comparado así, con este valor»— vivía **dentro** de la
regla de puntuación, acoplada a ella. Cuando el reparto necesitó condicionar por atributo del lead y
la descalificación necesitó su propia etapa, la opción más rápida habría sido repetir esa lógica de
comparación en cada sitio nuevo: tres implementaciones del mismo concepto, divergiendo cada vez que
alguien corrigiera una en un solo lugar.

## Decisión

Se extrae `Criterion` como objeto de valor compartido:

```python
Criterion(field: str, operator: Operator, value: Any)
    .matches(lead) -> bool
```

Las tres etapas del recorrido de un lead —viabilidad, puntuación y asignación— lo consumen. El
gestor aprende a escribir una condición una sola vez y la reutiliza en las tres, y la interfaz puede
usar el mismo componente en los tres formularios.

`Criterion` valida sus propios datos al construirse contra una **lista blanca de campos
evaluables** (nombre, correo, presupuesto, puntuación... y cualquier atributo personalizado). No es
una limitación de negocio sino una frontera de seguridad: sin ella, una regla podría condicionar
sobre el identificador de organización o cualquier otro dato de sistema, convirtiéndolo en un
criterio comercial que el gestor no debería poder tocar.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Duplicar la lógica de comparación en cada etapa que la necesite | Tres implementaciones del mismo concepto que divergen con el tiempo; el punto entero de extraerlo es que sea **un** cambio y no tres parches |
| Dejar el campo evaluable como reflexión libre sobre cualquier atributo del lead | Abre la puerta a que una regla condicione sobre datos internos del sistema en vez de datos de negocio |
| Un lenguaje de expresiones más general (un motor de reglas configurable) | Resuelve un problema mayor del que hay: ninguna organización necesita más que comparar un campo contra un valor con un operador fijo, y una gramática más rica es coste sin comprador en este alcance |

## Consecuencias

**Fácil:** un operador nuevo, o un campo evaluable nuevo, se añade en un solo sitio y las tres
etapas lo heredan automáticamente. Las reglas de las tres etapas son comparables entre sí en la
interfaz porque comparten forma.

**Difícil:** el gestor está limitado a la lista blanca de campos, más los atributos personalizados
que la fuente aporte libremente. Ampliar qué se puede evaluar exige tocar código —añadir un campo a
la lista blanca—, no es autoservicio para el gestor.

## Ver también

- [ADR-0012 · Y dentro, O entre](0012-y-dentro-o-entre.md)
- [ADR-0013 · Condiciones en JSONB](0013-condiciones-en-jsonb.md)
- [Reglas](../modulos/reglas.md)
