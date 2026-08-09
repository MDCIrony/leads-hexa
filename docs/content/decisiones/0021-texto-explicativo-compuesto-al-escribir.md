# ADR-0021 · El texto explicativo se guarda compuesto

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend |

## Contexto

Dos piezas distintas del sistema necesitan explicar, más adelante, por qué pasó algo: el desglose
de puntuación de un lead —qué reglas se cumplieron y cuántos puntos aportó cada una— y el mensaje de
una notificación —qué ocurrió y sobre qué lead o registro—. En ambos casos, la explicación depende
de datos —una regla de puntuación, un lead, un registro de ingesta— que pueden borrarse o cambiar
después de que el hecho ya ocurrió.

## Decisión

El texto explicativo se compone en el momento en que ocurre el hecho y se guarda ya hecho, junto al
dato que explica, en vez de reconstruirse leyendo sus referencias cuando alguien lo consulta. El
desglose de puntuación de un lead guarda el nombre y los puntos de cada regla que se cumplió, no
sólo su identificador; el mensaje de una notificación se redacta y se persiste al crearla, no cuando
alguien la lee.

Es el mismo criterio aplicado dos veces, con la misma razón: el dato debe poder explicarse aunque su
origen ya no exista. Es lo que permite borrar una regla de puntuación sin dejar leads mudos.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Guardar sólo la referencia (el identificador de la regla, del lead, del registro) y componer el texto al leer | Obliga a cargar cada entidad referenciada sólo para mostrar una explicación, y rompe en cuanto una de ellas se borra o cambia: una regla eliminada dejaría un lead sin poder explicar su puntuación, y un lead eliminado dejaría una notificación muda |
| Guardar referencia y texto a la vez, recalculando el texto si la referencia sigue viva | Añade una rama de lógica —¿sigue viva la referencia o no?— para un beneficio que nadie pidió: la explicación de un hecho pasado no debería cambiar aunque la regla que lo causó se edite después |

## Consecuencias

**Fácil:** borrar una regla de puntuación o un lead no deja huérfano nada que dependiera de
explicarlo: cada desglose y cada notificación sigue explicándose con el texto que se guardó en su
momento, sin ningún join adicional en la consulta que lo muestra.

**Difícil:** el texto guardado puede quedar desactualizado a propósito respecto al estado actual del
sistema —si una regla se renombra después, el desglose de un lead antiguo sigue mostrando el nombre
viejo—, y un lead borrado deja notificaciones cuyo enlace ya no lleva a ninguna parte, aunque el
mensaje se siga leyendo con sentido.

## Ver también

- [Reglas](../modulos/reglas.md)
- [Notificaciones](../modulos/notificaciones.md)
- [Recorrido de un lead](../arquitectura/recorrido-de-un-lead.md)
