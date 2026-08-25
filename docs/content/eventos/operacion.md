# Operar la mensajería

Cómo se levanta, qué mirar cuando algo no llega, y qué no está resuelto todavía.

## Levantar la pila

```bash
docker compose up -d db backend                # la API, sin mensajería
docker compose up -d kafka rabbitmq            # los brókeres
docker compose up -d intake-worker             # el trabajador
```

**El orden no importa y la API no espera a nadie.** Ni `kafka` ni `rabbitmq` son `depends_on`
bloqueantes del servicio `backend`: si no están, el relay reintenta y la ingesta se degrada a
trabajo en proceso. Está verificado — con ambos brókeres apagados, `/health` responde `200` y los
leads se guardan.

El único que sí espera es `intake-worker`, con `depends_on: rabbitmq: condition: service_healthy`:
sin bróker no tiene nada que hacer, y esperar evita un ciclo de arrancar y morir.

| Servicio | Puerto en el equipo | Para qué |
|---|---|---|
| `backend` | 8001 | La API |
| `kafka` | 9094 | El consumidor de prueba, desde fuera de la red de compose |
| `rabbitmq` | 5672 · 15672 | AMQP y el panel de administración |
| `test-consumer` | 8003 | La aplicación del cliente, tras `--profile demo` |

**Kafka tiene tres direcciones, no dos.** `9092` sin autenticación dentro de la red, `9094` con SASL
para la máquina anfitriona, y `9095` con SASL **también dentro de la red**. El tercero existe porque
el segundo se anuncia como `localhost`, que dentro de otro contenedor resuelve a ese contenedor: un
consumidor que corre en esta red necesita una dirección que resuelva aquí *y* una credencial. Las
ACL son por principal, así que aísla exactamente igual.

## Cuando un lead no llega al cliente

Tres sitios donde mirar, en este orden:

### 1 · ¿Está registrado en el outbox?

```sql
SELECT event_type,
       count(*) FILTER (WHERE published_at IS NOT NULL) AS publicados,
       count(*) FILTER (WHERE published_at IS NULL)     AS pendientes
FROM outbox_events
GROUP BY event_type;
```

Si no hay fila, el problema está **antes** del transporte: el evento no se registró. Si la hay con
`published_at` a `NULL`, el relay no ha conseguido entregarlo — y `last_error` dice por qué:

```sql
SELECT id, event_type, attempts, last_error
FROM outbox_events
WHERE published_at IS NULL
ORDER BY attempts DESC
LIMIT 20;
```

Un `attempts` que crece sin parar señala un destino roto. **Nada se descarta por eso**: la entrada se
hunde en el orden del lote para no bloquear a las nuevas, y se sigue reintentando.

### 2 · ¿Llegó al topic?

```bash
docker exec leads-hexa-kafka-1 \
  /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

cd tools/test-consumer && python consume.py --tenant <uuid> --from-beginning
```

Si el topic no existe, nunca se le publicó nada: la creación es automática al primer mensaje.

### 3 · ¿Se procesó el trabajo?

```bash
docker compose logs intake-worker --tail=50
docker exec leads-hexa-rabbitmq-1 rabbitmqctl list_queues name messages
```

Una `intake.jobs` que crece y no baja significa que el worker no está consumiendo. Mensajes en
`intake.jobs.dlq` son trabajos que fallaron tres veces: **nadie avisa de ellos**, hay que mirar.

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
- **Nadie mira la DLQ.**
- **Sin observabilidad**: ni retraso del consumidor, ni profundidad de cola, ni alerta por entradas
  atascadas en el outbox.
- **El worker no reconecta** por su cuenta; `restart: on-failure` lo recupera.

## Lo que sí está demostrado

| Garantía | Cómo se comprueba |
|---|---|
| Un lead guardado tiene su evento registrado, y al revés | Test de integración: un `record()` seguido de `rollback` no deja fila |
| Una entrada que falla no se pierde ni bloquea a las demás | Test de integración: 25 fallos seguidos y sigue en el lote, detrás de las nuevas |
| La API arranca y sirve con ambos brókeres caídos | `/health` responde `200`; verificado a mano |
| La cola caída no rechaza leads | Test unitario del respaldo, con la excepción real que lanza el cliente |
| El recorrido completo sobre HTTP | `./scripts/verify-e2e.sh` — 138 comprobaciones |
