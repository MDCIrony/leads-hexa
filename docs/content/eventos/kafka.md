# Kafka · el canal del producto

Kafka es lo que el cliente compra: **sus leads procesados, en un flujo propio, que puede volver a
leer**. No es un detalle de infraestructura; es la forma que tiene el producto de entregarse.

Decisión que lo fija: [ADR-0026](../decisiones/0026-kafka-como-canal-del-producto.md).

## Por qué un log y no una cola

La pregunta que decide no es «¿cuál es mejor?», sino **qué pide el cliente**:

> *Si en algún punto necesito los elementos, quiero poder reobtenerlos.*

```mermaid
flowchart LR
    subgraph cola["Cola de trabajo"]
        direction TB
        C1["Mensaje"] --> C2["Consumidor"] --> C3["ack"] --> C4["Desaparece"]
        C4 -.->|"¿y si lo necesito otra vez?"| C5["Ya no está"]
    end
    subgraph log["Log con retención"]
        direction TB
        L1["Mensaje"] --> L2["Se queda"]
        L2 --> L3["Consumidor A · offset 100"]
        L2 --> L4["Consumidor B · offset 0"]
        L4 -.->|"vuelve al principio"| L2
    end
```

Una cola **borra el mensaje al confirmarlo**. Quien ya lo consumió no puede volver a por él, y
emularlo exigiría que nosotros guardásemos una copia y expusiéramos una API de reenvío — es decir,
reimplementar un log con retención, peor.

Un log guarda el mensaje aunque alguien ya lo haya leído, y cada consumidor lleva su propia
posición. Reobtener es mover un número hacia atrás. **Ese requisito es el que elige la tecnología**,
no una preferencia.

## Un topic por organización

`leads.{tenant_id}`, con `lead_id` como clave de partición y `event_type` en la cabecera del
mensaje.

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| **Un topic por organización** | Uno compartido con `tenant_id` dentro | Obligaría a filtrar en el consumidor. El aislamiento entre organizaciones es un invariante del sistema, no una cortesía. Además abre la puerta a retención y credenciales distintas por cliente |
| **Los dos hechos en el mismo topic**, separados por cabecera | Un topic por tipo de evento | Repartirlos rompería el orden entre «se procesó» y «se descartó» del mismo lead, que es justo lo que garantiza la clave de partición |
| **`lead_id` como clave** | `tenant_id` como clave | Con `tenant_id`, una organización entera sería una sola partición. Con `lead_id`, todo lo de un lead llega en orden y el topic puede repartirse |

## Qué viaja dentro

El contrato completo del lead, no un identificador. **Quien lo recibe está fuera de este sistema y
no tiene una llamada que hacer para averiguar de quién se trata.**

```json
{
  "schema_version": 1,
  "event_id": "da8970dc-48de-4188-8c42-ea89cbd075ec",
  "occurred_on": "2026-08-24T20:05:41.511670+00:00",
  "tenant_id": "04047f84-...",
  "lead_id": "e40fa333-...",
  "source_id": "c2f8766a-...",
  "first_name": "Ana",
  "last_name": "Diaz",
  "email": "ana@lead.test",
  "phone": null,
  "company": "Acme",
  "industry": "Tech",
  "budget": "9000.00",
  "custom_attributes": {},
  "score": 65,
  "score_breakdown": [
    { "rule_id": "788ff56f-...", "name": "tech o saas", "score_delta": 40 },
    { "rule_id": "f9748a4d-...", "name": "presupuesto alto", "score_delta": 25 }
  ],
  "status": "UNASSIGNED",
  "assigned_agent_id": null,
  "assigned_at": null,
  "created_at": "2026-08-24T20:05:41.507122+00:00"
}
```

Tres detalles que no son casuales:

- **`budget` es una cadena, nunca un número.** La columna es `NUMERIC(14, 2)` porque un presupuesto
  es dinero, y entregarlo como coma flotante binaria tiraría la exactitud justo donde el dato sale
  de nuestras manos.
