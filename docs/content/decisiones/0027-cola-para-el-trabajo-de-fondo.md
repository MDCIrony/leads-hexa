# ADR-0027 · Una cola para el trabajo de fondo

| | |
|---|---|
| **Estado** | Aceptada — sustituye a [ADR-0019](0019-trabajo-de-fondo-en-proceso.md). El *fallback* en proceso y el parseo del fichero en la API quedan sustituidos por [ADR-0034](0034-encolado-por-outbox-y-fichero-durable.md) al completar F1 |
| **Fecha** | 2026-08-24 |
| **Ámbito** | Backend · Infraestructura |

## Contexto

El [ADR-0019](0019-trabajo-de-fondo-en-proceso.md) dejó el procesamiento de un intake corriendo en
el mismo proceso que la API, con `BackgroundTasks`, y asumió su riesgo explícitamente: si el
contenedor cae mientras procesa un fichero, el trabajo queda a medias y nadie lo retoma solo. Se
mitigó haciéndolo **reprocesable a mano**, y se dejó escrito que construir una cola en ese momento
habría sido infraestructura para un riesgo que el propio ADR elegía asumir.

Ese riesgo ya no es aceptable en el mismo grado: un intake puede traer hasta 10.000 leads
(`ProcessIntakeJobUseCase._MAX_ITEMS_PER_RUN`), y perder ese progreso a mitad de fichero por un
reinicio del contenedor —para retomarlo solo cuando alguien note que quedó a medias— es justo el
coste que el ADR-0019 decidió absorber por no tener aún dónde apoyar una cola. Ahora sí lo tiene:

- **0.2** hizo que `start()` acepte un job en `PROCESSING`, no sólo `PENDING` — sin eso, redisparar un
  job interrumpido lo rechazaba.
- **0.3** hizo que los contadores de `IntakeJob` se **deriven** con `count_by_tenant` en vez de
  acumularse con `record_success`/`record_failure` — sin eso, una redelivery duplicaría la cuenta.

Esas dos piezas son lo que hace segura una redelivery **por construcción**, no por suerte. Este ADR
es el que por fin las usa.

## Por qué RabbitMQ y no Kafka

El [ADR-0026](0026-kafka-como-canal-del-producto.md) ya introdujo un bróker en este backend, para el
canal de salida del producto. Éste es un problema distinto y pide el bróker contrario:

- **El canal de salida es un hecho publicado.** El cliente debe poder reobtenerlo — por eso Kafka,
  con su log de retención y sus offsets, y por eso el ADR-0026 descartó explícitamente RabbitMQ para
  ese caso: «borra el mensaje al confirmarlo».
- **Esto es trabajo, no un hecho.** Un job se coge, se hace y se confirma; si el que lo cogió muere,
  otro lo repite. Eso es exactamente lo que da una cola con `ack` manual, redelivery y DLQ — y es
  justo lo que Kafka no da sin emularlo con offsets y grupos de consumidores, dependiendo entonces el
  reparto entre workers de cómo caigan las particiones. **El reparto es el reparto de RabbitMQ.**

No son alternativas intercambiables: son la respuesta a dos preguntas distintas, con dos bróker
distintos.

## Decisión

Una cola `intake.jobs`, cuórum, con `ack` manual tras terminar el trabajo (nunca al recibir: un job
confirmado antes de acabar es un job perdido si el worker muere a mitad) y una DLQ `intake.jobs.dlq`
para lo que falla de forma persistente:

- **`x-delivery-limit: 3` en la propia cola**, no un contador llevado a mano por la aplicación
  leyendo la cabecera `x-death`. Es la razón de que `intake.jobs` sea de tipo `quorum`: ese argumento
  sólo existe ahí. Al tercer intento fallido, RabbitMQ mismo mueve el mensaje a `intake.jobs.dlq` vía
  `x-dead-letter-exchange` — no hay una cuarta redelivery que programar ni cancelar.
- **El mensaje lleva `{"tenant_id", "job_id"}` y nada más.** El trabajo ya está en base de datos
  (ADR-0010); meter el payload también en la cola sería tenerlo en dos sitios que pueden discrepar.
  El worker relee el job y sus registros `PENDING` antes de tocar nada.
- **El puerto `JobQueuePort.enqueue_intake_job` devuelve `bool`, no lanza.** Es el único puerto de
  salida de este repositorio que rompe ese patrón, a propósito: que el bróker esté caído no es culpa
  de quien envió el lead, y el endpoint necesita poder decidir en vez de que la excepción decida por
  él. `RabbitMQJobQueue` abre una conexión nueva por llamada en vez de mantener una abierta —
  FastAPI corre los endpoints síncronos en un pool de hilos, y `pika.BlockingConnection` no es segura
  para compartir entre hilos.
