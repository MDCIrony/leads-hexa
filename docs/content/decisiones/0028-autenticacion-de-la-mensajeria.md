# ADR-0028 · Autenticación de la mensajería

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-24 |
| **Ámbito** | Backend · Infraestructura |

## Contexto

Un aplazamiento anterior sobre la credencial de integración dejó escrito el cierre exacto de este
hueco: *«Cuándo entra: 1. SASL/SCRAM en Kafka... 2. La credencial de máquina en la API»*. Verificado
contra el código y `docker-compose.yml`, dos huecos seguían abiertos en la tabla «Bloqueante para
desplegar fuera» de [Operar la mensajería](../eventos/operacion.md):

- **Kafka en PLAINTEXT, sin autenticación.** Cualquiera con acceso a la red del host lee los topics
  de **todas** las organizaciones por el listener mapeado a `9094`.
- **Sin credencial de máquina en la API.** Un sistema externo sólo puede llamar a
  `GET /leads?updated_since=` con un token de persona.

Las dos entran juntas, no por separado: una credencial de API mientras el bróker está abierto de par
en par es seguridad de teatro, y peor, deja escrito en el código que el asunto está resuelto sin
estarlo. El TLS de RabbitMQ, tercer hueco de esa misma tabla, se aplaza — ver «Alternativas
consideradas».

## Decisión

### Sólo el listener del host pasa a SASL/SCRAM

`docker-compose.yml` ya declaraba tres listeners con dos audiencias: `PLAINTEXT` (9092, interno,
nunca mapeado a `ports:`), `CONTROLLER` (9093, KRaft) y `PLAINTEXT_HOST` (9094, el único alcanzable
desde fuera de la red de compose). El hueco vivía en `PLAINTEXT_HOST` únicamente, así que sólo ése
pasa a `SASL_PLAINTEXT` con `SCRAM-SHA-256`; `PLAINTEXT` y `CONTROLLER` se quedan como están.

Tres consecuencias de esa frontera:

1. `KafkaOutboundDispatcher` y su `Producer` no cambian: siguen conectando por `kafka:9092`, sin
   autenticación, el mismo perímetro de confianza que ya asume Postgres en este compose.
2. No hace falta reformatear el volumen ni un `kafka-storage.sh format --add-scram`: eso sólo es
   necesario cuando el tráfico *entre brokers* también debe autenticarse, y aquí
   `KAFKA_INTER_BROKER_LISTENER_NAME` sigue siendo `PLAINTEXT`.
3. Con `authorizer.class.name=StandardAuthorizer` activo, una conexión sin SASL resuelve al principal
   `User:ANONYMOUS`. Declararlo `super.users` es lo que deja aprovisionar credenciales sin una cuenta
   de arranque propia — el propio listener interno es la vía administrativa.

**Cómo se entrega el JAAS del lado servidor — corregido en la implementación.** El plan original
proponía montar una propiedad `sasl.jaas.config` suelta en `/mnt/shared/config/`, asumiendo que el
entrypoint de `apache/kafka:3.7.0` la fusionaría con `server.properties`. **Verificado contra un
arranque real: no lo hace** — `KafkaDockerWrapper` copia el fichero tal cual a
`/opt/kafka/config/security.properties`, que el broker nunca lee, y arranca reventando con
`Could not find a 'KafkaServer'... entry in the JAAS configuration`. El mecanismo que sí funciona,
confirmado en el log de arranque, es el estándar de la JVM: un fichero JAAS real
(`kafka/kafka_server_jaas.conf`) montado en el contenedor, y `KAFKA_OPTS` apuntando
`-Djava.security.auth.login.config` a esa ruta — que además es obligatorio en cuanto
`KAFKA_ADVERTISED_LISTENERS` incluye un listener `SASL_*` (el propio script de arranque lo exige con
`ensure KAFKA_OPTS`).

### Un usuario Kafka por organización con ACL; el cliente consume directo

`tools/test-consumer/consume.py` habla **directo** con el bróker, sin pasar por la API — es la razón
de ser del [ADR-0026](0026-kafka-como-canal-del-producto.md): la reobtención por offset es lo que
vende Kafka, y forzar el consumo a pasar por un intermediario HTTP la anularía. Por tanto:

- El productor sigue siendo uno solo (el backend), sobre el listener interno sin autenticación: no
  hay más de un proceso produciendo, así que no hace falta un usuario por organización ahí.
- El consumo sí lo necesita: `ResourcePatternType.LITERAL` sobre `leads.{tenant_id}`, operaciones
  `READ` + `DESCRIBE`, principal `User:tenant-{tenant_id}`.
- El grupo de consumidor lleva un ACL `PREFIXED` sobre **`tenant-{tenant_id}`**, que es el propio
  principal: **la regla que el cliente tiene que cumplir es la misma cadena con la que ya se
  autentica**, y no depende del nombre de ninguna herramienta nuestra. Nombrarlo a partir de
  `consume.py` habría dejado sin poder consumir a cualquier cliente real que use su propio
  `group.id` —que es lo que hace un cliente real—. Es `PREFIXED` y no `LITERAL` porque un consumidor
  puede tener varios grupos, y porque `consume.py` añade un sufijo aleatorio en cada ejecución para
  que un segundo `--from-beginning` no reanude desde el commit del primero.

**Verificado en vivo, con la pila completa**: la credencial de la organización A lee su propio topic
y recibe el mensaje publicado; las mismas credenciales contra el topic de la organización B fallan
con `TOPIC_AUTHORIZATION_FAILED` del propio bróker.

