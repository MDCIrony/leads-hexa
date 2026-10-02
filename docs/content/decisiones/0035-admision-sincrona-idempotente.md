# ADR-0035 · Admisión síncrona e idempotente entre Intake y Lead Core

| | |
|---|---|
| **Estado** | Aceptada — se implementa en F4 |
| **Fecha** | 2026-10-01 |
| **Ámbito** | Backend · Ingesta · Asignación |

## Contexto

Hoy `IngestLeadUseCase` reclama el registro (`claim_unpromoted`), crea el lead, evalúa viabilidad,
scoring y asignación, avanza el cursor, marca el registro y escribe el outbox, todo en **una**
transacción. Al separar intake y lead-core en bases distintas, esa transacción desaparece y hay que
decidir cómo pide intake la decisión y qué impide crear dos leads del mismo registro.

## Decisión

- El worker de intake llama a **`POST /internal/v1/admissions`** de lead-core por cada registro
  pendiente, con un token de servicio, el `tenant_id` y el `source_id` del registro, y el candidato.
- La respuesta es `ADMITTED` (con `lead_id`, estado y puntuación) o `REJECTED` (con los errores por
  campo de `Lead.create`). Un 5xx o un *timeout* (5 s) deja el registro `PENDING` y el job interrumpido.
- **Idempotencia por `UNIQUE (tenant_id, intake_record_id)`** en `leads`. Una admisión repetida
  devuelve el mismo `lead_id` sin publicar nada; en una carrera, la perdedora revierte (incluido el
  avance del cursor) y responde con el lead de la ganadora. `REJECTED` no guarda nada porque es
  determinista.
- Intake cierra el registro en su propia transacción y registra `IntakeRejected` en su outbox.
- La promoción manual desde la bandeja usa el mismo endpoint desde la API de intake.
- El adaptador vive detrás de `LeadAdmissionPort`; el transporte es un detalle de infraestructura.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Comando por RabbitMQ y resultado por Kafka | Desacople temporal total, pero dos consumidores nuevos, cierre de jobs y contadores por eventos y más estados intermedios. La migración tendría más riesgo sin una ganancia que el MVP necesite |
| Intake publica el registro en Kafka y lead-core lo consume (coreografía) | Usa Kafka para un comando con un único ejecutor y deja a intake sin saber cuándo cerrar el job |
| Admisión por lotes desde el principio | Optimiza antes de medir; queda como evolución con su señal |
| gRPC | Sin ganancia medible y una segunda pila; cambiar el transporte es cambiar el adaptador |

## Consecuencias

**Fácil:** es el cambio mínimo: hoy el worker ya llama a la decisión a través de un puerto, y sólo
cambia el adaptador. Si lead-core cae, RabbitMQ conserva el job y lo reentrega. El usuario no percibe
el acoplamiento temporal, porque ya recibió su `202`.

**Difícil:** el worker depende de que lead-core esté disponible para avanzar, y un job grande hace una
llamada por registro. Hay que añadir y rellenar `leads.intake_record_id` antes de mover las tablas.
Ingesta y decisión ya no son atómicas: hacen falta la reconciliación y los tests de contrato en los
dos lados.

## Ver también

- [Comunicación y eventos · Contrato de admisión](../microservices/04-comunicacion-y-eventos.md#contrato-de-admision)
- [ADR-0010 · Recepción y procesamiento separados](0010-recepcion-y-procesamiento-separados.md)
- [ADR-0034 · Encolado por outbox y fichero crudo durable](0034-encolado-por-outbox-y-fichero-durable.md)
