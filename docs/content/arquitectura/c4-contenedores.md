# C4 · Contenedores

El segundo nivel del modelo C4: las piezas desplegables que forman Lead Router, según
`docker-compose.yml`, y cómo hablan entre sí.

## Los contenedores

| Contenedor | Tecnología | Puerto (host:contenedor) | Protocolo | Responsabilidad |
|---|---|---|---|---|
| `frontend` | Nginx sirviendo el build estático de React (Vite) | 80:80 | HTTP | Interfaz web; también hace de proxy inverso de `/api/v1/` hacia `gateway` |
| `gateway` | Nginx (`nginx:1.27-alpine`) | 8001:8080 | HTTP con JSON | Única entrada de la API: enruta, autentica con el *phantom token* (introspección + JWT interno), CORS, `Origin`, `X-Request-Id` y límites. Ver [Gateway y autenticación](../microservices/03-gateway-y-autenticacion.md) |
| `lead-core` | FastAPI + Uvicorn sobre Python 3.12, imagen de `services/lead-core` | — (sólo red interna, `8000`) | HTTP con JSON; SQL | La API salvo identidad, ingesta y notificaciones: leads, reglas, grupos y asesores, más `POST` y `GET /internal/v1/admissions`, que sólo atiende al servicio `intake`. Verifica el JWT interno con la JWKS de identity y le pide por HTTP, con un token de servicio, el asesor que su proyección aún no tiene. Aplica sus migraciones al arrancar. Sólo **escribe** en el outbox: no entrega nada. Base propia, `leads_db`, que sólo abre su rol `lead_core_svc` |
| `lead-core-worker` | La imagen de `lead-core`, ejecutando `python -m infrastructure.worker` | — | SQL; Kafka; HTTP (webhooks) | La entrega: un relay del outbox por canal (`product`, `internal`). Crea `internal.lead-core.events` al arrancar. Consume `lead-core.advisors` (la proyección `advisors`), con su DLQ |
| `identity` | FastAPI + Uvicorn sobre Python 3.12, imagen de `services/identity` | — (sólo red interna, `8000`) | HTTP con JSON; SQL; Kafka (aprovisiona credenciales) | Autenticación, MFA, OAuth, organizaciones y agentes (`/auth`, `/tenants`, `/agents`). Sirve la introspección, la JWKS, los tokens de servicio y `GET /internal/v1/agents/{agent_id}`. Es el único con la clave de firma. Aplica sus migraciones al arrancar. Base propia, `identity_db` |
| `identity-worker` | La imagen de `identity`, ejecutando `python -m infrastructure.worker` | — | SQL; Kafka | El relay de su outbox (`AgentState`, `TenantState`) a `internal.identity.agents` e `internal.identity.tenants`, que crea al arrancar |
| `notifications` | FastAPI + Uvicorn sobre Python 3.12, imagen de `services/notifications` | — (sólo red interna, `8000`) | HTTP con JSON; SQL | La bandeja: `GET /notifications`, `POST /notifications/read-all` y `POST /notifications/{id}/read`. Verifica el JWT interno con la JWKS de identity y aplica sus migraciones al arrancar. Base propia, `notifications_db` |
| `notifications-worker` | La imagen de `notifications`, ejecutando `python -m infrastructure.worker` | — | Kafka; SQL | Los tres consumidores (`notifications.lead-events`, `notifications.intake-events`, `notifications.members`) y sus DLQ `internal.dlq.<grupo>` |
| `intake` | FastAPI + Uvicorn sobre Python 3.12, imagen de `services/intake` | — (sólo red interna, `8000`) | HTTP con JSON; SQL | Fuentes, trabajos, registros y ficheros de ingesta (`/sources`, `/intake`), con `GET /intake/stats`. Verifica el JWT interno con la JWKS de identity y llama a lead-core (`POST /internal/v1/admissions`) con su token de servicio en la promoción manual. Aplica sus migraciones al arrancar. Base propia, `intake_db` |
| `intake-worker` | La imagen de `intake`, ejecutando `python -m infrastructure.worker` | — | AMQP; Kafka; SQL; HTTP (lead-core) | El relay de su outbox (`job` a RabbitMQ, `internal` a Kafka, que crea `internal.intake.events`), el consumo de `intake.jobs` (pide la admisión de cada registro a lead-core) y el de `intake.tenants`, con su DLQ. Espera hasta 5 min al parar, para terminar el trabajo en curso |
| `db-bootstrap` | `postgres:16-alpine` | — | SQL | Una sola ejecución: crea el rol y las bases (`*_db` y `*_test`) de `lead-core`, `identity`, `intake` y `notifications` (`db/bootstrap.sql`) |
| `kafka` | Apache Kafka (KRaft, un nodo) | 9094 | Kafka con SASL (el host); 9092 sin autenticación dentro de la red | El canal del producto `leads.{tenant_id}` y los topics internos `internal.*` |
| `rabbitmq` | RabbitMQ con el plugin de administración | 5672 · 15672 | AMQP | La cola `intake.jobs` y su cola muerta |
| `db` | PostgreSQL 16 (`postgres:16-alpine`) | 5433:5432 | Protocolo de PostgreSQL, vía `psycopg` | Un único servidor con una base y un rol por servicio: `leads_db` (lead-core), `identity_db`, `intake_db` y `notifications_db` |
| `docs` | MkDocs Material | 8002:8000 | HTTP | Este sitio, servido desde `docs/content` |

