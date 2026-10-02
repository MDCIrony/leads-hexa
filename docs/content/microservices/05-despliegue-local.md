# 05 · Despliegue local

Todo sigue levantándose con Docker Compose. Kubernetes no reduce la latencia entre servicios ni es
requisito para que una arquitectura sea de microservicios; el diseño queda preparado para llevarlo
ahí sin cambios (ver [Evoluciones y riesgos](07-evoluciones-y-riesgos.md)).

## Topología

```mermaid
flowchart TB
    subgraph host["Puertos del host"]
        P80[":80 frontend"]
        P8001[":8001 gateway"]
        P8002[":8002 docs"]
        P5433[":5433 db"]
        P15672[":15672 rabbitmq"]
        P8004[":8004 kafka-ui"]
        P9094[":9094 kafka (SASL)"]
    end

    P80 --> FE["frontend"]
    FE --> GW["gateway"]
    P8001 --> GW
    GW --> ID["identity"]
    GW --> IN["intake"]
    GW --> LC["lead-core"]
    GW --> NO["notifications"]

    IDW["identity-worker"]
    INW["intake-worker"]
    LCW["lead-core-worker"]
    NOW["notifications-worker"]

    ID & IDW & IN & INW & LC & LCW & NO & NOW --> DB[("db")]
    BOOT["db-bootstrap<br/>una ejecución"] --> DB
    IN & INW --> RMQ["rabbitmq"]
    IDW & INW & LCW & NOW --> K["kafka"]
```

| Servicio de Compose | Imagen | Comando | Puerto en el host |
|---|---|---|---|
| `gateway` | nginx | — | **8001** |
| `frontend` | la actual | — | 80 |
| `identity`, `identity-worker` | `services/identity` | `api` / `worker` | — |
| `intake`, `intake-worker` | `services/intake` | `api` / `worker` | — |
| `lead-core`, `lead-core-worker` | `backend` | `api` / `worker` | — |
| `notifications`, `notifications-worker` | `services/notifications` | `api` / `worker` | — |
| `db-bootstrap` | postgres | script idempotente | — |
| `db`, `rabbitmq`, `kafka`, `kafka-ui`, `docs` | las actuales | — | las actuales |
| `test-consumer` (perfil `demo`) | la actual | — | 8003 |

Sólo el gateway publica la API. Los servicios no tienen puerto en el host: para depurar uno se entra
por el gateway, igual que el frontend. `test-consumer` cambia `LEADS_API_BASE` a
`http://gateway:8080/api/v1`.

El gateway **no declara `depends_on`**. Sus `upstream` usan `resolve` con el DNS de Docker
(`resolver 127.0.0.11 valid=10s`, nginx 1.27.3 o posterior), así que arranca sin que sus servicios
existan y sigue funcionando si uno se recrea con otra IP. El nginx del frontend hace lo mismo con el
gateway.