- **`score_breakdown` viaja con el evento.** El cliente puede explicar la puntuación sin
  preguntarnos, y sin que las reglas que la produjeron tengan que seguir existiendo.
- **`event_id` es la clave de deduplicación.** La entrega es *at-least-once*: si el relay muere
  entre entregar y marcar, el mismo hecho sale dos veces con el mismo identificador.

## Dos hechos, no uno ambiguo

| Evento | Significa | Va al webhook |
|---|---|---|
| `LeadProcessedEvent` | Pasó el filtro: `ASSIGNED` o `UNASSIGNED` | Sí |
| `LeadDisqualified` | Una regla lo descartó, con el nombre de la regla | **No** |

Antes se publicaba **todo** por el mismo evento, incluidos los leads que nuestras reglas acababan de
descartar. El cliente recibía la basura que habíamos filtrado y volvía a filtrarla de su lado: justo
el trabajo por el que nos paga.

`LeadDisqualified` sí llega a Kafka —es la traza de auditoría— pero **no** al webhook: un cliente que
hoy recibe webhooks de leads procesados no debe empezar a recibir de golpe el doble de tráfico.

## La reobtención, en la práctica

```bash
cd tools/test-consumer

python consume.py --tenant <uuid> --sasl-username tenant-<uuid> --sasl-password <secreto>                  # desde ahora
python consume.py --tenant <uuid> --sasl-username tenant-<uuid> --sasl-password <secreto> --from-beginning # todo lo retenido
```

`--sasl-username`/`--sasl-password` los emite `POST /agents/integration-credential` — ver
[Autenticación](autenticacion.md).

El script no importa nada del backend **a propósito**: es lo que un cliente escribiría por su
cuenta, y si necesitara una librería nuestra sería señal de que el contrato no se sostiene solo.

## El backend arranca sin Kafka

El servicio `kafka` no lleva `depends_on` desde `backend` ni desde `backend-worker`. Si el bróker no
responde, la API sigue aceptando y guardando leads: sólo escribe en el outbox. El relay del canal
`product`, que vive en `backend-worker`, falla al entregar, lo registra y reintenta en el ciclo
siguiente; lo que no salió se queda en el outbox. Es exactamente el comportamiento que el outbox
existe para dar, y está verificado: con Kafka apagado, `/health` responde `200` y los leads se
guardan.

## Los topics internos

Además de `leads.{tenant_id}`, el sistema usa Kafka entre sus propios procesos
([ADR-0033](../decisiones/0033-eventos-internos-en-kafka.md)). Son topics `internal.*`, separados del
canal del cliente: un contrato con terceros y uno interno evolucionan a ritmos distintos, y el
primero no debe exponer datos internos a la organización.

| Topic | Qué lleva | Configuración | Quién lo lee |
|---|---|---|---|
| `internal.lead-core.events` | `LeadAssigned`, `LeadReassigned`, `LeadLeftUnassigned` | 3 particiones, `delete`, 7 días | Grupo `notifications.lead-events` |
| `internal.intake.events` | `IntakeRejected` | 3 particiones, `delete`, 7 días | Grupo `notifications.intake-events` |
| `internal.identity.agents` | `AgentState`: el estado completo de cada agente | 3 particiones, **`compact`** | Nadie todavía |
| `internal.identity.tenants` | `TenantState`: el estado completo de cada organización | 3 particiones, **`compact`** | Nadie todavía |
| `internal.dlq.<grupo>` | Lo que un grupo no pudo procesar | 1 partición, `delete`, 7 días | Un humano |

Los hechos se retienen siete días; el estado se **compacta**: de cada clave sólo importa el último
mensaje, y una copia derivada se reconstruye leyendo el topic desde el principio. Cada mensaje de
estado lleva la `version` de su fila (la sube la base en cada escritura), para que quien lo
proyecte descarte lo que ya tiene.

