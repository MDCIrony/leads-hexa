# ADR-0034 · Encolado por outbox y fichero crudo durable

| | |
|---|---|
| **Estado** | Aceptada — implantada. Sustituye parcialmente a [ADR-0027](0027-cola-para-el-trabajo-de-fondo.md) |
| **Fecha** | 2026-10-01 |
| **Ámbito** | Backend · Mensajería · Ingesta |

## Contexto

[ADR-0027](0027-cola-para-el-trabajo-de-fondo.md) encola cada job después de confirmar la recepción y,
si RabbitMQ no responde, lo procesa en el propio proceso de la API con `BackgroundTasks`. Además,
`batch-upload` parsea el fichero en un `BackgroundTask` con los bytes en memoria, y un job con un
registro fallido hace `ACK` y queda en `PROCESSING` hasta que alguien lo reprocesa a mano.

Con lead-core detrás de la red, los fallos transitorios al procesar un registro dejan de ser raros, y
una segunda ruta de ejecución dentro de la API (que además tendría que llamar a lead-core) deja de ser
una degradación aceptable.

## Decisión

- **El encolado pasa por el outbox** (`channel=job`): el job, sus registros y la orden de procesarlo
  se escriben en una transacción, y el relay publica en `intake.jobs` con *publisher confirms*.
- **Se elimina el *fallback* en proceso.** Con RabbitMQ caído, el job espera en el outbox.
- **El fichero de `batch-upload` se guarda crudo** en `intake_files` (`bytea`) dentro de la
  transacción de recepción, con un límite de tamaño en el gateway y en el endpoint. El worker lo parsea.
- **Un job interrumpido hace `nack`** con reencolado, en lugar de `ack`. A la tercera entrega, RabbitMQ
  lo mueve a `intake.jobs.dlq`, como ya fija ADR-0027.
- Se conserva de ADR-0027: la cola cuórum, `x-delivery-limit: 3`, la DLQ, `prefetch_count=1`, el
  mensaje mínimo (ahora con `message_id`, `schema_version` y `correlation_id` aditivos) y el
  reproceso manual.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Mantener el *fallback* en proceso | Dos rutas de ejecución con garantías distintas; en la arquitectura objetivo la API de intake tendría que llamar a lead-core en línea por cada registro |
| Un barrido periódico que reencole jobs `PENDING` antiguos | Recupera tarde y con un umbral arbitrario lo que el outbox entrega en cuanto el broker vuelve |
| Guardar el fichero en un almacén de objetos | Un servicio más que operar para un tamaño que PostgreSQL maneja bien con `bytea` en un MVP |
| Meter el fichero en el mensaje | Contradice ADR-0027: el trabajo vive en base, no en la cola |
| Seguir haciendo `ack` del job interrumpido | Con fallos transitorios frecuentes, los jobs se quedarían varados en `PROCESSING` |

## Consecuencias

**Fácil:** la ingesta es durable de extremo a extremo: lo que recibe un `202` llega a procesarse
aunque caiga cualquier proceso o broker. Hay una sola ruta de ejecución. Un fallo transitorio de
lead-core se recupera solo con la redelivery.

**Difícil:** con RabbitMQ caído un lead no se procesa hasta que vuelve; antes se procesaba en la API.
Los ficheros ocupan espacio en `intake_db` y necesitan una política de retención. Un registro que
falla siempre lleva su job a la DLQ en tres entregas, y recuperarlo sigue siendo manual.

## Ver también

- [ADR-0027 · Una cola para el trabajo de fondo](0027-cola-para-el-trabajo-de-fondo.md)
- [ADR-0009 · Registrar antes de interpretar](0009-registrar-antes-de-interpretar.md)
- [Comunicación y eventos · RabbitMQ](../microservices/04-comunicacion-y-eventos.md#rabbitmq-intakejobs)
