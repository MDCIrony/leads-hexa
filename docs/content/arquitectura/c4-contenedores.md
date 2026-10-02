# C4 · Contenedores

El segundo nivel del modelo C4: las piezas desplegables que forman Lead Router, según
`docker-compose.yml`, y cómo hablan entre sí.

## Los contenedores

| Contenedor | Tecnología | Puerto (host:contenedor) | Protocolo | Responsabilidad |
|---|---|---|---|---|
| `frontend` | Nginx sirviendo el build estático de React (Vite) | 80:80 | HTTP | Interfaz web; también hace de proxy inverso de `/api/v1/` hacia `gateway` |
| `gateway` | Nginx (`nginx:1.27-alpine`) | 8001:8080 | HTTP con JSON | Única entrada de la API: enruta, autentica con el *phantom token* (introspección + JWT interno), CORS, `Origin`, `X-Request-Id` y límites. Ver [Gateway y autenticación](../microservices/03-gateway-y-autenticacion.md) |
| `backend` | FastAPI + Uvicorn sobre Python 3.12 | — (sólo red interna, `8000`) | HTTP con JSON | La API salvo identidad y notificaciones: leads, reglas, grupos, asesores, fuentes e ingesta. Verifica el JWT interno con la JWKS de identity y le pide por HTTP, con un token de servicio, el asesor que su proyección aún no tiene. Sólo **escribe** en el outbox: no entrega nada |
| `backend-worker` | La imagen del `backend`, ejecutando `python -m infrastructure.worker` | — | SQL; Kafka; AMQP; HTTP (webhooks) | La entrega: un relay del outbox por canal (`product`, `internal`, `job`). Crea `internal.lead-core.events` e `internal.intake.events` al arrancar. Desde F3 consume `lead-core.advisors` (la proyección `advisors`) e `intake.tenants` (las fuentes por defecto), con sus DLQ |
| `identity` | FastAPI + Uvicorn sobre Python 3.12, imagen de `services/identity` | — (sólo red interna, `8000`) | HTTP con JSON; SQL; Kafka (aprovisiona credenciales) | Autenticación, MFA, OAuth, organizaciones y agentes (`/auth`, `/tenants`, `/agents`). Sirve la introspección, la JWKS, los tokens de servicio y `GET /internal/v1/agents/{agent_id}`. Es el único con la clave de firma. Aplica sus migraciones al arrancar. Base propia, `identity_db` |
| `identity-worker` | La imagen de `identity`, ejecutando `python -m infrastructure.worker` | — | SQL; Kafka | El relay de su outbox (`AgentState`, `TenantState`) a `internal.identity.agents` e `internal.identity.tenants`, que crea al arrancar |
| `notifications` | FastAPI + Uvicorn sobre Python 3.12, imagen de `services/notifications` | — (sólo red interna, `8000`) | HTTP con JSON; SQL | La bandeja: `GET /notifications`, `POST /notifications/read-all` y `POST /notifications/{id}/read`. Verifica el JWT interno con la JWKS de identity y aplica sus migraciones al arrancar. Base propia, `notifications_db` |
| `notifications-worker` | La imagen de `notifications`, ejecutando `python -m infrastructure.worker` | — | Kafka; SQL | Los tres consumidores (`notifications.lead-events`, `notifications.intake-events`, `notifications.members`) y sus DLQ `internal.dlq.<grupo>` |
| `db-bootstrap` | `postgres:16-alpine` | — | SQL | Una sola ejecución: crea los roles y las bases de `identity` y `notifications` (`db/bootstrap.sql`) |
| `intake-worker` | La imagen del `backend`, ejecutando `python -m infrastructure.intake_worker` | — | AMQP; SQL | Consume `intake.jobs` y ejecuta el procesamiento de cada trabajo de ingesta |
| `kafka` | Apache Kafka (KRaft, un nodo) | 9094 | Kafka con SASL (el host); 9092 sin autenticación dentro de la red | El canal del producto `leads.{tenant_id}` y los topics internos `internal.*` |
| `rabbitmq` | RabbitMQ con el plugin de administración | 5672 · 15672 | AMQP | La cola `intake.jobs` y su cola muerta |
| `db` | PostgreSQL 16 (`postgres:16-alpine`) | 5433:5432 | Protocolo de PostgreSQL, vía `psycopg` | Un único servidor con una base por servicio: `leads_db` (backend), `identity_db` y `notifications_db` |
| `docs` | MkDocs Material | 8002:8000 | HTTP | Este sitio, servido desde `docs/content` |

