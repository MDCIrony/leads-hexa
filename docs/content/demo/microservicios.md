# Guion de la demo de microservicios

Recorrido de unos 25 minutos para enseñar cómo funciona Lead Router separado en servicios. Hay que
mostrar qué servicio atiende cada petición, cómo viaja la identidad, cómo se comunican los servicios
y qué pasa cuando uno cae. Cada paso dice qué hacer y **qué tiene que verse**.

El recorrido de producto (reglas, bandas, cliente externo) está en
[La demo de extremo a extremo](index.md). Este guion se centra en la arquitectura.

## Antes de empezar

```bash
docker compose up -d                                   # los servicios de la aplicación
python3 demo/seed.py                                   # Nordwind Solar: gestora, 12 asesores, reglas
cd .slides-microservices && npm run dev                # diapositivas en :3030 (opcional)
```

El sembrado se puede repetir. Credenciales: `gestor@nordwindsolar.test` / `Demo1234`. Los asesores
usan la misma contraseña, por ejemplo `lucia.ferrer@nordwindsolar.test`.

| Qué | Dónde |
|---|---|
| Aplicación (gestora y asesores) | <http://localhost> |
| API pública, a través del gateway | <http://localhost:8001/docs> (lead-core) · `/openapi/identity.json` · `/openapi/intake.json` · `/openapi/notifications.json` |
| **Kafka UI** | <http://localhost:8004> |
| **RabbitMQ** (consola de gestión) | <http://localhost:15672>, usuario `leads`, contraseña `leadspassword` (sólo en desarrollo) |
| Diapositivas | <http://localhost:3030> |
| Diagramas | `docs/content/microservices/diagramas/c4-contenedores.svg` y `comunicacion.svg` |

Para seguir los logs en una segunda terminal:

```bash
docker compose logs -f gateway identity intake intake-worker lead-core lead-core-worker notifications-worker
```

## 1 · El mapa (2 min)

Abre el diagrama C4 (diapositiva o SVG).

- **Qué contar:**
  - Hay cuatro servicios por contexto: identity, intake, lead-core y notifications.
  - Cada uno tiene dos procesos, `api` y `worker`, y su propia base.
  - Cada base sólo la abre su rol (`identity_svc`, `intake_svc`, `lead_core_svc` y `notifications_svc`).
  - Delante está un gateway nginx, que es la única puerta de entrada.
- **Qué tiene que verse:** `docker compose ps` lista `identity`, `intake`, `lead-core` y
  `notifications`, cada uno con su `-worker`, más `gateway`, `db`, `kafka` y `rabbitmq`. No queda
  ningún `backend`.

## 2 · Entrar: gateway, identity y phantom token (4 min)

Entra en la aplicación como la gestora.

- **Qué contar:**
  - El navegador sólo guarda una cookie opaca, `leads_session`, que es un valor aleatorio.
  - En cada petición el gateway pregunta a identity quién es el portador de esa cookie. Lo hace con
    `auth_request` a `/internal/v1/auth/introspect`.
  - identity devuelve un JWT firmado (Ed25519) que dura 60 s.
  - El gateway sustituye `Authorization` por `Bearer <JWT>`, quita la cookie y reenvía la petición
    al servicio.
  - El servicio comprueba la firma con la clave pública de identity (la JWKS, que guarda en caché) y
    construye el usuario a partir de los claims `sub`, `tid`, `role` y `ptype`.
- **Dónde está:**
  - `gateway/protected.inc`: `auth_request` y `auth_request_set`.
  - `gateway/nginx.conf`: el `map` que forma `Bearer …` y las `location` de `/_introspect`.
  - `gateway/proxy_headers.inc`: la línea que sobrescribe `Authorization`.
- **Qué tiene que verse:**
  - En las herramientas del navegador (Application → Cookies) aparece `leads_session`, un valor
    opaco, no un JWT.
  - En el log del gateway, cada línea lleva `rid=…` y `upstream=<IP:8000>`: la de `GET /api/v1/leads`
    apunta a la IP de `lead-core`, y la de `GET /api/v1/notifications` a la de `notifications`.
- **El token por dentro.** Este comando muestra los claims que reciben los servicios. El token nunca
  sale de la red:

  ```bash
  SESS=$(curl -s -c - -o /dev/null -X POST localhost:8001/api/v1/auth/login \
    --data-urlencode username=gestor@nordwindsolar.test --data-urlencode password=Demo1234 \
    | awk '$6=="leads_session"{print $7}')
  docker compose exec -T -e SESS="$SESS" lead-core python -c '
  import os, json, base64, urllib.request
  r = urllib.request.urlopen(urllib.request.Request("http://identity:8000/internal/v1/auth/introspect",
      headers={"Cookie": "leads_session=" + os.environ["SESS"]}))
  p = r.headers["X-Internal-Token"].split(".")[1]
  print(json.dumps(json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4))), indent=2))'
  ```

  Tiene que mostrar `iss: identity`, `aud: lead-router`, `sub` (la gestora), `tid` (su
  organización), `role: MANAGER`, `ptype: human` y un `exp` 60 s después de `iat`.

