# Operar la mensajería

Cómo se levanta, qué mirar cuando algo no llega, y qué no está resuelto todavía.

## Levantar la pila

```bash
docker compose up -d db backend                # la API, sin mensajería
docker compose up -d kafka rabbitmq            # los brókeres
docker compose up -d backend-worker            # los relays del outbox
docker compose up -d notifications notifications-worker  # la bandeja y sus tres consumidores
docker compose up -d intake-worker             # el trabajador de ingesta
```

**El orden no importa y la API no espera a nadie.** Ni `kafka` ni `rabbitmq` son `depends_on`
bloqueantes del servicio `backend`, que sólo escribe en el outbox: si no están, las filas esperan y
`backend-worker` reintenta; `notifications-worker` lo hace con sus carriles. Está verificado — con ambos brókeres apagados, `/health` responde `200`
y los leads se guardan; con sólo RabbitMQ apagado, una ingesta responde `202` y su trabajo queda
`PENDING` hasta que el bróker vuelve (`verify_ms_f1`).

`backend-worker` tampoco espera a los brókeres: reintenta la creación de sus topics y entrega por
canales independientes, así que Kafka caído no detiene los jobs ni RabbitMQ caído detiene las
notificaciones. Al reiniciarlo no se pierde nada: una fila sin marcar se entrega otra vez, y los
consumidores deduplican por `event_id`.

`notifications-worker` espera a que `notifications` esté sano, porque la API aplica las migraciones al
arrancar y los consumidores escriben esas tablas, pero no espera a Kafka: sus carriles reintentan
hasta que el bróker responde. No tiene *healthcheck*: ningún servicio depende de él, los carriles se
reparan solos y su fallo queda en el log.

El único que sí espera es `intake-worker`, con `depends_on: rabbitmq: condition: service_healthy`:
sin bróker no tiene nada que hacer, y esperar evita un ciclo de arrancar y morir. Una vez arriba,
si el bróker cae, reconecta solo.

| Servicio | Puerto en el equipo | Para qué |
|---|---|---|
| `gateway` | 8001 | La API |
| `kafka` | 9094 | El consumidor de prueba, desde fuera de la red de compose |
| `kafka-ui` | 8004 | Consola de Kafka: topics, mensajes, grupos |
| `rabbitmq` | 5672 · 15672 | AMQP y el panel de administración |
| `test-consumer` | 8003 | La aplicación del cliente, tras `--profile demo` |

**Kafka tiene tres direcciones, no dos.** `9092` sin autenticación dentro de la red, `9094` con SASL
para la máquina anfitriona, y `9095` con SASL **también dentro de la red**. El tercero existe porque
el segundo se anuncia como `localhost`, que dentro de otro contenedor resuelve a ese contenedor: un
consumidor que corre en esta red necesita una dirección que resuelva aquí *y* una credencial. Las
ACL son por principal, así que aísla exactamente igual.

## Cuando algo no llega

Cuatro sitios donde mirar, en este orden.

### 1 · ¿Está registrado en el outbox?

```sql
SELECT channel, event_type,
       count(*) FILTER (WHERE published_at IS NOT NULL) AS publicados,
       count(*) FILTER (WHERE published_at IS NULL)     AS pendientes
FROM outbox_events
GROUP BY channel, event_type;
```

Si no hay fila, el problema está **antes** del transporte: el evento no se registró. Si la hay con
`published_at` a `NULL`, el relay de ese canal no ha conseguido entregarla — y `last_error` dice por
qué:

```sql
SELECT id, channel, event_type, attempts, last_error, correlation_id
FROM outbox_events
WHERE published_at IS NULL
ORDER BY attempts DESC
LIMIT 20;
```

Un `attempts` que crece sin parar señala un destino roto. **Nada se descarta por eso**: la entrada se
hunde en el orden del lote para no bloquear a las nuevas, y se sigue reintentando. El `channel` dice
qué proceso mirar: `product` es Kafka del cliente y webhooks, `internal` son los topics `internal.*`
y `job` es RabbitMQ; los tres entregan desde `backend-worker`. Lo que se entrega a `internal.*` lo
consume `notifications-worker`.

### 2 · ¿Llegó al topic?

```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

cd tools/test-consumer && python consume.py --tenant <uuid> --from-beginning
```

