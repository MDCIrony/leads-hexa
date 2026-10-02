# Contratos entre servicios

Lo que un servicio promete a otro, escrito una sola vez y comprobado por los tests de las dos partes:
quien produce demuestra que su salida conforma; quien consume, que sabe leer las fixtures.

## Qué hay

| Ruta | Contenido |
|---|---|
| `openapi/identity-internal.v1.yaml` | OpenAPI 3.1 de las rutas internas de identity: introspección, JWKS, tokens de servicio y `GET /internal/v1/agents/{agent_id}` |
| `openapi/lead-core-internal.v1.yaml` | OpenAPI 3.1 de las rutas internas de lead-core: `POST` y `GET /internal/v1/admissions` (admisión idempotente y reconciliación) |
| `events/envelope.v1.schema.json` | El sobre de todo evento interno (`$id` `envelope.v1`), tal como lo escribe `chassis.outbox.envelope` y lo lee `chassis.consumer.envelope` |
| `events/<EventType>.v1.schema.json` | Un esquema por evento interno: el sobre más su `event_type` y su `payload` |
| `schemas/identity/*.v1.schema.json` | Los cuerpos JSON de la API interna de identity; el OpenAPI los referencia con `$ref` relativo |
| `schemas/lead-core/*.v1.schema.json` | Los cuerpos de la admisión: petición, resultado (`ADMITTED` o `REJECTED`) y consulta de reconciliación |
| `schemas/intake/job-message.v1.schema.json` | El mensaje de la cola `intake.jobs` de RabbitMQ (`$id` `intake.job-message.v1`) |
| `fixtures/events/<EventType>.v1.json` | Un sobre completo y válido por evento |
| `fixtures/identity/*.v1.json` | Un cuerpo de respuesta válido por esquema de identity. El `access_token` de muestra es `"<opaque>"`, no un JWT |
| `fixtures/lead-core/*.v1.json` | Una petición, un resultado `ADMITTED`, uno `REJECTED` y una consulta de admisión válidos |
| `fixtures/intake/job-message.v1.json` | Un mensaje de job válido |

Los esquemas son JSON Schema 2020-12 y se identifican por su `$id` (`envelope.v1`, `AgentState.v1`,
`identity.agent.v1`…), no por su ruta.

El `status` de `schemas/lead-core/admission-result.v1.schema.json` cubre los seis valores de
`LeadStatus` (`NEW`, `QUALIFIED`, `ASSIGNED`, `UNASSIGNED`, `DISQUALIFIED`, `DISCARDED`): una admisión
repetida devuelve el lead como está ahora, y no sólo los estados que produce una admisión nueva. Se
amplió dentro de v1, como cambio aditivo, antes de que intake lo consumiera
([plan de F4](../docs/content/microservices/06-plan-de-desacople.md#f4-intake)).

Eventos en v1: `AgentState`, `TenantState`, `LeadAssigned`, `LeadReassigned`, `LeadLeftUnassigned`,
`IntakeRejected`. El `payload` es el `as_payload()` del evento: sus campos sin `event_id` ni
`occurred_on`, con `tenant_id`.

## Versionado

- **Cambio compatible:** un campo opcional nuevo, o un fichero nuevo. Se hace en la misma versión: los
  `payload` y los cuerpos declaran `additionalProperties: true` para que un consumidor ignore lo que
  no conoce.
- **Cambio incompatible:** quitar o renombrar un campo, cambiar su tipo, volver obligatorio uno
  opcional. Se escribe un fichero `v2` nuevo junto al `v1`, y los tests de productor y consumidor
  fallan hasta que cada parte se adapta. El `v1` se retira cuando nadie lo produce ni lo consume.

## Quién lo cambia

Sólo quien orquesta. Una pista que necesite un cambio aquí se detiene y lo reporta; no edita el
contrato desde su lado.

## Cómo lo usan los tests

Con `chassis.testing.contracts` (extra `chassis[contracts]`, o `jsonschema` en el grupo `dev`):

```python
from chassis.testing.contracts import assert_conforms, load_fixture

envelope = load_fixture("events/AgentState.v1.json")              # ruta bajo fixtures/
assert_conforms(envelope, "events/AgentState.v1.schema.json")     # ruta bajo contracts/
assert_conforms(load_fixture("identity/agent.v1.json"), "schemas/identity/agent.v1.schema.json")
```

`contracts_root()` busca un directorio `contracts/` con este `README.md` subiendo desde el directorio
de trabajo y desde la propia librería. En Docker se monta de sólo lectura en `/srv/contracts` o en
`/contracts`, que son ancestros del código de cada servicio.
