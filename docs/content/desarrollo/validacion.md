# Validación

Cinco comandos, cada uno demuestra algo que los otros no. Ninguno necesita `--build` ni
`restart` para reflejar un cambio.

```bash
docker compose --profile test run --rm backend-test    # suite completa     ~4 min
cd backend && uv run pytest -m unit -q                 # dominio aislado    ~1 s
./scripts/verify-e2e.sh                                # negocio sobre HTTP ~3 s
./scripts/verify-structure.sh                          # estructura, todo el repo ~1 s
cd bruno && bru run flows --env local -r               # contrato como cliente ~10 s
```

Cada servicio extraído trae su propia suite, con los mismos dos primeros comandos sobre su carpeta
(hoy, notifications; ver [La suite de notifications](#la-suite-de-notifications)):

```bash
docker compose --profile test run --rm notifications-test
cd services/notifications && uv run pytest -m unit -q
```

## Por qué no hace falta reconstruir

El código de `backend/src`, sus tests y las migraciones están montados como volúmenes de sólo
lectura en los contenedores `backend` y `backend-test`, y lo mismo vale para `services/notifications`
y `libs/chassis/src` en `notifications`, `notifications-worker` y `notifications-test` (ver
`docker-compose.yml`). La API además
corre con recarga en caliente (`uvicorn --reload --reload-dir /app/src`, en `backend/Dockerfile`),
así que un cambio guardado se refleja sin reiniciar nada.

Sólo hace falta reconstruir la imagen cuando cambia algo que se instala en tiempo de build:
`pyproject.toml`, `uv.lock` o el propio `Dockerfile`.

```bash
docker compose build backend backend-worker intake-worker backend-test notifications notifications-worker notifications-test
```

## Qué demuestra cada uno

### La suite completa

`docker compose --profile test run --rm backend-test` corre contra una base PostgreSQL real
(`leads_test`, un contenedor aparte de la de desarrollo), no contra un doble en memoria. Es la
única de las tres que ejercita de verdad `backend/src/infrastructure/adapters/output/persistence`.
Cubre los cuatro marcadores de `pyproject.toml`: `unit`, `integration`, `e2e` y `architecture`. Los
tests e2e usan `GatewayClient` (`backend/tests/e2e/gateway_client.py`), un `TestClient` que se comporta
como el gateway: introspecciona la cookie o la `X-Api-Key` contra `/internal/v1/auth/introspect` y
reenvía sólo el bearer resultante, igual que `gateway/nginx.conf`, de modo que ejercitan la misma
frontera de confianza que el stack. Siguen sin servidor HTTP real.

Como la suite no levanta brókeres, `GatewayClient` hace también de `intake-worker`: tras cada petición
reenviada **drena en el propio proceso** el canal `job` a través de `process_job_message`, con las
mismas tres entregas que concede la cola antes de la DLQ. El canal `internal` no se drena: sus filas
quedan sin publicar, porque desde F2 su único consumidor vive en notifications y se prueba en la suite
de ese servicio. Por eso un test e2e ve el lead promovido al terminar su petición, sin esperas. Lo que
ese atajo no ejercita —Kafka, RabbitMQ, los hilos del relay— lo cubre `verify-e2e.sh`.
`test_internal_auth` usa un `TestClient` plano a propósito, porque habla con la app sin gateway.

!!! warning
    `docker compose run` reemplaza el `CMD` de la imagen, no lo extiende. Para correr sólo una
    parte de la suite: `docker compose --profile test run --rm backend-test pytest -q <ruta>`.
    Invocar `backend-test` sin argumentos vuelve a ejecutar `pytest -q`, la suite entera.

### El dominio aislado

`cd backend && uv run pytest -m unit -q` corre sin PostgreSQL —ni falta el contenedor de base de
datos, ni falta Docker— y sin que quien lo ejecuta tenga que exportar ninguna variable de entorno.
`backend/tests/conftest.py` fija `DATABASE_URL`, `MFA_ENCRYPTION_KEY` y `SIGNING_KEYS` una única vez,
con `os.environ.setdefault(...)`, antes de que se importe cualquier módulo de test.

Si `pytest -m unit` empieza a fallar fuera de Docker, es la señal de que se infiltró una
dependencia de infraestructura en el dominio: el marcador existe precisamente para detectar eso.

!!! warning
    Ningún fichero de test debe fijar `DATABASE_URL`, `MFA_ENCRYPTION_KEY` o `SIGNING_KEYS` por su cuenta. Copiar un
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
`/health` antes de que el backend haya migrado, así que `/health` no indica que la API esté lista.

El script se amplía, nunca se reescribe: cada fase de trabajo añade su propia función `verify_fN` y
la llama desde `main`, de modo que las comprobaciones anteriores siguen corriendo y probando que lo
que ya funcionaba sigue funcionando. Las fases del [desacople en microservicios](../microservices/06-plan-de-desacople.md)
usan una `verify_ms_fN` por fase (`verify_ms_f0` es la primera), porque los nombres `verify_fN` ya eran
de planes anteriores.

Desde F1 las notificaciones llegan **de forma asíncrona** (relay, Kafka y consumidor), así que las
comprobaciones que leen el buzón no pueden asumir que el aviso ya está. Dos ayudantes del script lo
resuelven con esperas acotadas: `await_notice` espera, hasta unos 10 s, a que el buzón de una sesión
cumpla una expresión; `await_quiet` espera a que el contador de no leídas deje de moverse, para fijar
una línea base fiable antes de comprobar un «+1». Ninguno decide el resultado: la comprobación que les
sigue sigue siendo la que pasa o falla.

### La durabilidad: `verify_ms_f1`

Que una caída de un bróker retrasa el trabajo sin perderlo sólo se prueba con los brókeres de verdad,
así que vive en el script. Corre justo **antes** de `verify_ms_f0`, que detiene el backend. Comprueba:

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
- **La correlación.** El `X-Request-Id` de la ingesta aparece en los logs de `backend-worker` y en los
  de `intake-worker`.

El límite de 10 MB del `batch-upload` (`413`) ya lo prueba `verify_ms_f0`, y no se repite.

Si la ejecución se interrumpe con RabbitMQ parado, la función lo vuelve a arrancar.

### La bandeja en su servicio: `verify_ms_f2`

Corre antes de `verify_ms_f1`, que rebobina un grupo. Comprueba que la bandeja ya no está en el monolito:

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
- **El monolito ya no la tiene.** `leads_db.notifications` no crece, el backend contesta 404 en
  `/api/v1/notifications` y `backend/src` no menciona notificaciones.

### Los tests de fallo de entrega

Lo que `verify_ms_f1` no puede provocar a voluntad se prueba con la base real y brókeres
sustituidos por dobles:

- **Un relay que publica y muere antes de marcar**
  (`backend/tests/integration/test_delivery_failures.py`). El despachador entrega y `mark_published`
  falla de forma simulada: la siguiente pasada entrega la misma fila otra vez, y la fila queda
  publicada **una sola** vez. Que el consumidor descarte el duplicado lo prueba la suite de
  notifications (`test_the_same_envelope_twice_creates_one_notification`).
- **Un evento cuyo efecto falla siempre**
  (`services/notifications/tests/integration/consumers/test_dead_letter.py`). El `ConsumerLoop` lo
  reintenta tres veces, lo aparca en `internal.dlq.notifications.lead-events` con `attempts=3`,
  confirma el offset, y no quedan ni notificación ni marca en `processed_events`.
- **Un trabajo con un registro que falla** (`backend/tests/integration/test_delivery_failures.py`).
  `process_job_message` devuelve `"nack"`, y la topología que declara `declare_intake_topology`
  conserva `x-delivery-limit: 3` y la DLQ.

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
en la suite. `verify_ms_f0` corre la última, porque detiene y vuelve a arrancar el backend. Comprueba:

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
- Con el backend parado, 503 `SERVICE_UNAVAILABLE` (siempre cerrado), y vuelve al arrancarlo.
- **Todo `location` de `/api/v1/` pasa por la autenticación.** Es una comprobación estática sobre
  `nginx -T`: `nginx -t` es válido, se ven `location /api/v1/…` (un volcado vacío daría cero por la
  razón equivocada) y todos, salvo `/api/v1/auth/`, incluyen `protected.inc` o
  `protected_optional.inc`. Un `location` que se salte el `include` serviría sin autenticar y ninguna
  prueba de petición lo vería.

La comprobación social OAuth ya está integrada. Conserva la API habitual y arranca un backend efímero
en `127.0.0.1` con `APP_ENV=test` y `OAUTH_TEST_MODE=true`; ese único proceso usa un adaptador
determinista y sin red para el callback. Verifica start/PKCE/cookie, el primer enlace y el subject
repetido, el rechazo de correo no verificado, la transición a MFA y el replay. El modo rechaza cualquier
entorno que no sea `test`, no usa credenciales de proveedor y el contenedor temporal se elimina al final.

### La estructura del código

`./scripts/verify-structure.sh` aplica la regla de [ADR-0037](../decisiones/0037-estructura-y-tamano-del-codigo.md)
a cada raíz Python del repositorio —`backend/src`, `backend/tests`, `libs/chassis/src`,
`libs/chassis/tests`, `services/notifications/src`, `services/notifications/tests`, `test-consumer/`,
`demo/` y `tools/`— con `python -m chassis.testing check`, sobre el entorno de `libs/chassis` y sin
Docker. Las fuentes no pasan de 150 líneas por fichero; fuentes y
tests, de 12 ficheros `.py` por carpeta. Lo heredado se compara con su lista base, que sólo encoge;
imprime `ok` por raíz, o lo que falla y por qué, y sale con código distinto de cero si alguna falla.
Ver [Convenciones](convenciones.md#estructura-y-tamano-del-codigo).

## Los cuatro tests de arquitectura

Dentro de la suite completa, `backend/tests/architecture/test_dependency_rule.py` analiza el árbol
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

A su lado, `backend/tests/architecture/test_structure.py` lleva los guardianes de estructura a la
propia suite, con los helpers de `chassis.testing`:

- `test_source_files_and_folders_stay_within_the_limits_or_their_baseline` — `backend/src` contra
  `structure_baseline.py`.
- `test_test_folders_stay_within_the_folder_limit_or_their_baseline` — `backend/tests`, sin límite de
  líneas, contra `tests_structure_baseline.py`.
- `test_domain_tests_import_only_the_domain` — `tests/unit/domain/` sólo importa dominio, stdlib,
  `pytest` y sus propios helpers; un import relativo que sale de la carpeta también falla.

Cada servicio extraído repite los cuatro tests en su propio
`tests/architecture/test_dependency_rule.py`, con `layer_violations` y `stdlib_only_violations` de
`chassis.testing`, y los tres de estructura en `test_structure.py`, sin lista base. `chassis` cuenta
como infraestructura: ni `domain` ni `application` pueden importarlo.

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

## El test de contrato de serialización

`backend/tests/e2e/test_response_contract.py` vigila un defecto que la suite dejó pasar cuatro
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

`libs/chassis` tiene su propia suite, independiente del backend y sin base de datos:

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