## 3 · Una carga masiva atraviesa tres servicios (5 min)

**Primero se detiene el worker de intake**, para que el mensaje se quede visible en la cola:

```bash
docker compose stop intake-worker
```

En la aplicación, ve a **Carga masiva** y sube `demo/leads-lote-1.csv`.

- **Qué contar:**
  1. La API de intake guarda el fichero, el job y una fila de outbox con canal `job`, todo en una
     transacción, y responde 202.
  2. El relay de `intake-worker` publica esa fila en RabbitMQ.
  3. Ahora el relay está parado, así que el trabajo espera en el outbox: no se pierde.
- **En RabbitMQ:** antes de arrancar el worker, Queues → `intake.jobs` no tiene mensajes, porque el
  relay también vive en el worker.

Arranca el worker:

```bash
docker compose start intake-worker
```

- **En RabbitMQ:** en «Queues», `intake.jobs` muestra el pico en *Message rates* y vuelve a 0 en
  *Ready* y *Unacked*. En «Features» se ve `quorum` y `delivery-limit: 3`, y `intake.jobs.dlq`
  sigue vacía.
- **Qué contar:** el worker parsea el fichero y crea un registro por fila. Por cada registro llama a
  lead-core con `POST /internal/v1/admissions`, usando un token de servicio con `sub=intake` y
  `aud=lead-core`. lead-core decide si descarta, puntúa y asigna, y guarda el lead. Que el mismo
  registro no se admita dos veces lo garantiza `UNIQUE (tenant_id, intake_record_id)`, no una
  transacción compartida.
- **Qué tiene que verse:**
  - El trabajo termina `COMPLETED` con 24 de 24.
  - En el log de `lead-core` hay 24 líneas `POST /internal/v1/admissions … 200`.

## 4 · Los eventos en Kafka (5 min)

