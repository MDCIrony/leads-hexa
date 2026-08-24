# ADR-0023 · Los eventos del canal de salida

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-24 |
| **Ámbito** | Backend · Dominio · Aplicación |

Sustituye a [ADR-0016 · Sólo eventos con consumidor](0016-solo-eventos-con-consumidor.md).

## Contexto

El [ADR-0016](0016-solo-eventos-con-consumidor.md) acotó el catálogo de eventos a los cuatro que
tenían un manejador en proceso: un evento que nadie escuchaba era una clase, una prueba y un punto de
publicación que mantener sin beneficio. Ese razonamiento describía una plataforma cerrada, donde
todo consumidor vivía en este repositorio.

Ya no es el caso. El producto consiste en **procesar los leads con las reglas del cliente y
publicarle los que pasan el filtro**, para que él reciba trabajo aprovechable en vez de todo lo que
entró por el formulario. El consumidor de esos eventos es su sistema, y vive fuera de aquí.

Con la regla del 0016, `LeadProcessedEvent` era el único evento del canal, y salía para todo lead que
no hubiera sido rechazado en la validación —incluidos los que una regla de viabilidad acababa de
descalificar—. El cliente recibía la basura que nuestras reglas filtraron, y volvía a filtrarla de su
lado: exactamente el trabajo por el que nos paga.

## Decisión

Un evento del **canal de salida** existe porque describe un hecho que el producto publica, no porque
haya un manejador de este proceso suscrito a él. Su contrato es la razón de existir; el consumidor es
externo por definición.

Los eventos **internos** —los que alimentan las notificaciones del panel— siguen bajo la regla del
0016: sin consumidor en proceso, no se construyen. Son dos catálogos con dos criterios, no uno
relajado.

El canal de salida arranca con dos eventos de significado disjunto:

| Evento | Significa |
|---|---|
| `LeadProcessedEvent` | El lead pasó el filtro: quedó `ASSIGNED` o `UNASSIGNED` |
| `LeadDisqualified` | Una regla de viabilidad lo descartó, con el nombre de la regla que lo hizo |

`LeadDisqualified` se construye y se publica desde ya, aunque su consumidor externo llegue con la
mensajería. El `WebhookEventHandler` **no** se suscribe a él: un cliente que hoy recibe webhooks de
leads procesados no debe empezar a recibir de golpe el doble de tráfico con los descartados. Se
suscribirá cuando exista configuración de webhooks salientes por tipo de evento, o cuando exista el
topic de auditoría.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Mantener el 0016 y publicar sólo `LeadProcessedEvent`, dejando que el cliente filtre los descalificados | Pone nuestro filtro de su lado y le factura tráfico que existe para tirarlo; es el trabajo que el producto vende |
| Un solo evento con un campo `disqualified: bool` | Obliga a todo consumidor a leer el campo antes de saber si el mensaje le sirve, y hace imposible enrutar los dos hechos a destinos distintos sin abrir el cuerpo del mensaje |
| Esperar a Kafka para construir `LeadDisqualified` | El hecho ocurre hoy y hoy se pierde; construir el evento no depende del transporte, y dejarlo para después obliga a rehacer el punto de publicación cuando llegue |

## Consecuencias

**Fácil:** el canal de salida puede describir lo que de verdad ocurre sin esperar a que su consumidor
exista en este repositorio, y el cliente recibe leads aprovechables en vez de una mezcla que tiene
que volver a filtrar. Enrutar cada hecho a un destino distinto —el producto a un sitio, la auditoría
a otro— no exige inspeccionar el cuerpo del mensaje.

**Difícil:** vuelve posible un evento que nadie consuma nunca. La disciplina que lo evita pasa de
«tiene manejador» a «está en el contrato publicado», que es una comprobación de documentación y no de
código: nada en la suite falla si se añade un evento al canal que después no se publica en ningún
sitio.

## Ver también

- [ADR-0016 · Sólo eventos con consumidor](0016-solo-eventos-con-consumidor.md)
- [ADR-0017 · Retirada de `webhook_dispatched`](0017-retirada-de-webhook-dispatched.md)