- **El backend arranca sin RabbitMQ.** Si `enqueue_intake_job` devuelve `False`, el trabajo se
  procesa con `BackgroundTasks`, exactamente como hacía antes de este ADR. Degradar es preferible a
  rechazar el lead de un cliente porque nuestra cola interna está caída; no es un descuido, es el
  comportamiento elegido.
- **La subida de un fichero se encola por su mitad larga, no entera.** Parsear el fichero necesita
  sus bytes, que sólo viven en la memoria de la petición, así que eso sigue ocurriendo en el proceso
  de la API. Pero cuando termina, cada fila ya es un `intake_record` duradero, y **puntuar y enrutar
  diez mil de ellas —que es la parte que de verdad muere con el proceso— se encola igual que un lead
  suelto**, con el mismo respaldo. Encolar el fichero completo habría exigido meter sus bytes en el
  mensaje, contradiciendo la decisión de arriba sobre qué lleva dentro.
- **El worker es un proceso aparte** (`infrastructure/workers/intake_worker.py`), servicio propio de
  compose que comparte imagen con el backend y difiere sólo en el comando que ejecuta. Es exactamente
  lo que el ADR-0019 excluía a propósito de este alcance, y lo que este cambio introduce ahora que hay
  dónde apoyarlo. Consume con `prefetch_count=1`: un job a la vez por worker, porque son largos y un
  prefetch mayor dejaría a un worker acaparando varios mientras otro está libre.
- **Ante `DomainException` de job inexistente, el worker confirma el mensaje igual.** Reintentar un
  job que no existe no lo hace aparecer. Ante cualquier otra excepción, el worker hace `nack` con
  `requeue=True` y sigue consumiendo — no se cae por un job problemático, y es esa redelivery la que
  alimenta el `x-delivery-limit` hasta la DLQ.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Kafka también para esto, reutilizando el bróker del ADR-0026 | Resuelve «publicar un hecho reobtenible», no «repartir un trabajo que se reintenta si quien lo cogió muere». Emularlo exigiría offsets, grupos de consumidores y ceder el reparto entre workers a cómo caigan las particiones — control que una cola da de fábrica |
| Contar los intentos a mano con la cabecera `x-death` y una cola clásica | Duplica en la aplicación algo que `x-delivery-limit` ya resuelve en el bróker desde RabbitMQ 3.10, a cambio de más código propio que puede desincronizarse del límite real |
| Mantener una conexión RabbitMQ abierta en el `Container`, en vez de una por llamada | Más rápida por llamada, pero `pika.BlockingConnection` no es segura entre hilos y FastAPI ejecuta los endpoints síncronos en un pool; compartirla exigiría un lock que el volumen de este endpoint no justifica |
| Un `depends_on` bloqueante de `backend` sobre `rabbitmq` | Repetiría el mismo error que el ADR-0026 evitó con Kafka: la API no debe dejar de arrancar, ni de aceptar leads, porque un bróker interno esté caído |

## Consecuencias

**Fácil:** un contenedor que cae a mitad de un fichero de 10.000 leads ya no deja el trabajo varado
—otro worker, o el mismo tras reiniciar, lo retoma sin que nadie tenga que reprocesar a mano—, y un
job que falla de forma persistente deja de tapar la cola indefinidamente: a la tercera, la DLQ.

**Difícil:** un segundo bróker que operar y monitorizar además de Kafka, con su propio servicio de
compose y su propia imagen de worker. `intake.jobs.dlq` no tiene todavía consumidor ni alerta propia
— un mensaje que llega ahí se queda ahí hasta que alguien lo mire a mano, lo cual es una mejora sobre
"nadie lo retoma nunca" pero no es todavía observabilidad real. La conexión por llamada en
`RabbitMQJobQueue` añade el coste de un handshake AMQP en cada ingesta con la cola arriba, a cambio de
no necesitar gestionar el ciclo de vida de una conexión compartida.

## Ver también

- [ADR-0019 · Trabajo de fondo en el mismo proceso](0019-trabajo-de-fondo-en-proceso.md)
- [ADR-0010 · Recepción y procesamiento separados](0010-recepcion-y-procesamiento-separados.md)
- [ADR-0026 · Kafka como canal del producto](0026-kafka-como-canal-del-producto.md)
- [Ingesta](../modulos/ingesta.md)