El directorio `gateway/` se monta **entero** en `/etc/nginx/conf.d`, no fichero a fichero: un montaje
de un solo fichero fija el *inode*, y un editor que reemplaza el fichero dejaba el contenedor con la
configuración vieja. La imagen sólo carga `*.conf` (`nginx.conf`); los `*.inc` son fragmentos que se
incluyen (`proxy_headers.inc`, `introspect.inc`, `protected.inc`, `protected_optional.inc`; ver
[03](03-gateway-y-autenticacion.md#includes-compartidos)). Tras editar cualquiera de ellos basta
`docker compose exec gateway nginx -s reload`.

## Bases de datos

Un único contenedor PostgreSQL con una base y un rol por servicio. *Database per service* exige
propiedad lógica, no cuatro servidores.

| Base | Rol | Servicio | Test |
|---|---|---|---|
| `identity_db` | `identity_svc` | identity | `identity_test` |
| `intake_db` | `intake_svc` | intake | `intake_test` |
| `leads_db` | `lead_core_svc` | lead-core | `leads_test` |
| `notifications_db` | `notifications_svc` | notifications | `notifications_test` |

Cada rol tiene `CONNECT` y propiedad sobre su base y sobre ninguna otra; `REVOKE CONNECT … FROM PUBLIC`
en todas. Un servicio que intentara leer otra base fallaría al conectar, no al revisar un diff.

**Las crea `db-bootstrap`**, un servicio de una sola ejecución con un script `psql` idempotente
(`db/bootstrap.sql`), del que dependen los servicios con `condition: service_completed_successfully`.
Hoy crea, para notifications, el rol `notifications_svc` (con la contraseña de desarrollo que le pasa
Compose), las bases `notifications_db` y `notifications_test` con ese rol de propietario, y aplica
`REVOKE CONNECT … FROM PUBLIC` y `GRANT CONNECT` sólo al rol. La base de pruebas la crea él porque el
rol no tiene `CREATEDB`. Cada fase que extrae un servicio añade el suyo al script. No sirve
`/docker-entrypoint-initdb.d`: sólo se ejecuta con el volumen vacío, y el volumen `pgdata` actual ya
tiene datos. `CREATE DATABASE` no admite `IF NOT EXISTS`, así que el script usa el patrón:

```sql
SELECT format('CREATE DATABASE %I OWNER notifications_svc', name)
FROM (VALUES ('notifications_db'), ('notifications_test')) AS databases (name)
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = name)
\gexec
```

Las migraciones siguen siendo de cada servicio y se aplican al arrancar su proceso `api`, como hoy.

## Imágenes

- **Contexto de construcción: el directorio del servicio, más un contexto con nombre para
  `libs/chassis`**, con un `Dockerfile` por servicio (`additional_contexts: chassis: ./libs/chassis`
  en Compose; `COPY --from=chassis` en el `Dockerfile`). No se usa la raíz del repo como contexto.
  Cada imagen contiene **sólo** su servicio y `libs/chassis`; ningún otro servicio está dentro. Que un
  servicio importe código de otro no es una regla que revisar: no compila. BuildKit respeta el
  `.dockerignore` de `libs/chassis` para ese contexto con nombre.
- **Disposición en la imagen: `/srv/services/<svc>` y `/srv/libs/chassis`.** Replica la del
  repositorio porque `uv.lock` registra `chassis` como `../../libs/chassis`. El proyecto es *virtual*
  (sin `build-system`): `uv sync --no-install-project` instala las dependencias y `src/` se importa
  por `PYTHONPATH`.
- **Proyecto `uv` independiente por servicio** con su `uv.lock`, y `chassis` como dependencia por
  ruta (`chassis = { path = "../../libs/chassis", editable = true }`). Cambiar `chassis` obliga a
  reconstruir las imágenes que lo usan; es el precio de que la verificación del token sea idéntica en
  todas.
- **Mismas etapas en todos:** `runner`, `dev` (con `watchfiles`) y `test`, como el `Dockerfile` actual
  del backend.

## Recarga en caliente

Igual que hoy: `src/` y `migrations/` del servicio, más `libs/chassis/src`, montados en sólo lectura.
`api` corre con `uvicorn --reload`; `worker` con `watchfiles`. Un cambio de código no necesita
`--build` ni `restart`; sólo se reconstruye si cambian `pyproject.toml`, `uv.lock` o un `Dockerfile`.

## Configuración por servicio

| Variable | identity | intake | lead-core | notifications |
|---|:-:|:-:|:-:|:-:|
| `DATABASE_URL` (su base, su rol) | ✓ | ✓ | ✓ | ✓ |
| `SIGNING_KEYS` (`kid=<semilla Ed25519 en base64url>[,kid=…]`; la primera firma, todas se publican) | ✓ | | | |
| `SERVICE_CLIENTS` (hashes y audiencias) | ✓ | | | |
| `MFA_ENCRYPTION_KEY`, `GOOGLE_*`, `GITHUB_*`, `FRONTEND_ORIGIN` | ✓ | | | |
| `JWKS_URL` (`http://backend:8000/internal/v1/jwks` mientras identity no esté extraído) | | ✓ | ✓ | ✓ |
| `SERVICE_CLIENT_ID`, `SERVICE_CLIENT_SECRET` | | ✓ | ✓ | |
| `LEAD_CORE_URL` | | ✓ | | |
| `IDENTITY_URL` | | | ✓ | |
| `KAFKA_BOOTSTRAP_SERVERS` | ✓ | ✓ | ✓ | ✓ |
| `KAFKA_EXTERNAL_BOOTSTRAP_SERVERS` | ✓ | | | |
| `RABBITMQ_URL` | | ✓ | | |
| `LOG_LEVEL` (`INFO` por defecto) | | | | ✓ |

Los valores de desarrollo viven en `docker-compose.yml`, como hoy viven `MFA_ENCRYPTION_KEY` y las
contraseñas de los brokers. Los secretos de OAuth siguen leyéndose de `.env`.

## Arranque y dependencias

| Servicio | Espera a | Por qué |
|---|---|---|
| servicios de aplicación | `db` sano y, para los extraídos, `db-bootstrap` completado | Sin su base no hay nada que hacer. Hoy sólo `notifications` y `notifications-test` dependen de `db-bootstrap`; cada servicio que se extraiga lo hará también |
| `intake-worker` | `rabbitmq` sano | Su razón de ser es la cola (igual que hoy) |
| `notifications-worker` | `notifications` sano | La API aplica las migraciones al arrancar y los consumidores escriben esas tablas |
| `*-worker` y `api` | **no** esperan a Kafka | Los relays reintentan solos; la API sirve aunque el broker no esté (ADR-0026) |
| `gateway` | nada | Re-resuelve sus `upstream` en ejecución (`resolve`); responde `/health` aunque el servicio aún no exista |
| `frontend` | `gateway` sano | El `healthcheck` del gateway es su propio `GET /health` |

## Tests

| Comando | Qué demuestra |
|---|---|
| `docker compose --profile test run --rm <svc>-test` | La suite completa de un servicio, con su base `*_test` (hoy `notifications-test`; el backend usa `backend-test`) |
| `cd services/<svc> && uv run pytest -m unit -q` | El dominio aislado: **sin base y sin variables de entorno**, como hoy |
| `./scripts/verify-e2e.sh` | El negocio de punta a punta sobre HTTP real, contra el gateway en `:8001` |

`verify-e2e.sh` no cambia de destino ni se reescribe: cada fase de este desacople añade su
`verify_ms_fN` (una por fase; los nombres `verify_fN` ya son de planes anteriores) y la llama desde
`main`. `verify_ms_f0` va la última porque detiene y arranca el backend.

Con `--reset` recrea el volumen y espera a que `/api/v1/auth/me` responda 401: el gateway contesta
`/health` antes de que el backend haya migrado, así que `/health` no vale como señal de «listo».

Cada servicio lleva sus cuatro tests de guardián, y el de lead-core sigue siendo el del backend
actual.

## Estados intermedios

El Compose crece una fase cada vez; en ningún momento conviven dos versiones del mismo contexto
sirviendo tráfico.

| Tras | Servicios de aplicación |
|---|---|
| F0 | `gateway`, `backend` (monolito), `intake-worker` |
| F1 | + `backend-worker` (relay y consumidores) |
| F2 | + `notifications`, `notifications-worker`, `db-bootstrap`; `backend-worker` conserva los relays y deja de consumir |
| F3 | + `identity`, `identity-worker` |
| F4 | + `intake` (el `intake-worker` pasa a ser suyo) |
| F5 | `backend` → `lead-core`, `backend-worker` → `lead-core-worker` |