### La credencial de máquina en la API

- **Cabecera propia, `X-Api-Key`**, no una segunda forma de `Authorization: Bearer` — mantiene los
  dos caminos de autenticación separados en vez de exigir *sniffear* cuál es cuál.
- **Formato `{agent_id}.{secret}`**: el identificador va en claro en la propia clave (no es secreto),
  igual que un JWT lleva el `sub` en claro en su payload firmado.
- **Vive en `agents`**, con `role=AgentRole.INTEGRATION` y el mismo `BcryptPasswordHasher` que un
  agente humano. No se crea tabla nueva: reutiliza el hash, `RequestContext` y la desactivación ya
  existentes, con un correo determinista (`integration@{tenant.slug}.invalid`, TLD reservado por la
  [RFC 2606](https://www.rfc-editor.org/rfc/rfc2606)) que aprovecha la unicidad de correo por
  organización sin una comprobación nueva.
- **`POST /agents/integration-credential` es upsert**: alta y rotación son la misma operación, para
  que no existan dos rutas que puedan divergir. La revocación es `DELETE /agents/{agent_id}`, el
  endpoint que ya existe.
- **Alcance mínimo**: sólo `GET /leads`. `AgentRole.INTEGRATION` no pasa
  `require_organization_manager` (sigue exigiendo `MANAGER`), así que ampliar el alcance a otro
  endpoint el día de mañana es una línea, no un cambio de diseño.
- **Kafka se aprovisiona antes que el agente**, fuera de la transacción de Postgres: si el bróker no
  admite la credencial, no se crea ninguna fila en `agents`. Emitir una clave de API sin su
  contraparte en Kafka es exactamente la seguridad de teatro que este ADR cierra.

### Una credencial no es un asesor

Revisión posterior al primer borrador del plan: `RawSqlAgentRepository.list_by_tenant` (detrás de
`GET /agents`) y `get_available_agents` (el pool de candidatos del motor de asignación) no excluían
`AgentRole.INTEGRATION`. Sin el filtro, la fila de una credencial de máquina aparecería en la
plantilla de asesores del gestor y podría acabar nombrada en una regla de asignación, recibiendo
leads que nadie va a trabajar. Las dos consultas —y `count_by_tenant`, que `GetAgentsUseCase` ya
exige mantener en el mismo filtro que `list_by_tenant` o el total deja de cuadrar con la página—
excluyen el rol en SQL (`role <> 'INTEGRATION'`), no en el caso de uso: los dos únicos llamadores
quieren lo mismo, y un tercero que aparezca mañana hereda el acierto en vez de tener que acordarse.
`get_by_id_and_tenant` se deja **sin** ese filtro a propósito: es la vía que usa
`DeactivateAgentUseCase` para revocar, y filtrarla ahí rompería la revocación.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| mTLS en vez de SASL/SCRAM | Exige una CA propia, emitir y rotar certificados por organización, y un cliente capaz de presentarlos — carga operativa que este MVP no sostiene sin un paso de aprovisionamiento externo al propio `docker compose up` |
| Un usuario Kafka también por organización en el lado productor | Nunca hay más de un proceso produciendo (el backend, sobre el listener interno); no aporta aislamiento que no exista ya |
| TLS en RabbitMQ en esta misma tanda | Aplazado, no descartado: RabbitMQ ya tiene autenticación (`leads`/`leadspassword`), su puerto sólo se expone para tooling local, y ni `backend` ni `intake-worker` salen de la red de compose — el mismo perímetro que ya asume Postgres. El ADR-0027 tampoco prometía TLS. Kafka sí tenía un consumidor externo real contra un puerto mapeado, que es donde vivía el hueco de verdad |
| Montar `sasl.jaas.config` como propiedad suelta en `/mnt/shared/config/` | Verificado contra un arranque real: esta imagen no fusiona ese fichero con `server.properties`, sólo lo copia sin usar. El broker no arranca. Sustituido por un fichero JAAS real más `KAFKA_OPTS` |

## Consecuencias

**Fácil:** un tercero se integra con una sola llamada a `POST /agents/integration-credential` y
recibe lo que necesita tanto para HTTP (`X-Api-Key`) como para Kafka (usuario, contraseña, topic).
Revocar es el mismo `DELETE /agents/{agent_id}` que ya existía para cualquier agente.

**Difícil:** si el bróker está caído en el instante de emitir la credencial, la operación entera
falla con `503 MESSAGING_UNAVAILABLE` y no hay reintento automático — consecuencia directa y
deliberada de no dejar nunca una credencial de API sin su contraparte de Kafka; verificado que la
espera hasta ese fallo es de hasta 10 s, el `request_timeout_seconds` del adaptador. Revocar puede
dejar la credencial Kafka huérfana si el bróker no responde justo en ese instante: se registra con un
aviso, sin reintento, mismo criterio que ya acepta este repositorio para la DLQ de `intake.jobs` sin
consumidor. Sin test de integración contra un Kafka con SASL real en la suite automática: el
aislamiento entre organizaciones sólo se demuestra a mano (o en el propio log de esta
implementación), igual que el resto de lo que el ADR-0026 ya dejó fuera de la suite.

## Ver también

- [ADR-0025 · Outbox transaccional](0025-outbox-transaccional.md)
- [ADR-0026 · Kafka como canal del producto](0026-kafka-como-canal-del-producto.md)
- [ADR-0027 · Una cola para el trabajo de fondo](0027-cola-para-el-trabajo-de-fondo.md)
- [Autenticación de la mensajería](../eventos/autenticacion.md)