`kafka-ui` (consola de Kafka, 8004) es una herramienta de operación, no parte del producto. Otro
servicio por cada uno de los cuatro, `lead-core-test`, `identity-test`, `intake-test` y `notifications-test`, existe sólo bajo
el perfil `test`: construye la misma imagen con destino `test` y ejecuta la suite contra una base de
datos de pruebas. No es un contenedor de producto; ver [Validación](../desarrollo/validacion.md).

```mermaid
flowchart TD
    BROWSER(["Navegador"])

    subgraph SISTEMA["Lead Router"]
        FRONTEND["frontend — Nginx + React"]
        GATEWAY["gateway — Nginx"]
        LEADCORE["lead-core — FastAPI + Uvicorn"]
        BW["lead-core-worker — relays"]
        IDS["identity — FastAPI"]
        IDW["identity-worker — relay"]
        NOTIF["notifications — FastAPI"]
        NW["notifications-worker — consumidores"]
        INT["intake — FastAPI"]
        IW["intake-worker"]
        DB[("db — PostgreSQL 16")]
        KAFKA["kafka"]
        RMQ["rabbitmq"]
        DOCS["docs — MkDocs Material"]
    end

    BROWSER -->|"HTTP, puerto 80"| FRONTEND
    FRONTEND -->|"proxy /api/v1/, puerto 8080"| GATEWAY
    BROWSER -->|"HTTP, puerto 8001"| GATEWAY
    GATEWAY -.->|"auth_request: introspección"| IDS
    GATEWAY -->|"/auth, /tenants, /agents"| IDS
    GATEWAY -->|"el resto, puerto 8000"| LEADCORE
    GATEWAY -->|"/notifications, puerto 8000"| NOTIF
    GATEWAY -->|"/sources, /intake, puerto 8000"| INT
    INT -.->|"JWKS; admissions con token de servicio"| IDS
    INT -->|"admissions, token de servicio"| LEADCORE
    IW -->|"admissions, token de servicio"| LEADCORE
    NOTIF -.->|"JWKS"| IDS
    LEADCORE -.->|"JWKS; agents/{id} con token de servicio"| IDS
    IDS -->|"identity_db"| DB
    IDW -->|"lee el outbox"| DB
    IDW -->|"internal.identity.*"| KAFKA
    LEADCORE -->|"SQL vía psycopg, puerto 5432"| DB
    NOTIF -->|"notifications_db"| DB
    NW -->|"notifications_db"| DB
    BW -->|"lee el outbox"| DB
    BW -->|"product e internal"| KAFKA
    KAFKA -->|"internal.*"| NW
    KAFKA -->|"lead-core.advisors"| BW
    KAFKA -->|"intake.tenants"| IW
    INT -->|"intake_db"| DB
    IW -->|"lee el outbox, escribe intake_db"| DB
    IW -->|"internal.intake.events"| KAFKA
    IW -->|"job, con confirmación; consume intake.jobs"| RMQ
    BROWSER -->|"HTTP, puerto 8002"| DOCS
```

## Qué depende de qué, y por qué

`db` no depende de ningún otro contenedor: es la base del grafo de arranque. `lead-core` espera a
que `db` esté saludable (`condition: service_healthy`) y a que `db-bootstrap` haya terminado antes de
arrancar, porque aplica las migraciones nada más iniciar con su propio rol. `frontend` espera a que `gateway` esté saludable. `gateway` no espera a
nadie: vuelve a resolver los nombres de `lead-core`, `identity`, `intake` y `notifications` por DNS en ejecución,
así que arranca sin ellos y sobrevive a que se recreen.

La API no espera a `kafka` ni a `rabbitmq` ([ADR-0026](../decisiones/0026-kafka-como-canal-del-producto.md),
[ADR-0027](../decisiones/0027-cola-para-el-trabajo-de-fondo.md)): sólo escribe en el outbox, y la
entrega es de `lead-core-worker`, que espera a `lead-core` (que aplica las migraciones) pero no a Kafka (reintenta sus topics y sigue
entregando el resto de canales). `identity`, `intake` y `notifications` esperan, como `lead-core`, a `db` y a que
`db-bootstrap` haya terminado; `identity-worker` y `notifications-worker` esperan a su API (que
aplica las migraciones) y no a Kafka. `intake-worker` espera además a `rabbitmq` saludable: sin
bróker no tiene nada que hacer. No espera a `lead-core`: si lead-core cae, el trabajo en curso se
interrumpe y se reentrega. Separar la entrega de la API significa que un bróker lento o un
webhook que agota su plazo no consumen capacidad de petición, y que reiniciar la API no interrumpe la
entrega.

`docs` no depende ni de `lead-core` ni de `db`. Es deliberado: la documentación tiene que poder
leerse incluso cuando el producto no arranca, que es precisamente cuando más se necesita.

## Volúmenes y recarga

`lead-core`, `identity`, `intake`, `notifications` y `docs` montan su código fuente como volumen de sólo lectura
(`./services/<svc>/src`, `./services/<svc>/migrations`, `./docs/content`) en vez de copiarlo en la imagen. Un cambio en un
fichero se sirve sin `--build` ni `restart`: las APIs y MkDocs sirven en
caliente (las APIs reinician Uvicorn con `watchfiles`), y `lead-core-worker`, `identity-worker`, `notifications-worker` e `intake-worker` se reinician solos con
`watchfiles` al cambiar su `src` o `libs/chassis/src`. Sólo `pgdata`, el volumen de `db`, persiste datos entre arranques; los demás contenedores
son efímeros por diseño.

## Ver también

- [C4 · Componentes](c4-componentes.md) entra dentro del contenedor `lead-core`.
- [Puesta en marcha](../desarrollo/puesta-en-marcha.md)