Abre Kafka UI (<http://localhost:8004>) y entra en **Topics**.

| Topic | Qué es | Qué mirar |
|---|---|---|
| `internal.identity.agents` · `.tenants` | Estado de agentes y organizaciones, producido por identity-worker | *Settings* → `cleanup.policy=compact`: Kafka guarda el último estado de cada clave (el id) |
| `internal.lead-core.events` | Hechos de lead-core: `LeadAssigned`, `LeadLeftUnassigned`, `LeadReassigned` | *Messages*: el sobre con `event_id`, `event_type`, `producer: lead-core`, `tenant_id`, `correlation_id` y `payload` |
| `internal.intake.events` | `IntakeRejected`, producido por intake | Aparece al subir un fichero con filas malas (`demo/leads-sucios.csv`) |
| `leads.<tenant_id>` | Canal de producto hacia el cliente de cada organización | Un mensaje por lead procesado |
| `internal.dlq.<grupo>` | Mensajes que un consumidor no pudo procesar tras 3 intentos | Tienen que estar vacíos |

En **Consumers**:

| Grupo | Lee | Qué hace |
|---|---|---|
| `lead-core.advisors` | `internal.identity.agents` | Mantiene la proyección `advisors` en `leads_db` |
| `intake.tenants` | `internal.identity.tenants` | Crea las dos fuentes por defecto de cada organización nueva |
| `notifications.lead-events` · `.intake-events` | Los dos topics de hechos | Crea las notificaciones de la bandeja |
| `notifications.members` | `internal.identity.agents` | Mantiene la proyección `members` (quién recibe avisos) |

- **Qué contar:**
  - Ningún servicio escribe en su base y en Kafka por separado. Guarda el cambio y una fila en
    `outbox_events` en la misma transacción.
  - El worker publica esa fila y sólo la marca como publicada cuando Kafka confirma.
  - El consumidor aplica el efecto y anota el `event_id` en `processed_events`, también en una
    transacción, así que un duplicado se ignora. `lead-core.advisors` es la excepción: es
    idempotente por `version` y no escribe en `processed_events`.
- **Qué tiene que verse:**
  - El *Lag* de todos los grupos vuelve a 0.
  - En la aplicación, la campana de notificaciones de un asesor con leads nuevos muestra avisos.

## 5 · Proyecciones: un asesor nuevo llega a todos (3 min)

En la aplicación, como gestora, ve a **Asesores** y crea uno nuevo, asignándole un equipo.

- **Qué contar:**
  1. identity guarda el agente y publica su estado en `internal.identity.agents`.
  2. lead-core lo recibe y lo añade a `advisors`, con el `group_id`, que es un dato propio de
     lead-core.
  3. notifications lo añade a `members`.
  4. Si una asignación llega antes que el evento, lead-core le pide el agente a identity
     (`GET /internal/v1/agents/{id}`).
- **Qué tiene que verse:**
  - En Kafka UI, el mensaje nuevo en `internal.identity.agents`, con la clave igual al id del agente.
  - En la aplicación, el asesor aparece en su equipo con carga 0.

## 6 · Lo que se rompe a propósito (5 min)

**lead-core caído:**

```bash
docker compose stop lead-core
```

Sube `demo/prueba-1-banda-industrial.csv`.

- **Qué tiene que verse:**
  - El trabajo se queda en `PROCESSING`.
  - En RabbitMQ, `intake.jobs` muestra el mensaje en *Unacked*. El worker espera 10 s antes de
    devolverlo a la cola.
  - En el log de `intake-worker`, `left records pending, requeueing`.

```bash
docker compose start lead-core
```

- **Qué tiene que verse:**
  - La siguiente entrega termina el trabajo, sin duplicados.
  - Si el mensaje ya agotó sus tres entregas, aparece en `intake.jobs.dlq`. Se recupera
    reprocesando el trabajo por la API (la interfaz no tiene ese botón):

    ```bash
    curl -s -b "leads_session=$SESS" -X POST localhost:8001/api/v1/intake/jobs/<job_id>/reprocess
    ```

**RabbitMQ caído:**

```bash
docker compose stop rabbitmq
```

Sube otro fichero.

- **Qué tiene que verse:** la API responde 202 y el trabajo espera en el outbox de intake.

```bash
docker compose start rabbitmq
```

- **Qué tiene que verse:** al volver RabbitMQ, el relay publica y el trabajo termina.

**identity caído:**

```bash
docker compose stop identity
```

- **Qué tiene que verse:**
  - Cualquier petición autenticada recibe `503`. El gateway nunca deja pasar una petición sin
    identidad.
  - Al arrancar identity (`docker compose start identity`), todo sigue sin intervención.

## 7 · Seguir una petición de punta a punta (2 min)

Cada petición lleva un `X-Request-Id`. Lo genera el gateway, o respeta el que trae el cliente.

```bash
RID=demo-$(date +%s)
curl -s -o /dev/null -b "leads_session=$SESS" -H "X-Request-Id: $RID" \
  -H 'Content-Type: application/json' -X POST localhost:8001/api/v1/intake/leads/ingest \
  -d '{"first_name":"Ana","last_name":"Demo","email":"ana.demo@x.test","company":"Acme","industry":"Tech","budget":5000}'
sleep 3; docker compose logs gateway intake intake-worker lead-core 2>&1 | grep "$RID"
```

- **Qué tiene que verse:** el mismo id en el gateway (`rid=…`), en la API de intake, en el job de
  `intake-worker` y en la admisión de `lead-core`. En Kafka UI, el `correlation_id` del evento
  `LeadAssigned` coincide.

## 8 · Las cuatro bases, una por servicio (2 min, con DBeaver)

PostgreSQL publica el puerto **5433** en la máquina anfitriona (dentro de la red de Compose es 5432).
En DBeaver: *Nueva conexión → PostgreSQL*.

| Conexión | Host · puerto | Base | Usuario | Contraseña | Para qué |
|---|---|---|---|---|---|
| Superusuario, todas las bases | `localhost` · `5433` | `postgres` | `postgres` | `postgrespassword` | En la pestaña *PostgreSQL* marca **Show all databases**: aparecen `identity_db`, `intake_db`, `leads_db` y `notifications_db` (y las `*_test`) |
| identity | `localhost` · `5433` | `identity_db` | `identity_svc` | `identitypassword` | El rol del servicio |
| intake | `localhost` · `5433` | `intake_db` | `intake_svc` | `intakepassword` | El rol del servicio |
| lead-core | `localhost` · `5433` | `leads_db` | `lead_core_svc` | `leadcorepassword` | El rol del servicio |
| notifications | `localhost` · `5433` | `notifications_db` | `notifications_svc` | `notificationspassword` | El rol del servicio |

Son credenciales de desarrollo, las mismas que fija `docker-compose.yml`.

- **Qué tiene que verse:**
  - Con `lead_core_svc`, `leads_db` tiene sólo las tablas de lead-core: `leads`, reglas,
    `sales_groups`, `advisors`, `webhook_configs` y `outbox_events`.
  - Intentar abrir `identity_db` con `lead_core_svc` falla con *permission denied for database*.
    Cada base sólo la abre su rol.
  - En `outbox_events` de cada base, la columna `published_at` muestra qué se ha publicado ya.
  - En `processed_events` de `notifications_db` e `intake_db` está lo que cada consumidor ya
    procesó.

## 9 · Cierre: cómo se sabe que todo cuadra (1 min)

```bash
docker compose exec intake-worker python -m infrastructure.cli.reconcile   # intake ↔ lead-core: 0 diferencias
./scripts/verify-e2e.sh                                                     # el negocio entero sobre HTTP real
```

`reconcile` compara los registros `PROMOTED` de intake con lo que lead-core dice haber admitido. Sale
con 0 si no hay diferencias. `verify-e2e.sh` recorre el sistema completo, incluida una comprobación
por fase de la separación.