Para el canal del cliente, el `test-consumer`. Para `internal.*`, [kafka-ui](http://localhost:8004)
(**Topics → Messages**) o el consumidor de consola:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic internal.lead-core.events --from-beginning \
  --property print.headers=true --timeout-ms 5000
```

Si `internal.*` no aparece en la lista, `backend-worker` aún no ha podido crear sus topics: sus logs
dicen `Kafka topics not ready` mientras reintenta. Lo mismo vale para `internal.dlq.*` y
`notifications-worker`.

### 3 · ¿Se aplicó en el consumidor?

```bash
docker compose logs notifications-worker --tail=50

docker compose exec kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 --describe --group notifications.lead-events
```

`LAG` creciente es un consumidor parado o lento; con `Attempt n/3 failed` en el log, un evento que no
se aplica y acabará en la DLQ. Los grupos son `notifications.lead-events`,
`notifications.intake-events` y `notifications.members`. Un evento ya aplicado figura en
`processed_events` de `notifications_db` (el grupo `notifications.members` no lo usa):

```bash
docker compose exec db psql -U postgres -d notifications_db \
  -c "SELECT consumer, count(*) FROM processed_events GROUP BY consumer"
```

### 4 · ¿Se procesó el trabajo?

```bash
docker compose logs intake-worker --tail=50
docker compose exec rabbitmq rabbitmqctl list_queues name messages
```

Una `intake.jobs` que crece y no baja significa que el worker no está consumiendo. Mensajes en
`intake.jobs.dlq` son trabajos que fallaron tres veces: **nadie avisa de ellos**, hay que mirar.

El `X-Request-Id` de la petición que originó el problema (el que devuelve la API en la cabecera, o el
`correlation_id` de la fila del outbox) aparece en las líneas de log de los tres procesos:

```bash
docker compose logs backend-worker notifications-worker intake-worker | rg <request-id>
```

`notifications-worker` no escribe una línea por mensaje: el `X-Request-Id` sólo aparece en sus logs si
algo falla o se reintenta. Lo que prueba que el consumidor lo aplicó es el aviso en `notifications`.

## Las colas muertas y cómo reinyectar un mensaje

| Cola muerta | Qué contiene | Dónde se ve |
|---|---|---|
| `internal.dlq.notifications.lead-events` | Eventos de `internal.lead-core.events` que fallaron tres veces | kafka-ui, **Topics** |
| `internal.dlq.notifications.intake-events` | Lo mismo para `internal.intake.events` | kafka-ui, **Topics** |
| `internal.dlq.notifications.members` | Estados de agente que no se pudieron proyectar, de `internal.identity.agents` | kafka-ui, **Topics** |
| `intake.jobs.dlq` | Trabajos entregados tres veces sin terminar, o mensajes malformados | Consola de RabbitMQ ([localhost:15672](http://localhost:15672), **Queues**) |

Un mensaje de `internal.dlq.<grupo>` es el sobre original, con las cabeceras originales más `error`,
`attempts`, `original_topic`, `original_partition` y `original_offset`. `attempts=0` significa que no
se pudo ni interpretar como sobre: **reinyectarlo tal cual falla otra vez** y vuelve a la DLQ sin
reintentos. Un mensaje así sólo se recupera produciendo un sobre válido corregido a mano, o se
descarta.

**No hay reinyección automática.** Primero se corrige la causa (la cabecera `error` y el log de
`notifications-worker` la dicen), y luego a mano:

- **Evento interno.** Se vuelve a producir el mensaje en el topic de `original_topic`, con la misma
  clave y el mismo valor: en kafka-ui, **Produce Message** sobre ese topic, o `kafka-console-producer.sh`
  con `--property parse.key=true`. No hace falta nada más: el mensaje fallido nunca llegó a
  `processed_events`, porque su transacción se deshizo, así que se aplica como si fuera nuevo.
- **Trabajo.** El mensaje solo lleva identificadores; el trabajo vive en base. Con la causa corregida,
  `POST /api/v1/intake/jobs/{job_id}/reprocess` registra una orden nueva en el outbox. Después se vacía
  el mensaje de `intake.jobs.dlq` desde la consola (**Purge**). Un trabajo `COMPLETED` o `FAILED` no se
  puede reprocesar.

## Sembrar el estado de identidad

Los topics `internal.identity.agents` e `internal.identity.tenants` sólo contienen el estado escrito
desde que existen. Para publicar el estado actual de **todos** los agentes y organizaciones, por
ejemplo antes de que un consumidor nuevo se suscriba:

```bash
docker compose exec backend-worker python -m infrastructure.cli.publish_identity_snapshot
```

Registra un `AgentState` o `TenantState` por fila en el outbox `internal`, por páginas de 100, y
`backend-worker` los entrega. Se puede repetir sin riesgo: cada mensaje lleva la `version` de su fila,
y una proyección descarta lo que ya tiene.

## Qué no está resuelto

Ninguno de estos puntos es un descuido: están asumidos y anotados. Pero conviene tenerlos a la vista
antes de llevar esto más allá de una máquina de desarrollo.

### Bloqueante para desplegar fuera

| Hueco | Consecuencia |
|---|---|
| ~~Kafka en PLAINTEXT, sin autenticación~~ | **Resuelto** — [ADR-0028](../decisiones/0028-autenticacion-de-la-mensajeria.md): sólo `PLAINTEXT_HOST` (9094) admitía esto, y ahora exige SASL/SCRAM con ACL por organización |
| ~~Sin credencial de máquina en la API~~ | **Resuelto** — [ADR-0028](../decisiones/0028-autenticacion-de-la-mensajeria.md): `POST /agents/integration-credential` |
| **Credenciales de RabbitMQ en claro** en el compose, sin TLS | Aplazado con razón escrita, no olvidado: ver «Alternativas consideradas» en el [ADR-0028](../decisiones/0028-autenticacion-de-la-mensajeria.md#alternativas-consideradas) |

Las dos primeras iban juntas a propósito: una credencial de API mientras el bróker estaba abierto de
par en par era seguridad de teatro. El ADR-0028 cierra ambas en la misma tanda.

### Configuración que nadie eligió

| Valor | Está en | Debería |
|---|---|---|
| Retención de **168 horas** | El valor por defecto de Kafka | Elegirse por cliente: hoy reobtener funciona siete días |
| **`num.partitions=1`** | El valor por defecto | El ADR-0026 justifica `lead_id` como clave «para que el topic escale», y con una partición esa ventaja no existe |
| **`AUTO_CREATE_TOPICS_ENABLE=true`** | El compose | Aprovisionamiento explícito: un `tenant_id` mal escrito crea un topic fantasma en silencio |

### Resuelto desde entonces

- **Kafka no conservaba nada.** El volumen que declara la imagen en `/var/lib/kafka/data` estaba
  vacío: `log.dirs` apuntaba por defecto a `/tmp/kafka-logs`, en la capa de escritura del
  contenedor. Cada recreación se llevaba por delante los topics, los mensajes retenidos y —por vivir
  en `__cluster_metadata`— las credenciales SASL y las ACL. Una semana de historia reobtenible no se
  sostiene sobre espacio de usar y tirar. Ahora `KAFKA_LOG_DIRS` apunta al volumen nombrado
  `kafkadata`, verificado sobreviviendo a un `rm` del contenedor.

### Operación

- **El outbox crece sin podarse.** Las filas publicadas se quedan. Es a propósito mientras sean el
  único registro de lo que salió, pero un volumen real necesitará archivarlas.
- **`processed_events` e `intake_files` tampoco se podan.** La primera crece con cada evento
  consumido, y la segunda guarda los bytes de cada fichero subido (hasta 10 MB cada uno).
- **Nadie mira las DLQ**, ni `intake.jobs.dlq` ni `internal.dlq.*`: no hay alerta, y reinyectar es
  manual.
- **Sin observabilidad**: ni retraso del consumidor, ni profundidad de cola, ni alerta por entradas
  atascadas en el outbox.

## Lo que sí está demostrado

| Garantía | Cómo se comprueba |
|---|---|
| Un lead guardado tiene su evento registrado, y al revés | Test de integración: un `record()` seguido de `rollback` no deja fila |
| Una entrada que falla no se pierde ni bloquea a las demás | Test de integración: 25 fallos seguidos y sigue en el lote, detrás de las nuevas |
| La API arranca y sirve con ambos brókeres caídos | `/health` responde `200`; verificado a mano |
| Con RabbitMQ caído una ingesta no se pierde | `verify_ms_f1`: `202`, el trabajo sigue `PENDING`, y al volver el bróker termina y el lead existe |
| Una notificación llega por Kafka sin duplicarse al releer el grupo desde el principio | `verify_ms_f1` |
| Los topics de identidad están compactados y las DLQ existen y están vacías | `verify_ms_f1` (los dos grupos de avisos) y `verify_ms_f2` (los tres) |
| La bandeja la sirve `notifications` a través del gateway y el backend ya no la tiene | `verify_ms_f2` |
| El recorrido completo sobre HTTP | `./scripts/verify-e2e.sh` |