**Se crean al arrancar `backend-worker`**, con `ensure_topics`, idempotente y con reintentos mientras
Kafka no responda. El productor interno lleva `allow.auto.create.topics=false`: un topic que se
perdiera después debe fallar a la vista, no reaparecer sin compactación por la creación automática del
bróker. Mientras los topics no existen, el canal `internal` no entrega y sus filas esperan en el
outbox.

Los productores usan `acks=all`, `enable.idempotence=true` y `message.timeout.ms=9000`, por debajo
de los 10 s de `flush`: un mensaje que el productor aún reintenta no puede llegar después de que su
fila se haya marcado como fallida.

### El sobre

Los topics internos llevan un sobre común; `leads.{tenant_id}` conserva su forma, porque es un
contrato con terceros.

```json
{
  "event_id": "7a4dfb8d-2b5d-46d9-a5ea-9e83a5c0e3ad",
  "event_type": "LeadAssigned",
  "schema_version": 1,
  "occurred_at": "2026-10-01T10:00:00+00:00",
  "producer": "lead-core",
  "tenant_id": "04047f84-...",
  "aggregate_id": "e40fa333-...",
  "correlation_id": "f0d7fdf8-...",
  "payload": { "lead_id": "e40fa333-...", "agent_id": "9b1c..." }
}
```

El `payload` depende del evento: `LeadAssigned`, `LeadReassigned` y `LeadLeftUnassigned` llevan
`lead_id` (y `agent_id` los dos primeros, más `previous_agent_id` el segundo); `IntakeRejected`
lleva `intake_record_id` y `reason`, y su `aggregate_id` es el `intake_record_id`.

La clave del mensaje es el `aggregate_id` (el lead, el registro de ingesta, el agente o la organización), y `event_type` y
`correlation_id` viajan también como cabeceras. `producer` es `lead-core` en todos los eventos:
mientras sólo el monolito escribe, publica en nombre de todos los contextos.

### El consumidor de notificaciones

`NotificationConsumer` corre en `backend-worker`, un hilo por grupo, sobre `chassis.consumer`:

- `processed_events (consumer, event_id)` se escribe **en la misma transacción** que las
  notificaciones: un duplicado encuentra la marca y no hace nada, y un fallo deshace ambas cosas.
- El offset se confirma **después** del commit en base.
- Tres intentos, con espera creciente; al tercer fallo el mensaje se aparca en
  `internal.dlq.<grupo>` con cabeceras `error`, `attempts` y `original_topic`/`partition`/`offset`, y
  el offset avanza. Un mensaje que no es un sobre válido va directo a la DLQ, sin reintentos.
- Si la DLQ no se puede escribir, el consumidor retrocede al offset y vuelve a intentarlo; una
  partición cuyo retroceso falla queda bloqueada hasta que ese mensaje se resuelve, para no confirmar
  por encima de él.
- Si un consumidor muere por un fallo del cliente de Kafka, el hilo construye otro tras una espera de
  1 s que se duplica hasta 30 s.

## Límites de hoy

| Límite | Consecuencia |
|---|---|
| **Retención de 168 h** (el valor por defecto, no elegido) | Reobtener funciona siete días |
| **`num.partitions=1`** por defecto | La clave de partición está bien elegida, pero el reparto que justifica todavía no existe |
| **`AUTO_CREATE_TOPICS_ENABLE=true`** | Un `tenant_id` mal escrito crea un topic fantasma en silencio. Los `internal.*` quedan fuera: se crean a propósito y su productor no usa la creación automática |

Los tres están asumidos como decisiones de MVP con fecha de caducidad, no como descuidos. El cuarto
límite que estaba aquí —el listener del host sin autenticación— ya se cerró:
[ADR-0028](../decisiones/0028-autenticacion-de-la-mensajeria.md).
