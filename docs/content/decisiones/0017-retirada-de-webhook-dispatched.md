# ADR-0017 · Retirada de `webhook_dispatched`

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · API |

## Contexto

La respuesta de la ingesta incluía un campo `webhook_dispatched`, calculado a partir de si el
publicador de eventos existía, no de si algún webhook se había entregado. El publicador se inyecta
siempre, así que el campo valía `True` en toda ingesta, incluso en una organización sin ningún
webhook configurado, e incluso cuando la entrega HTTP real había fallado —el manejador de webhooks
descarta el resultado booleano que su propio envío devuelve—.

## Decisión

El campo `webhook_dispatched` se retira de la respuesta de ingesta y de todo DTO, en vez de
corregirse. Para que dijera la verdad, el caso de uso tendría que conocer si una entrega HTTP hecha
por un manejador desacoplado tuvo éxito, y eso exige que el publicador de eventos devuelva
resultados de sus manejadores al llamador. Con eso, el caso de uso volvería a acoplarse a lo que el
patrón publicador/suscriptor existe precisamente para desacoplar.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Corregir el cálculo para que refleje el resultado real de la entrega | Obliga al publicador a devolver el resultado de cada manejador suscrito, deshaciendo el desacoplamiento entre el caso de uso y sus efectos secundarios que el bus de eventos existe para dar |
| Dejar el campo como está, documentando que es aproximado | Un campo que miente con documentación sigue mintiendo; quien lea la respuesta sin leer la documentación seguirá creyendo que el webhook se entregó |

## Consecuencias

**Fácil:** la respuesta de ingesta deja de afirmar algo que no puede saber. Ningún cliente de la API
puede tomar una decisión basada en un dato falso disfrazado de booleano.

**Difícil:** hoy no hay ninguna forma de consultar, desde la ingesta, si un webhook se entregó. La
entrega es asíncrona por diseño y su resultado se consulta donde vive ese conocimiento, no en la
respuesta de un caso de uso que ya no lo tiene. Una bandeja de entregas de webhook queda pendiente
para cuando exista la configuración de webhooks salientes.

## Ver también

- [ADR-0016 · Sólo eventos con consumidor](0016-solo-eventos-con-consumidor.md)
- [Notificaciones](../modulos/notificaciones.md)