`kafka-ui` (consola de Kafka, 8004) es una herramienta de operación, no parte del producto. Otro
servicio, `backend-test` (e `identity-test` y `notifications-test` para los servicios extraídos), existe sólo bajo
el perfil `test`: construye la misma imagen con destino `test` y ejecuta la suite contra una base de
datos de pruebas. No es un contenedor de producto; ver [Validación](../desarrollo/validacion.md).

```mermaid
flowchart TD
    BROWSER(["Navegador"])

    subgraph SISTEMA["Lead Router"]
        FRONTEND["frontend — Nginx + React"]
        GATEWAY["gateway — Nginx"]
        BACKEND["backend — FastAPI + Uvicorn"]
        BW["backend-worker — relays"]
        IDS["identity — FastAPI"]
        IDW["identity-worker — relay"]
        NOTIF["notifications — FastAPI"]
        NW["notifications-worker — consumidores"]
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
    GATEWAY -->|"el resto, puerto 8000"| BACKEND
    GATEWAY -->|"/notifications, puerto 8000"| NOTIF
    NOTIF -.->|"JWKS"| IDS
    BACKEND -.->|"JWKS; agents/{id} con token de servicio"| IDS
    IDS -->|"identity_db"| DB
    IDW -->|"lee el outbox"| DB
    IDW -->|"internal.identity.*"| KAFKA
    BACKEND -->|"SQL vía psycopg, puerto 5432"| DB
    NOTIF -->|"notifications_db"| DB
    NW -->|"notifications_db"| DB
    BW -->|"lee el outbox"| DB
    BW -->|"product e internal"| KAFKA
    KAFKA -->|"internal.*"| NW
    KAFKA -->|"internal.identity.*"| BW
    BW -->|"job, con confirmación"| RMQ
    RMQ --> IW
    IW -->|SQL| DB
    BROWSER -->|"HTTP, puerto 8002"| DOCS
```

## Qué depende de qué, y por qué

`db` no depende de ningún otro contenedor: es la base del grafo de arranque. `backend` espera a
que `db` esté saludable (`condition: service_healthy`) antes de arrancar, porque aplica las
migraciones nada más iniciar. `frontend` espera a que `gateway` esté saludable. `gateway` no espera a
nadie: vuelve a resolver los nombres de `backend`, `identity` y `notifications` por DNS en ejecución,
así que arranca sin ellos y sobrevive a que se recreen.

La API no espera a `kafka` ni a `rabbitmq` ([ADR-0026](../decisiones/0026-kafka-como-canal-del-producto.md),
[ADR-0027](../decisiones/0027-cola-para-el-trabajo-de-fondo.md)): sólo escribe en el outbox, y la
entrega es de `backend-worker`, que espera a `db` pero no a Kafka (reintenta sus topics y sigue
entregando el resto de canales). `identity` y `notifications` esperan a `db` y a que `db-bootstrap`
haya terminado; `identity-worker` y `notifications-worker` esperan a su API (que aplica las
migraciones) y no a Kafka. `intake-worker` sí espera a que `rabbitmq` esté saludable: sin
bróker no tiene nada que hacer. Separar la entrega de la API significa que un bróker lento o un
webhook que agota su plazo no consumen capacidad de petición, y que reiniciar la API no interrumpe la
entrega.

`docs` no depende ni de `backend` ni de `db`. Es deliberado: la documentación tiene que poder
leerse incluso cuando el producto no arranca, que es precisamente cuando más se necesita.

## Volúmenes y recarga

`backend`, `identity`, `notifications` y `docs` montan su código fuente como volumen de sólo lectura
(`./backend/src`, `./backend/migrations`, `./services/<svc>/src`, `./services/<svc>/migrations`,
`./docs/content`) en vez de copiarlo en la imagen. Un cambio en un
fichero se sirve sin `--build` ni `restart`: Uvicorn recarga con `--reload`, MkDocs sirve en
caliente, y `backend-worker`, `identity-worker`, `notifications-worker` e `intake-worker` se reinician solos con
`watchfiles` al cambiar su `src` o `libs/chassis/src`. Sólo `pgdata`, el volumen de `db`, persiste datos entre arranques; los demás contenedores
son efímeros por diseño.

## Ver también

- [C4 · Componentes](c4-componentes.md) entra dentro del contenedor `backend`.
- [Puesta en marcha](../desarrollo/puesta-en-marcha.md)
