# ADR-0026 · Kafka como canal del producto

| | |
|---|---|
| **Estado** | Aceptada. **Nota:** `OutboundDispatcherPort` es hoy el protocolo `Dispatcher` de `chassis.outbox`, y el relay que lo usa corre en `backend-worker`. El contrato de `leads.{tenant_id}` no cambia |
| **Fecha** | 2026-08-24 |
| **Ámbito** | Backend · Dominio · Infraestructura |

## Contexto

El [ADR-0025](0025-outbox-transaccional.md) resolvió cómo entregar el canal de salida sin perder
eventos entre el commit y la publicación: un `OutboxRelay` que reparte cada entrada entre uno o más
`OutboundDispatcherPort`. El primero fue el webhook, reutilizando lo que ya existía. Este ADR añade
el segundo, y con él el transporte que de verdad vende el producto.

Lo que el producto vende no es «entregar un mensaje», es que **el cliente tiene sus leads
procesados y puede volver a por ellos**. Un webhook que falla, o un cliente que estuvo caído una
hora, pierde ese tramo para siempre si el único registro es la propia entrega. Una cola de trabajo
tampoco basta: borra el mensaje en cuanto se confirma, así que quien ya lo consumió no puede volver
a pedirlo. Un log con retención sí conserva lo ya entregado, y **la reobtención por offset es lo que
decide Kafka frente a RabbitMQ** — no es una preferencia de bróker, es el requisito del producto.

## Decisión

Un topic por organización, `leads.{tenant_id}`, con `lead_id` como clave de partición y
`event_type` en la cabecera del mensaje:

- **Por organización, no compartido.** Un topic común obligaría a filtrar por `tenant_id` en el
  consumidor, y el aislamiento entre organizaciones es un invariante de este repositorio, no una
  cortesía. Separar por topic también deja abierta la puerta a retención y credenciales distintas
  por cliente, cuando llegue el momento de tenerlas.
- **`LeadProcessedEvent` y `LeadDisqualified` en el mismo topic**, distinguidos por la cabecera
  `event_type`. Repartirlos en dos topics rompería el orden entre «se procesó» y «se descartó» del
  mismo lead, que es justo lo que garantiza la clave de partición.
- **`lead_id` como clave, no `tenant_id`.** Todo lo de un lead cae en la misma partición y llega en
  orden. Con `tenant_id` como clave, cada organización sería una única partición y el topic no
  escalaría más allá de un consumidor por cliente.

`KafkaOutboundDispatcher` es un segundo `OutboundDispatcherPort`, tal como preveía el ADR-0025: usa
`OutboxEntry.payload`, ya serializado una vez por `DomainEvent.as_payload()`, sin una segunda
conversión que mantener sincronizada. Publica con `confluent-kafka` y hace `flush()` antes de
devolver el control — no `poll()` asíncrono — porque el relay marca la fila como publicada en
cuanto `dispatch()` vuelve sin excepción; un envío que sigue en un búfer en memoria y ya se dio por
entregado dejaría al outbox sin significado. El valor de retorno de `flush()` no basta por sí solo
para saber si la entrega tuvo éxito —una entrega que terminó con error también vacía el búfer—, así
que el fallo se lee del callback `on_delivery` que `flush()` dispara, y tanto un error de entrega
como un `flush()` que agota su plazo con mensajes pendientes se traducen en una excepción: es la
única señal que el relay entiende para reintentar en vez de dar la fila por publicada.

**El backend no depende de Kafka para arrancar.** El servicio `kafka` no lleva `depends_on` desde
`backend`: si el bróker no responde, el relay falla al entregar, lo registra y reintenta en el
siguiente ciclo. La API sigue aceptando y guardando leads. Es exactamente el comportamiento que el
outbox existe para dar, y construir el `Producer` no lo compromete — la conexión al bróker no es
parte de su construcción, sólo de sus intentos de entrega.

**El contrato de salida gana dos campos**, declarados en `OutboundEvent` con valor por defecto para
que ningún constructor existente cambie:

- **`schema_version: int = 1`.** Quedó fuera adrede en el contrato original, con el argumento de
  que entraría «cuando exista un consumidor externo que versionar». Ese consumidor es éste.
- **`event_id`**, que ya existía en `DomainEvent`, viaja como clave de deduplicación del
  consumidor. Un mismo lead publicado dos veces —tras la ingesta, y otra vez si se le reasigna a
  mano— lleva dos `event_id` distintos, y eso es correcto: son dos hechos, no un duplicado. Lo que
  el consumidor deduplica con `event_id` es la reentrega del *mismo* hecho, que es lo que produce la
  semántica *at-least-once* del relay.

**Kafka corre en modo KRaft**, sin ZooKeeper: una imagen y un proceso menos que levantar y
mantener, con `apache/kafka:3.7.0`. El puerto **9094** queda expuesto al host —9092 es el listener
de dentro de la red de compose—, y `KAFKA_AUTO_CREATE_TOPICS_ENABLE=true` crea el topic de una
organización la primera vez que se le publica. **Es una decisión de MVP con fecha de caducidad**:
sin aprovisionamiento explícito, cualquier `tenant_id` mal escrito crea un topic nuevo en silencio,
y la retención y las particiones quedan en lo que decida la configuración por defecto del clúster en
vez de una elegida a propósito para cada cliente.

**Sin test de integración contra un bróker real en la suite.** Levantarlo multiplicaría varias veces
los ~45 segundos que cuesta hoy, y lo que demostraría —que `confluent-kafka` sabe hablar con
Kafka— no es código de este repositorio. `tools/test-consumer/` cubre esa comprobación a mano: un
script sin dependencias del backend, tal como lo escribiría un cliente real, con dos modos — desde
ahora, y `--from-beginning` para demostrar la reobtención que es la razón de ser de este ADR.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| RabbitMQ | Borra el mensaje al confirmarlo: un cliente que ya lo consumió no puede volver a pedirlo. Resuelve «entregar», no «poder reobtener», que es lo que el producto vende |
| Un topic único para todas las organizaciones, filtrando por `tenant_id` en el consumo | El aislamiento entre organizaciones es un invariante de este repositorio; delegarlo al filtro de un consumidor externo lo convierte en una cortesía que cualquier cliente mal configurado puede saltarse |
| `tenant_id` como clave de partición | Toda una organización caería en una sola partición: ni escala más allá de un consumidor por cliente, ni gana nada frente a `lead_id`, que además preserva el orden por lead |
| Aprovisionar los topics explícitamente en vez de `auto.create.topics.enable` | Este MVP no tiene todavía dónde enganchar ese paso —ni alta de organización con aprovisionamiento propio, ni un operador que lo dispare—; añadirlo ahora es infraestructura para un flujo que no existe todavía |

## Consecuencias

**Fácil:** el cliente puede reobtener cualquier lead procesado dentro de la ventana de retención del
topic, con el mismo mecanismo con el que reobtendría cualquier hecho pasado — sin un endpoint nuevo
que mantener. Añadir Kafka no tocó el relay ni el punto de registro del outbox, tal como preveía el
ADR-0025.

**Difícil:** `AUTO_CREATE_TOPICS_ENABLE=true` es también su propio riesgo — un `tenant_id` mal
formado crea un topic fantasma sin que nada lo señale, y ninguno de los topics creados así tiene una
retención pensada para el cliente que los usa. La entrega sigue siendo *at-least-once*: un
consumidor que no deduplique por `event_id` verá el mismo hecho más de una vez tras un reintento del
relay. Y el consumidor de prueba es exactamente eso, de prueba — no sustituye una librería cliente
publicada ni documentación de integración para un cliente real.

## Ver también

- [ADR-0019 · Trabajo de fondo en el mismo proceso](0019-trabajo-de-fondo-en-proceso.md)
- [ADR-0023 · Los eventos del canal de salida](0023-eventos-del-canal-de-salida.md)
- [ADR-0024 · El contrato de salida se construye una vez](0024-el-contrato-de-salida-se-construye-una-vez.md)
- [ADR-0025 · Outbox transaccional](0025-outbox-transaccional.md)
