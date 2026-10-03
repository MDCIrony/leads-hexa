# Arquitectura de servicios

Lead Router son cuatro servicios con datos propios detrás de un gateway nginx. Cada servicio tiene su
API y su worker, con imagen y base propias:

| Servicio | Procesos | Posee |
|---|---|---|
| `identity` | `identity`, `identity-worker` | Autenticación, MFA, OAuth, organizaciones, agentes, credenciales de integración. Único con la clave de firma |
| `intake` | `intake`, `intake-worker` | Fuentes, trabajos, registros y ficheros de ingesta. Pide la decisión de cada registro a lead-core |
| `lead-core` | `lead-core`, `lead-core-worker` | Leads, reglas, grupos y asesores; decide viabilidad, puntuación y asignación |
| `notifications` | `notifications`, `notifications-worker` | La bandeja de avisos y sus tres consumidores |

El `gateway` (nginx, `:8001`) es la única entrada: autentica con `auth_request` contra identity y enruta por
prefijo. RabbitMQ lleva el trabajo de fondo de intake y Kafka el canal de producto y los eventos
internos. Las decisiones están registradas como ADR
([0031](../decisiones/0031-microservicios-por-contexto.md)–[0037](../decisiones/0037-estructura-y-tamano-del-codigo.md)).

## Decisiones tomadas

| Tema | Decisión | Dónde |
|---|---|---|
| Servicios | `identity`, `intake`, `lead-core`, `notifications` + `gateway` | [02](02-servicios-y-datos.md), [ADR-0031](../decisiones/0031-microservicios-por-contexto.md) |
| Datos | Una base por servicio en el mismo PostgreSQL, rol propio, sin consultas cruzadas | [02](02-servicios-y-datos.md), [ADR-0031](../decisiones/0031-microservicios-por-contexto.md) |
| Código | Monorepo `services/<svc>/`, mismo esqueleto en todos, `libs/chassis` sólo técnico | [02](02-servicios-y-datos.md), [ADR-0037](../decisiones/0037-estructura-y-tamano-del-codigo.md) |
| Gateway | nginx con `auth_request`; única entrada en `:8001` | [03](03-gateway-y-autenticacion.md), [ADR-0032](../decisiones/0032-gateway-y-phantom-token.md) |
| Autenticación | Cookie opaca en el navegador (ADR-0029 intacto) + *phantom token*: JWT interno Ed25519 de 60 s que cada servicio verifica en local | [03](03-gateway-y-autenticacion.md), [ADR-0032](../decisiones/0032-gateway-y-phantom-token.md) |
| Servicio a servicio | HTTP/JSON con token de servicio; gRPC descartado por ahora | [03](03-gateway-y-autenticacion.md), [07](07-evoluciones-y-riesgos.md) |
| Hechos | Kafka: `leads.{tenant_id}` sin cambios + topics `internal.*`; estado en topics compactados | [04](04-comunicacion-y-eventos.md), [ADR-0033](../decisiones/0033-eventos-internos-en-kafka.md) |
| Trabajo | RabbitMQ `intake.jobs` sin cambios de topología; encolado por outbox | [04](04-comunicacion-y-eventos.md), [ADR-0034](../decisiones/0034-encolado-por-outbox-y-fichero-durable.md) |
| Ingesta → decisión | `POST /internal/v1/admissions` síncrono e idempotente por `intake_record_id` | [04](04-comunicacion-y-eventos.md), [ADR-0035](../decisiones/0035-admision-sincrona-idempotente.md) |
| Contrato público | Dos cambios acotados: `/advisors` y `/intake/stats` | [02](02-servicios-y-datos.md), [ADR-0036](../decisiones/0036-cambios-de-contrato-publico.md) |
| Despliegue | Docker Compose; Kubernetes queda como evolución con criterio | [05](05-despliegue-local.md) |

## Vista del sistema

```mermaid
flowchart TB
    B(["Navegador"]) --> FE["frontend<br/>nginx estático :80"]
    FE -->|"/api/v1"| GW
    EXT(["Integrador<br/>X-Api-Key"]) --> GW["gateway<br/>nginx :8001"]

    GW -.->|"auth_request"| ID
    GW --> ID["identity"]
    GW --> IN["intake"]
    GW --> LC["lead-core"]
    GW --> NO["notifications"]

    ID --> IDB[("identity_db")]
    IN --> INDB[("intake_db")]
    LC --> LDB[("leads_db")]
    NO --> NDB[("notifications_db")]

    IN -->|"outbox → intake.jobs"| RMQ["RabbitMQ"]
    RMQ --> INW["intake-worker"]
    INW -->|"POST /internal/v1/admissions"| LC

    ID -->|"internal.identity.*"| K["Kafka"]
    IN -->|"internal.intake.events"| K
    LC -->|"internal.lead-core.events"| K
    LC -->|"leads.{tenant_id}"| K
    K --> LC
    K --> IN
    K --> NO
    K -->|"leads.{tenant_id}"| CRM(["Sistema del cliente"])
```

## Cómo leer esta sección

| Página | Responde |
|---|---|
| [02 · Servicios y datos](02-servicios-y-datos.md) | Qué servicios, qué posee cada uno, el patrón de construcción |
| [03 · Gateway y autenticación](03-gateway-y-autenticacion.md) | Cómo entra una petición y cómo cada servicio sabe quién la hace |
| [04 · Comunicación y eventos](04-comunicacion-y-eventos.md) | Cuándo HTTP, RabbitMQ o Kafka; topics, outbox, consumidores, contrato de admisión |
| [05 · Despliegue local](05-despliegue-local.md) | Compose, bases, imágenes, puertos y tests |
| [07 · Evoluciones y riesgos](07-evoluciones-y-riesgos.md) | Lo que se descartó por ahora y la señal que lo justificaría |

## Invariantes que la separación no negocia

Las invariantes de la plataforma rigen en **cada** servicio, más tres propias de la separación:

- **La organización sale del token** (ADR-0004). En el borde, del JWT interno; entre servicios, del
  dato persistido por el servicio que llama, nunca de la entrada del usuario final.
- **404, no 403**, al leer una entidad de otra organización (ADR-0005).
- **SQL crudo**, migraciones idempotentes, guardián 4/4 por servicio.
- **Cada servicio sólo lee y escribe su base.** Lo que necesita de otro llega por API,
  evento o proyección. Nunca un `JOIN` entre bases.
- **Toda publicación sale de un outbox local**, en la transacción del agregado que la
  produce. Todo consumidor deduplica por `event_id`.
- **Ningún servicio importa código de otro.** Sólo `libs/chassis`, y sólo desde
  `infrastructure`.

## Qué queda fuera a propósito

- Un servicio por router o por tabla, y partir scoring, viabilidad y asignación: los tres comparten
  una transacción (bloqueo de `rr_cursor` + lead + outbox) que no compensa distribuir.
- Servicios de Delivery, Reporting u Organizaciones separados de Identity.
- Kubernetes, service mesh, gRPC, CQRS y motores de workflow.
- Cambiar el contrato externo `leads.{tenant_id}`.

Cada exclusión tiene su señal de revisión en [Evoluciones y riesgos](07-evoluciones-y-riesgos.md).
