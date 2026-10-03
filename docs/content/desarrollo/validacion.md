# Validación

Cinco comandos, cada uno demuestra algo que los otros no. Ninguno necesita `--build` ni
`restart` para reflejar un cambio.

```bash
docker compose --profile test run --rm lead-core-test  # suite completa     ~4 min
cd services/lead-core && uv run pytest -m unit -q     # dominio aislado    ~1 s
./scripts/verify-e2e.sh                                # negocio sobre HTTP ~3 s
./scripts/verify-structure.sh                          # estructura, todo el repo ~1 s
cd bruno && bru run flows --env local -r               # contrato como cliente ~10 s
```

Los dos primeros son los de lead-core. Cada uno de los otros tres servicios trae su propia suite, con
los mismos dos comandos sobre su carpeta (ver [La suite de notifications](#la-suite-de-notifications),
[La suite de identity](#la-suite-de-identity) y [La suite de intake](#la-suite-de-intake)):

```bash
docker compose --profile test run --rm notifications-test
cd services/notifications && uv run pytest -m unit -q
docker compose --profile test run --rm identity-test
cd services/identity && uv run pytest -m unit -q
docker compose --profile test run --rm intake-test
cd services/intake && uv run pytest -m unit -q
```

## Por qué no hace falta reconstruir

El código de `services/lead-core/src`, sus tests y las migraciones están montados como volúmenes de
sólo lectura en los contenedores `lead-core`, `lead-core-worker` y `lead-core-test`, y lo mismo vale
para `services/notifications`, `services/identity`, `services/intake` y `libs/chassis/src` en sus
contenedores (`notifications`, `notifications-worker`, `notifications-test`, `identity`,
`identity-worker`, `identity-test`, `intake`, `intake-worker`, `intake-test`; ver `docker-compose.yml`).
La API además corre con recarga en caliente (`watchfiles` reinicia Uvicorn al cambiar
`/srv/services/lead-core/src`, en `services/lead-core/Dockerfile`), así que un cambio guardado se refleja
sin reiniciar nada.

Sólo hace falta reconstruir la imagen cuando cambia algo que se instala en tiempo de build:
`pyproject.toml`, `uv.lock` o el propio `Dockerfile`.

```bash
docker compose build lead-core lead-core-worker lead-core-test notifications notifications-worker notifications-test identity identity-worker identity-test intake intake-worker intake-test
```

## Qué demuestra cada uno

### La suite completa

`docker compose --profile test run --rm lead-core-test` corre contra una base PostgreSQL real
(`leads_test`, que crea `db-bootstrap`: el rol `lead_core_svc` no tiene `CREATEDB`), no contra un doble en memoria. Es la
única de las tres que ejercita de verdad `services/lead-core/src/infrastructure/adapters/output/persistence`.
Cubre los cuatro marcadores de `pyproject.toml`: `unit`, `integration`, `e2e` y `architecture`. Los
tests e2e usan `GatewayClient` (`services/lead-core/tests/e2e/helpers/gateway_client.py`), un `TestClient` que hace a la
vez de gateway y de identity: convierte el principal que declara el test en un bearer interno firmado
con una clave de prueba (`tests/tokens.py`, cuya JWKS sustituye a la de identity) y quita siempre
`Authorization`, `X-Api-Key` y `Cookie` del llamante, igual que `gateway/nginx.conf`. Sin principal la
petición llega sin bearer y lead-core responde 401. La hidratación de `AdvisorDirectory` habla con
`IdentityDouble` (`tests/advisors_sync.py`), un mapa en memoria con la forma del contrato de identity.
Siguen sin servidor HTTP real.

La suite no levanta brókeres, y `GatewayClient` no drena ningún outbox: las filas quedan sin publicar,
como con el worker parado. La ingesta no es de este servicio: la decisión de un registro se
prueba aquí a través de `POST /internal/v1/admissions` (con tokens de servicio de prueba:
sin token, de un humano o de otro llamante → 401; `intake` → 200 conforme a `contracts/`; repetir la
admisión da el mismo `lead_id` sin añadir filas al outbox), y el recorrido completo, con un worker
real, lo cubre `verify-e2e.sh`. Lo que el test e2e no ejercita —Kafka, RabbitMQ, los hilos del relay,
el identity de verdad— también.

!!! warning
    `docker compose run` reemplaza el `CMD` de la imagen, no lo extiende. Para correr sólo una
    parte de la suite: `docker compose --profile test run --rm lead-core-test pytest -q <ruta>`.
    Invocar `lead-core-test` sin argumentos vuelve a ejecutar `pytest -q`, la suite entera.

### El dominio aislado

`cd services/lead-core && uv run pytest -m unit -q` corre sin PostgreSQL —ni falta el contenedor de base de
datos, ni falta Docker— y sin que quien lo ejecuta tenga que exportar ninguna variable de entorno.
`services/lead-core/tests/conftest.py` fija `DATABASE_URL`, `JWKS_URL` (ficticia: nunca se descarga) y
`SERVICE_CLIENT_SECRET` una única vez, con `os.environ.setdefault(...)`, antes de que se importe
cualquier módulo de test.

Si `pytest -m unit` empieza a fallar fuera de Docker, es la señal de que se infiltró una
dependencia de infraestructura en el dominio: el marcador existe precisamente para detectar eso.

!!! warning
    Ningún fichero de test debe fijar `DATABASE_URL`, `JWKS_URL` ni ninguna otra variable de `ApiSettings` por su cuenta. Copiar un
    preámbulo `os.environ.setdefault(...)` de otro fichero reintroduce un fallo que depende del
    orden en que pytest importa los módulos: sólo pasa si `conftest.py` ya corrió antes.

### El negocio sobre HTTP real

`./scripts/verify-e2e.sh` no sustituye a pytest: los tests pueden estar en verde con el producto
roto —un router mal cableado en el módulo de dependencias, un contrato que cambió sin que ningún
test lo notara— y este script no. Lanza peticiones HTTP reales contra `http://localhost:8001`
(configurable con la variable de entorno `API`), construye su propio escenario —un administrador de
plataforma, dos organizaciones, varios agentes— y cada entidad lleva un sufijo por ejecución, así
que no necesita una base limpia para dar una respuesta correcta.

```bash
./scripts/verify-e2e.sh            # contra la base actual
./scripts/verify-e2e.sh --reset    # recrea el volumen de PostgreSQL primero
```

`--reset` sólo hace falta cuando una migración lo exige; el día a día no lo necesita. Requiere la
plataforma levantada — ver [Puesta en marcha](puesta-en-marcha.md).

`--reset` espera a que `GET /api/v1/auth/me` responda 401 antes de empezar: el gateway contesta
`/health` antes de que los servicios hayan migrado, así que `/health` no indica que la API esté lista.
Esa ruta la sirve identity; como lead-core no tiene ninguna ruta anónima, después espera a
que el *healthcheck* de `lead-core` diga `healthy`.

Los agentes y las organizaciones llegan a lead-core de forma asíncrona. El
`bootstrap` del script comprueba, tras crear cada organización, que tenga sus dos fuentes
(`await_sources`) y, tras crear cada agente, que aparezca en `GET /advisors` (`await_advisor`). Cada
espera dura hasta 30 s (en un arranque en frío el primer mensaje espera también a que el grupo se
una) y, si se agota, el check falla en vez de dejar que la siguiente comprobación falle por otra
razón.

El script se amplía, nunca se reescribe: cada fase de trabajo añade su propia función `verify_fN` y
la llama desde `main`, de modo que las comprobaciones anteriores siguen corriendo y probando que lo
que ya funcionaba sigue funcionando. Las comprobaciones de la separación en servicios
(ver [Arquitectura de servicios](../microservices/index.md)) usan el prefijo `verify_ms_fN`, porque
los nombres `verify_fN` ya eran de planes anteriores.

Las notificaciones llegan **de forma asíncrona** (relay, Kafka y consumidor), así que las
comprobaciones que leen el buzón no pueden asumir que el aviso ya está. Dos ayudantes del script lo
resuelven con esperas acotadas: `await_notice` espera, hasta unos 10 s, a que el buzón de una sesión
cumpla una expresión; `await_quiet` espera a que el contador de no leídas deje de moverse, para fijar
una línea base fiable antes de comprobar un «+1». Ninguno decide el resultado: la comprobación que les
sigue sigue siendo la que pasa o falla.

### La durabilidad: `verify_ms_f1`

Que una caída de un bróker retrasa el trabajo sin perderlo sólo se prueba con los brókeres de verdad,
así que vive en el script. Corre justo **antes** de `verify_ms_f0`, que detiene lead-core. Comprueba:

- **RabbitMQ caído no pierde trabajo.** Con `rabbitmq` parado, una ingesta responde `202` y el trabajo
  sigue `PENDING` pasados 3 s; al arrancarlo, el trabajo llega a `COMPLETED` en menos de 60 s y el lead
  existe (`GET /leads/{id}` → `200`).
- **La notificación llega por Kafka, sin duplicados.** Se asigna ese lead a un asesor; su
  `GET /notifications` contiene un `LEAD_ASSIGNED` de ese lead en menos de 15 s. Después se para
  `notifications-worker`, se rebobina `notifications.lead-events` al principio y se arranca: el grupo
  relee el topic hasta lag 0 y sigue habiendo **exactamente uno**, porque `processed_events` lo
  descarta.
- **La subida de un fichero** por el camino nuevo (fichero guardado, parseado por el worker) da las
  mismas cifras que antes: una fila buena promovida y una mala rechazada, sin perder ninguna.
- **Los topics y las colas de error.** `internal.identity.agents` e `internal.identity.tenants` tienen
  `cleanup.policy=compact`; las DLQ de los dos grupos de notificaciones existen y están vacías, y también
  `intake.jobs.dlq`.
- **La correlación.** El `X-Request-Id` de la ingesta aparece en los logs de `intake-worker` y en el
  acceso de lead-core a `/internal/v1/admissions`.

El límite de 10 MB del `batch-upload` (`413`) ya lo prueba `verify_ms_f0`, y no se repite.

Si la ejecución se interrumpe con RabbitMQ parado, la función lo vuelve a arrancar.

### La bandeja en su servicio: `verify_ms_f2`

Corre antes de `verify_ms_f1`, que rebobina un grupo. Comprueba que la bandeja no está en lead-core:

- **El enrutado.** `GET /notifications` por el gateway → 200, y el *access log* del gateway muestra
  `upstream=<IP de notifications>:8000` para ese `X-Request-Id`. Se mira el log del gateway porque el
  servicio no escribe una línea por petición.
- **Los avisos los escribe `notifications-worker`.** Un lead asignado a mano llega como `LEAD_ASSIGNED`
  al asesor en menos de 15 s. Se crea una organización, se espera a que su manager esté en
  `members` y un lead que queda `UNASSIGNED` produce `LEAD_LEFT_UNASSIGNED` para ese manager.
- **Marcado y aislamiento.** Marcar una y todas como leídas (204), contador a cero; otra organización
  recibe 404 al marcarla y no la ve en su lista.
- **Los grupos y las DLQ.** Los tres grupos llegan a lag 0 y `internal.dlq.<grupo>` existe y está
  vacía para cada uno.
- **lead-core no la tiene.** `leads_db` no tiene tabla `notifications`, lead-core contesta 404 en
  `/api/v1/notifications` y `services/lead-core/src` no menciona notificaciones.

### La identidad en su servicio: `verify_ms_f3`

Corre después de `verify_ms_f2` y antes de `verify_ms_f1`. Comprueba que la identidad no está en
lead-core y que lead-core sigue enrutando con su proyección:

- **El enrutado.** `GET /auth/me` por el gateway → 200 y el *access log* muestra el `upstream` de
  identity, con el `X-Request-Id` de la petición en el log de identity. lead-core contesta 404 en
  `/api/v1/auth/me`.
- **lead-core no la tiene.** No tiene clave de firma, MFA ni OAuth en su entorno,
  `services/lead-core/src` no menciona MFA, OAuth ni sesiones, e `identity_svc` no puede conectarse a `leads_db`.
- **Grupo sin esperar al evento.** Un asesor recién creado en identity no trae `group_id`;
  `PATCH /advisors/{id}` con un grupo responde 200 al instante (hidratación) y
  `GET /advisors?group_id=` lo devuelve. `PATCH /agents/{id}` con `group_id` → 422, y el asesor de
  otra organización → 404. Como ese `PATCH` puede encontrar ya la proyección, la cadena de
  hidratación se prueba aparte: desde el contenedor `lead-core`, con sus credenciales de servicio, un
  token de `POST /internal/v1/service-tokens` lee el agente en `GET /internal/v1/agents/{agent_id}`
  (200).
- **Desactivar corta.** El asesor entra; tras `DELETE /agents/{id}` su siguiente petición es 401 y
  aparece inactivo en `GET /advisors?is_active=false`.
- **Alta y suspensión de una organización.** Una organización nueva tiene sus dos fuentes en pocos
  segundos y acepta una ingesta que termina `COMPLETED`; al suspenderla, su gestor recibe 401 en
  `/auth/me` y en `/leads`.
- **Los grupos y las DLQ.** `lead-core.advisors`, `intake.tenants` y `notifications.members` llegan a
  lag 0 en menos de 30 s y su `internal.dlq.<grupo>` existe y está vacía; el gestor de la
  organización nueva llega a `members` de notifications.

### La ingesta en su servicio: `verify_ms_f4`

Corre después de `verify_ms_f3` y antes de `verify_ms_f1`. Comprueba que la recepción no está en
lead-core y que lead-core sigue decidiendo por el contrato de admisión:

- **El enrutado.** `GET /sources` por el gateway → 200 y el *access log* muestra el `upstream` de
  intake con el `X-Request-Id` de la petición; lead-core contesta 404 en `/api/v1/sources`;
  `/openapi/intake.json` publica las rutas de `/api/v1/intake`.
- **Las credenciales.** `intake_svc` entra en `intake_db` (control positivo) y no puede conectarse a
  `leads_db` ni a `identity_db`.
- **Una ingesta individual** con una regla de asignación creada para la prueba termina `COMPLETED`,
  su registro `PROMOTED`, el lead `ASSIGNED` al asesor de la regla y visible una sola vez en
  `GET /leads`.
- **Un fichero con tres filas** (válida, con el correo mal formado y descalificada por una regla):
  `total_items/succeeded/failed` = 3/2/1, dos registros `PROMOTED`, uno `REJECTED` por `email`, y la
  descalificada es un lead `DISQUALIFIED`. Reprocesar el trabajo completado no crea leads nuevos.
- **lead-core caído.** Con `lead-core` parado, una ingesta responde `202` y su trabajo no termina; el
  registro sigue `PENDING`. Al arrancarlo, el trabajo termina (por redelivery o, si ya llegó a la DLQ,
  con el reproceso) con su registro `PROMOTED` y un único lead para ese correo.
- **Estadísticas.** `GET /leads/stats` ya no lleva `pending_intake`; `GET /intake/stats` lo trae y
  cuadra con `pending + rejected` y con la bandeja.
- **Reconciliación y consumidores.** `python -m infrastructure.cli.reconcile` sale con 0, e
  `intake.tenants` llega a lag 0 con su `internal.dlq.intake.tenants` vacía.

### El corte de lead-core: `verify_ms_f5`

Corre después de `verify_ms_f4` y antes de `verify_ms_f1`. No comprueba negocio, sólo la estructura
que deja lead-core como servicio:

- **`leads_db` es sólo de lead-core.** Tiene exactamente nueve tablas (`advisors`, `assignment_rules`,
  `disqualification_rules`, `leads`, `outbox_events`, `sales_groups`, `schema_migrations`,
  `scoring_rules` y `webhook_configs`), ninguna de las quince que son de otros servicios o ya no
  existen, y todas son de `lead_core_svc`.
- **Cada rol entra sólo en su base.** `identity_svc`, `intake_svc`, `lead_core_svc` y
  `notifications_svc` entran en la suya (control positivo) y no en las otras tres.
- **Ningún proceso usa el superusuario.** Sin conexiones de `postgres` a `leads_db`; `lead-core` y
  `lead-core-worker` entran como `lead_core_svc`; el worker no tiene `JWKS_URL`, `IDENTITY_URL` ni el
  secreto de servicio, y la API no tiene `KAFKA_BOOTSTRAP_SERVERS`.
- **El gateway enruta a lead-core.** `GET /leads` → 200, con el `upstream` de `lead-core` en el *access
  log* y el `X-Request-Id` en el log de lead-core; `/openapi.json` lleva `/api/v1/leads`.
- **Los cuatro guardianes** de los servicios Python salen 4/4. El quinto servicio, el gateway, es
  nginx y no tiene guardián.
- **La configuración compartida** declara `lead-core` y `lead-core-worker`, y nginx tiene el
  `upstream lead-core`.

### Los tests de fallo de entrega

Lo que `verify_ms_f1` no puede provocar a voluntad se prueba con la base real y brókeres
sustituidos por dobles:

- **Un relay que publica y muere antes de marcar**
  (`services/lead-core/tests/integration/outbox/test_delivery_failures.py`). El despachador entrega y `mark_published`
  falla de forma simulada: la siguiente pasada entrega la misma fila otra vez, y la fila queda
  publicada **una sola** vez. Que el consumidor descarte el duplicado lo prueba la suite de
  notifications (`test_the_same_envelope_twice_creates_one_notification`).
- **Un evento cuyo efecto falla siempre**
  (`services/notifications/tests/integration/consumers/test_dead_letter.py`). El `ConsumerLoop` lo
  reintenta tres veces, lo aparca en `internal.dlq.notifications.lead-events` con `attempts=3`,
  confirma el offset, y no quedan ni notificación ni marca en `processed_events`.
- **Un trabajo interrumpido** (`services/intake/tests/unit/infrastructure/worker/`).
  `process_job_message` devuelve `"nack"`, el `nack` sale sólo tras la espera de 10 s, un trabajo largo
  se liquida por `add_callback_threadsafe` mientras el hilo de la conexión sigue atendiendo eventos
  (el *heartbeat*) y la topología que declara `declare_intake_topology` conserva `x-delivery-limit: 3`
  y la DLQ.

### Mirar las colas de error

Las DLQ vacías son parte de lo que se comprueba, y se pueden mirar a mano con lo mismo que usa el
script:

```bash
# Mensajes en una DLQ de Kafka: suma de los offsets finales de sus particiones
docker compose exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 \
  --topic internal.dlq.notifications.lead-events

# Cola muerta de RabbitMQ
docker compose exec -T rabbitmq rabbitmqctl list_queues name messages
```

Qué hacer con un mensaje que aparezca ahí: [Operar la mensajería](../eventos/operacion.md#las-colas-muertas-y-como-reinyectar-un-mensaje).

### El gateway: `verify_ms_f0`

Lo que el borde garantiza sólo se puede probar contra el nginx real, y por eso vive en el script y no
en la suite. `verify_ms_f0` corre la última, porque detiene y vuelve a arrancar identity y después
lead-core. Comprueba:

- Un bearer basura o un JWT firmado con otra clave → 401, por el gateway y directo al servicio; el
  `Authorization` del cliente nunca llega al servicio.
- `/internal/*` no se publica; `X-Request-Id` se conserva, se genera o se sustituye, y llega al access
  log.
- **Los casos de `Origin` y CORS**, que antes estaban en `test_origin_protection.py`: preflight de un
  origen permitido, un dominio parecido (`http://localhost:5173.evil.test`) → 403, un `Origin` hostil no
  crea sesión, un `Referer` hostil sin `Origin` no cuenta y `X-Api-Key` con `Origin` hostil → 403 antes
  de autenticar.
- `X-Api-Key` válida sólo en `GET /leads`; `POST /agents` anónimo con agentes ya creados → 401; un
  cuerpo de más de 10 MB → 413.
- Con identity parado, 503 `SERVICE_UNAVAILABLE` (siempre cerrado), y vuelve al arrancarlo. Lo
  mismo con `lead-core` parado: el gateway responde 503 con el sobre y la API vuelve al arrancarla.
- **Todo `location` de `/api/v1/` pasa por la autenticación.** Es una comprobación estática sobre
  `nginx -T`: `nginx -t` es válido, se ven `location /api/v1/…` (un volcado vacío daría cero por la
  razón equivocada) y todos, salvo `/api/v1/auth/`, incluyen `protected.inc` o
  `protected_optional.inc`. Un `location` que se salte el `include` serviría sin autenticar y ninguna
  prueba de petición lo vería.

La comprobación social OAuth ya está integrada. Conserva la API habitual y arranca un identity efímero
en `127.0.0.1` con `APP_ENV=test` y `OAUTH_TEST_MODE=true`; ese único proceso usa un adaptador
determinista y sin red para el callback. Verifica start/PKCE/cookie, el primer enlace y el subject
repetido, el rechazo de correo no verificado, la transición a MFA y el replay. El modo rechaza cualquier
entorno que no sea `test`, no usa credenciales de proveedor y el contenedor temporal se elimina al final.

### La estructura del código

`./scripts/verify-structure.sh` aplica la regla de [ADR-0037](../decisiones/0037-estructura-y-tamano-del-codigo.md)
a cada raíz Python del repositorio —`libs/chassis/src`, `libs/chassis/tests`, `services/lead-core/src`,
`services/lead-core/tests`, `services/notifications/src`, `services/notifications/tests`,
`services/identity/src`, `services/identity/tests`, `services/intake/src`, `services/intake/tests`,
`test-consumer/` y `tools/`— con `python -m chassis.testing check`, sobre el entorno de `libs/chassis` y sin
Docker. Las fuentes no pasan de 150 líneas por fichero; fuentes y
tests, de 12 ficheros `.py` por carpeta. Sólo `test-consumer/` se compara con una lista base,
que sólo encoge; las demás raíces, incluidas las de lead-core, no tienen. Imprime `ok` por raíz, o lo que
falla y por qué, y sale con código distinto de cero si alguna falla (o si una raíz declarada no existe).
Ver [Convenciones](convenciones.md#estructura-y-tamano-del-codigo).

## Los cuatro tests de arquitectura

Dentro de la suite de cada servicio, `tests/architecture/test_dependency_rule.py` (en lead-core, `services/lead-core/tests/architecture/`) analiza el árbol
de imports de cada módulo (AST, sin ejecutar el código) y falla si alguna capa cruza una frontera
que no le corresponde:

- `test_domain_does_not_import_outer_layers` — el dominio no importa `application` ni
  `infrastructure`.
- `test_application_does_not_import_infrastructure` — la aplicación no importa `infrastructure`.
- `test_domain_does_not_import_third_party_frameworks` — el dominio no importa nada fuera de la
  biblioteca estándar.
- `test_application_does_not_import_infrastructure_libraries` — la aplicación no importa ningún framework
  web, ni psycopg, ni un cliente de mensajería: llega a todos por un puerto.

Deben estar siempre 4/4. Si uno falla, algo cruzó una frontera que la arquitectura hexagonal existe
para impedir — ver [Arquitectura](../arquitectura/index.md) y
[ADR-0001](../decisiones/0001-arquitectura-hexagonal.md).

A su lado, `tests/architecture/test_structure.py` lleva los guardianes de estructura a la propia suite,
con los helpers de `chassis.testing`, sin lista base:

- `test_source_files_and_folders_stay_within_the_limits` — `src/`, con el límite de líneas y de
  ficheros por carpeta.
- `test_test_folders_stay_within_the_folder_limit` — `tests/`, sin límite de líneas.
- `test_domain_tests_import_only_the_domain` — `tests/unit/domain/` sólo importa dominio, stdlib,
  `pytest` y sus propios helpers; un import relativo que sale de la carpeta también falla.

Los cuatro servicios los repiten con `layer_violations` y `stdlib_only_violations` de
`chassis.testing`. `chassis` cuenta como infraestructura: ni `domain` ni `application` pueden importarlo.

## La suite de notifications

`docker compose --profile test run --rm notifications-test` corre contra `notifications_test`, que crea
`db-bootstrap` (el rol del servicio no tiene `CREATEDB`). `cd services/notifications && uv run pytest
-m unit -q` corre sin base ni variables de entorno; `tests/conftest.py` fija `DATABASE_URL`,
`JWKS_URL` y `KAFKA_BOOTSTRAP_SERVERS` una sola vez, y ningún test lo repite. Los marcadores salen de
la carpeta (`unit`, `integration`, `e2e`, `architecture`):

| Carpeta | Qué cubre |
|---|---|
| `tests/unit/` | Dominio, casos de uso con dobles, `groups.py` y `Settings` |
| `tests/integration/persistence/` | Repositorios y unidad de trabajo sobre PostgreSQL |
| `tests/integration/consumers/` | `NotificationConsumer`, `MemberConsumer` y la DLQ, con la base real |
| `tests/e2e/` | La API con tokens firmados y una JWKS de prueba |
| `tests/architecture/` | Los cuatro guardianes y la estructura |

## La suite de identity

`docker compose --profile test run --rm identity-test` corre contra `identity_test`, que también crea
`db-bootstrap`. `cd services/identity && uv run pytest -m unit -q` corre sin base ni variables de
entorno; `tests/conftest.py` fija `DATABASE_URL`, `SIGNING_KEYS`, `MFA_ENCRYPTION_KEY` y
`SERVICE_CLIENTS` una sola vez, con los valores de prueba de `tests/environment.py`. Mismos marcadores
por carpeta:

| Carpeta | Qué cubre |
|---|---|
| `tests/unit/` | Dominio, casos de uso con dobles, `ApiSettings`/`WorkerSettings`, `SERVICE_CLIENTS` y los tokens |
| `tests/integration/` | Migraciones, repositorios, `bcrypt`, `sync_tenants` y `publish_identity_snapshot` sobre PostgreSQL |
| `tests/e2e/` | Auth, MFA, OAuth, tenants, agentes y las rutas internas, con su propio `GatewayClient`; los eventos del outbox contra `contracts/` |
| `tests/architecture/` | Los cuatro guardianes y la estructura |

Los tests de contrato (`chassis.testing.contracts`) comprueban en los dos lados que lo que identity
produce —sus eventos, el agente de `GET /internal/v1/agents/{agent_id}`, el token de servicio—
conforma `contracts/`, y que lead-core sabe leer sus fixtures. `contracts/` se monta de sólo lectura
en `/srv/contracts` en los cuatro servicios.

## La suite de intake

`docker compose --profile test run --rm intake-test` corre contra `intake_test`, que también crea
`db-bootstrap`. `cd services/intake && uv run pytest -m unit -q` corre sin base ni variables de
entorno; `tests/conftest.py` fija el entorno una sola vez. Mismos marcadores por carpeta:

| Carpeta | Qué cubre |
|---|---|
| `tests/unit/` | Dominio, casos de uso con un `LeadAdmissionPort` falso, `ApiSettings`/`WorkerSettings`/`ReconcileSettings`, el consumidor de jobs, los relays y la reconciliación |
| `tests/integration/` | Migraciones (reaplicables, sin FK hacia `tenants` ni `leads`), repositorios, el reclamo concurrente de un registro, el consumidor `intake.tenants` y las consultas de la reconciliación, sobre PostgreSQL |
| `tests/e2e/` | La API pública con tokens firmados, un lead-core falso (`fake_lead_core.py`) y el trabajo procesado en proceso: fuentes, bandeja, trabajos, `batch-upload` (incluido el `413`), `GET /intake/stats` y el aislamiento entre organizaciones |
| `tests/architecture/` | Los cuatro guardianes y la estructura |

Los tests de contrato comprueban que lo que intake envía conforma `contracts/schemas/lead-core/admission-request.v1`, que
sabe leer los fixtures de resultado (`ADMITTED`, `REJECTED`) y de consulta, que el mensaje de
`intake.jobs` conforma `contracts/schemas/intake/job-message.v1` y que `IntakeRejected` conforma su
esquema de evento. El lado de lead-core (`lead-core-test`) comprueba que sus respuestas conforman los
mismos esquemas. Un 401 invalida el token de servicio en caché (`invalidate()`), y un 5xx, un
*timeout* o un cuerpo inválido son `AdmissionUnavailable`.

## El test de contrato de serialización

`services/lead-core/tests/e2e/system/test_response_contract.py` vigila un defecto que la suite dejó pasar cuatro
veces: **un campo nuevo llega hasta el borde de la API y el adaptador de salida lo descarta**. El
correo del lead se serializó como la cadena `"None"`; el identificador del origen, el del registro
de entrada y el motivo de descalificación se quedaron fuera de su respuesta. Ninguno lo detectó una
prueba: el primero apareció en el harness de negocio y el último, escribiendo otro test.

El resto de pruebas afirma sobre los campos que le interesan, así que sigue en verde aunque el
adaptador tire otros ocho. Ésta afirma sobre todos a la vez, con dos comprobaciones por entidad:

- **Nada de lo enviado vuelve vacío.** Se crea el recurso con valor en cada campo opcional, se
  relee, y se compara campo a campo.
- **Ningún campo del esquema queda sin rellenar.** Se recorren los campos declarados en el modelo
  Pydantic y se exige que ninguno vuelva `None`.

Añade además una garantía transversal: ningún cuerpo de respuesta contiene `hashed_password`,
`secret_hash` ni `password`.

!!! warning "Cuando este test falle, el arreglo está en el router"
    Los campos que legítimamente pueden volver vacíos viven en `NULLABLE_BY_DESIGN`, **cada uno con
    su razón escrita al lado**: estados del ciclo de vida que son mutuamente excluyentes, un
    `lead_id` que sólo existe si el registro llegó a promoverse. Cada uno de ésos se ejercita
    aparte, en un test que provoca su transición, para que la exención no se convierta en un hueco
    de cobertura.

    Si un campo empieza a volver `None` y no está en esa tabla, el test falla a propósito. **La
    corrección es rellenarlo en el router, no añadir una línea a `NULLABLE_BY_DESIGN`.** Ampliar la
    tabla para silenciar el fallo reintroduce exactamente el defecto que este test existe para
    impedir, y es tanto más tentador cuanto que el frontend genera sus tipos desde este contrato:
    un campo declarado en el esquema y nunca rellenado compila en TypeScript y llega `undefined` al
    navegador.

## La librería `chassis`

`libs/chassis` tiene su propia suite, independiente de los servicios y sin base de datos:

```bash
cd libs/chassis && uv run pytest -q -W error
```

Incluye `test_structure.py`: chassis cumple la regla de estructura sin lista base.

## La colección de Bruno

`bruno/` vuelve a ser una validación fiable. Necesita el stack levantado y la CLI de Bruno en la
máquina (`npm install -g @usebruno/cli@3.1`: el manejo de cookies que asume está comprobado en esa versión), y se corre desde su carpeta:

```bash
cd bruno && bru run flows --env local -r                 # los seis flujos     ~10 s
```

Los seis flujos recorren el contrato tal como lo ve un cliente, siempre a través del gateway: la
sesión por cookie y su revocación al desactivar a alguien, los dos planos de rol, el `404` en vez de
`403` entre organizaciones, la ingesta que responde `202` y se sondea hasta un estado terminal, y los
avisos que llegan, por Kafka, a quien deben. Es más estrecho que `verify-e2e.sh`, pero cada paso está
documentado en su bloque `docs` y sirve de guion legible del producto. Cada flujo crea sus datos con
su propio sello, así que no necesita una base limpia ni rompe lo que `verify-e2e.sh` comprueba.

La colección se autentica como un navegador: cada login guarda su cookie `leads_session` en la
variable de su rol y cada petición la manda en la cabecera `Cookie`. Bruno mezcla su tarro de cookies
por dominio por encima de esa cabecera, y una sesión pisaría a las demás; el `script:post-response`
de `bruno/collection.bru` vacía el tarro tras cada respuesta para que eso no pase.

Las carpetas de referencia (`auth`, `tenants`, `leads`…) no forman parte de la validación: dependen de
variables que siembran los flujos y algunas mutan entidades que el flujo ya dejó en su estado final.
`bru run --env local -r` sobre la colección entera, por eso, no sale en verde; cómo encadenar cada
carpeta con su flujo está en `bruno/README.md`.

## La limpieza entre pruebas

Cada test de integración o end-to-end trunca las tablas antes de correr. La lista de tablas no está
escrita a mano: se lee de `pg_tables` en el momento de la ejecución, así que una tabla nueva se
limpia sola y no hace falta acordarse de añadirla a ningún sitio.

## Ver también

- [Convenciones](convenciones.md)
- [Cómo contribuir](contribuir.md) — cuándo correr cada comando antes de proponer un cambio.
