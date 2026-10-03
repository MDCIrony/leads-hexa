# ADR-0033 · Eventos internos en Kafka, outbox por canal y estado compactado

| | |
|---|---|
| **Estado** | Aceptada — implantada |
| **Nota** | Revisión final de F1: el relay entrega, por canal, sólo la fila más antigua no publicada de cada `partition_key`, para que el estado compactado no quede en una versión vieja; ver [el outbox](../eventos/outbox.md#el-orden-se-garantiza-por-partition_key) |
| **Fecha** | 2026-10-01 |
| **Ámbito** | Backend · Mensajería |

## Contexto

Las notificaciones se publican con `InMemoryEventPublisher`, que no cruza procesos y pierde el aviso
si el proceso cae entre el commit y el handler. El relay del outbox corre en un hilo de la API. Al
separar servicios, además, lead-core y notifications necesitan datos de identidad (asesores activos,
managers de cada tenant) que ya no pueden leer con un `JOIN`.

## Decisión

- **Los hechos internos viajan por Kafka**, en topics `internal.*` separados del canal de producto
  `leads.{tenant_id}`, cuyo contrato no cambia.
- **Hechos y estado se separan.** `internal.lead-core.events` e `internal.intake.events` llevan hechos
  (7 días de retención). `internal.identity.agents` e `internal.identity.tenants` llevan el **estado
  completo** de cada entidad con su `version`, en topics **compactados**: una proyección se reconstruye
  desde cero leyendo el topic.
- **Los topics internos se crean explícitamente** al arrancar el worker productor
  (`ensure_topics()`), no por *auto-create*, que no compacta.
- **Sobre común** para los eventos internos: `event_id`, `event_type`, `schema_version`,
  `occurred_at`, `producer`, `tenant_id`, `aggregate_id`, `correlation_id` y `payload`.
- **Outbox con canal.** `outbox_events.channel` ∈ {`product`, `internal`, `job`}; cada despachador sólo
  atiende su canal. El relay sale de la API y vive en el proceso `worker` de cada productor.
- **Consumidor idéntico en todos**: `processed_events (consumer, event_id)` en la misma transacción
  que el efecto, offset confirmado después del commit, tres reintentos y aparcamiento en
  `internal.dlq.<grupo>`. Las proyecciones hacen *upsert* por `version`.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| RabbitMQ (exchange `topic`) para los eventos internos | Borra al confirmar: una proyección no podría reconstruirse ni un consumidor nuevo leer la historia. Es trabajo, no hechos ([ADR-0026](0026-kafka-como-canal-del-producto.md)) |
| Publicar los eventos internos en `leads.{tenant_id}` | Mezcla un contrato con terceros y uno interno, que evolucionan a ritmos distintos, y expondría datos internos al tenant |
| Eventos de cambio (`AgentRenamed`, `AgentDeactivated`…) en vez de estado completo | Reconstruir una proyección exigiría conservar la historia entera y aplicarla en orden; con estado compactado basta el último mensaje por clave |
| Consultar identity por HTTP en cada decisión | Pone a identity en el camino de cada lead y de cada notificación |
| Un relay global para todos los servicios | Tendría que leer bases ajenas; el outbox pertenece a la base del agregado ([ADR-0025](0025-outbox-transaccional.md)) |

## Consecuencias

**Fácil:** ningún aviso depende de que un proceso siga vivo; `LeadAssigned` pasa a registrarse dentro
de la transacción del lead. Una proyección rota se borra y se reconstruye. Un webhook caído deja de
reenviar los eventos internos. Un consumidor nuevo se suscribe sin tocar al productor.

**Difícil:** las proyecciones son eventualmente consistentes. Cada consumidor necesita su tabla
`processed_events`. Hay más topics que crear, observar y versionar. Hay que publicar una vez el estado
existente (`publish_identity_snapshot`) para sembrar los topics compactados.

## Ver también

- [Comunicación y eventos](../microservices/04-comunicacion-y-eventos.md)
- [ADR-0025 · Outbox transaccional](0025-outbox-transaccional.md)
- [ADR-0026 · Kafka como canal del producto](0026-kafka-como-canal-del-producto.md)
- [ADR-0015 · Notificaciones por sondeo](0015-notificaciones-por-sondeo.md)
