# Puesta en marcha

De cero a un lead ingerido: requisitos, arranque, el primer usuario, la primera organización y la
primera ingesta. Todos los comandos son `curl` reales, verificados contra el código.

## Requisitos

Docker y el plugin `docker compose`. Nada más: las variables de entorno de cada servicio están
fijadas en `docker-compose.yml` para desarrollo local, así que no hace falta crear ningún `.env`.

## Arrancar la plataforma

```bash
docker compose up -d
```

Levanta `db` (PostgreSQL 16), `lead-core` (la API, que aplica las migraciones pendientes al arrancar y
recarga en caliente lo que cambie en `services/lead-core/src`), `gateway` (nginx, la única entrada de la API),
`frontend` (nginx sirviendo la interfaz) y `docs` (este sitio), más `rabbitmq`, `kafka`, `kafka-ui`,
`lead-core-worker` (la entrega: los relays del outbox, y la proyección de asesores), el servicio de
recepción —`intake` (fuentes, trabajos y registros; aplica sus migraciones al arrancar) e
`intake-worker` (relays, `intake.jobs` y las fuentes por defecto de cada organización)—, el servicio de identidad —`identity` (autenticación, organizaciones y agentes; aplica
sus migraciones al arrancar) e `identity-worker` (publica sus eventos)— y el de notificaciones:
`notifications` (su API; aplica sus migraciones al arrancar) y `notifications-worker` (sus consumidores
de Kafka). Un servicio de una sola ejecución, `db-bootstrap`, crea antes los roles y las bases de
`lead-core`, `identity`, `intake` y `notifications`. `lead-core` espera a que `db` esté sano; `gateway` no espera a
nadie (vuelve a resolver `lead-core`, `identity`, `intake` y `notifications` por DNS); `frontend` espera a que `gateway`
esté sano.

Puertos reales en el host:

| Servicio | Puerto | Por qué no el estándar |
|---|---|---|
| API (`gateway`) | `8001` | `8000` es un puerto común y suele estar ocupado |
| Base de datos | `5433` | `5432` es el puerto por defecto de un PostgreSQL local |
| Interfaz web | `80` | — |
| Documentación | `8002` | `8001` es el gateway, y `8000` es un puerto común que suele estar ocupado |

Dentro de la red de `compose` cada servicio sigue escuchando en su puerto estándar (el gateway en
`8080`, `lead-core` en `8000`, la base en `5432`); el remapeo sólo afecta a cómo se les llega desde el
host. **`lead-core` no publica ningún puerto**: la API sólo es alcanzable por el gateway en `8001`, y
`8001` es el gateway, no lead-core. Para depurar con lead-core directamente hay que entrar
en el contenedor (`docker compose exec lead-core …`).

El directorio `gateway/` (`nginx.conf` y los `*.inc` que incluye: `proxy_headers.inc`,
`introspect.inc`, `protected.inc` y `protected_optional.inc`) está montado entero como volumen. Tras
editar cualquiera de ellos no hace falta reconstruir nada, sólo recargar nginx:

```bash
docker compose exec gateway nginx -s reload
```

Comprueba que la API responde:

```bash
curl http://localhost:8001/health
```

```json
{"status": "ok"}
```

## El primer usuario: la regla de bootstrap

`POST /api/v1/agents` no exige credencial mientras la tabla de agentes esté vacía. Ese primer
agente nace siempre con rol `ADMIN`, sin importar qué `role` traiga el cuerpo de la petición: es el
único punto de entrada del plano de plataforma, y no hay otro camino en la API para crear un
segundo `ADMIN`.

```bash
curl -s -X POST http://localhost:8001/api/v1/agents \
  -H 'Content-Type: application/json' \
  -d '{"name":"Root","email":"root@plat.test","password":"Secret123","role":"ADMIN"}'
```

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "Root",
  "email": "root@plat.test",
  "is_active": true,
  "role": "ADMIN",
  "tenant_id": null
}
```

`tenant_id` es `null`: un `ADMIN` no pertenece a ninguna organización y no accede a dato operativo
de ninguna — ver [API · Errores](api-errores.md).

!!! tip
    Este paso sólo funciona una vez. En cuanto existe un agente, la misma llamada exige token
    (`401 Unauthorized` sin él) y ya no acepta crear otro `ADMIN`. Si el volumen de PostgreSQL ya
    tiene datos de una sesión anterior, este `curl` devuelve `401` en vez de `201` — no es un fallo,
    es la regla haciendo su trabajo.

## Autenticarse

`POST /api/v1/auth/login` recibe las credenciales como formulario
(`application/x-www-form-urlencoded`), no como JSON: es el esquema estándar
`OAuth2PasswordRequestForm` de FastAPI.

```bash
curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -d 'username=root@plat.test&password=Secret123'
```

```json
{"status": "AUTHENTICATED"}
```

La respuesta fija la cookie HttpOnly `leads_session`. Si la cuenta tiene MFA activo devuelve
`{"status":"MFA_REQUIRED"}` y hay que verificar el código en `/api/v1/auth/mfa/verify` antes de
continuar.

## Activar OAuth localmente

OAuth de Google y GitHub está desactivado hasta configurar por completo cada proveedor. En un `.env`
local no versionado, usa credenciales de desarrollo y registra exactamente las URLs de callback:

```dotenv
FRONTEND_ORIGIN=http://localhost
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8001/api/v1/auth/oauth/google/callback
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
GITHUB_REDIRECT_URI=http://localhost:8001/api/v1/auth/oauth/github/callback
```

`FRONTEND_ORIGIN` debe estar incluido exactamente en `CORS_ORIGINS` (identity sólo usa esa lista para esta validación). Los orígenes que el navegador puede usar los decide el `map $http_origin` de `gateway/nginx.conf`: cambiar uno obliga a tocar los dos sitios. Al completar las tres variables
de un proveedor aparece su botón en el login; sólo permite entrar a agentes humanos ya existentes con
correo de proveedor verificado. La vuelta conserva PKCE y, si MFA está activo, continúa en `/mfa`.
No hay auto-registro: crea antes el `Agent` activo de prueba con el mismo correo. `SESSION_COOKIE_SECURE=false`
sirve sólo para este localhost HTTP; en cualquier entorno HTTPS debe ser `true`.

Para una demostración manual, registra las dos callback exactas de arriba en Google Cloud y GitHub,
abre `http://localhost/login`, inicia con la cuenta de prueba y comprueba `GET /api/v1/auth/me` tras
la vuelta. Repite la entrada para comprobar el subject enlazado; una cuenta sin `Agent` o sin correo
verificado vuelve al login sin sesión. Activa MFA en ese `Agent` para comprobar la transición a `/mfa`.
Borra las cookies entre intentos y no copies credenciales, códigos, tokens ni secretos a documentación,
capturas o commits: viven exclusivamente en el `.env` local no versionado.

Para encadenar comandos, conserva las cookies con un jar:

```bash
curl -c /tmp/leads.cookies -s -X POST http://localhost:8001/api/v1/auth/login \
  -d 'username=root@plat.test&password=Secret123'
```

## Crear una organización y su gestor

Sólo un `ADMIN` puede crear organizaciones, y las crea junto con su primer gestor (`MANAGER`) en
una sola transacción: si el correo del gestor ya existe, la organización tampoco se crea.

```bash
curl -s -X POST http://localhost:8001/api/v1/tenants \
  -b /tmp/leads.cookies \
  -H 'Content-Type: application/json' \
  -d '{"name":"Acme Corp","manager":{"name":"Ana Ruiz","email":"ana@acme.test","password":"Secret123"}}'
```

```json
{
  "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "is_active": true,
  "created_at": "2026-08-07T10:00:00+00:00",
  "agent_count": null,
  "manager": {
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "Ana Ruiz",
    "email": "ana@acme.test",
    "is_active": true,
    "role": "MANAGER",
    "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
  }
}
```

La organización recibe además dos orígenes de leads (`LeadSource`), `MANUAL_FORM` y `FILE_UPLOAD`,
unos segundos después: identity publica la organización nueva e intake los crea al recibirla. Sin
uno de ellos activo, la ingesta de la siguiente sección respondería `404 SOURCE_NOT_FOUND`;
`GET /api/v1/sources` como gestor muestra cuándo están.

## Autenticarse como gestor

```bash
curl -c /tmp/leads.cookies -s -X POST http://localhost:8001/api/v1/auth/login \
  -d 'username=ana@acme.test&password=Secret123'
```

## Ingerir el primer lead

La ingesta responde `202 Accepted` antes de interpretar el lead: la petición sólo confirma que el
payload quedó registrado, no cómo terminó procesándose. El procesamiento —viabilidad, puntuación,
asignación— corre después, en segundo plano.

```bash
curl -s -X POST http://localhost:8001/api/v1/intake/leads/ingest \
  -b /tmp/leads.cookies \
  -H 'Content-Type: application/json' \
  -d '{
    "first_name": "Maria",
    "last_name": "Gomez",
    "email": "mgomez@techcorp.com",
    "company": "TechCorp",
    "budget": 15000,
    "industry": "Technology",
    "phone": "+573001234567"
  }'
```

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "record_ids": ["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
  "status": "PENDING"
}
```

Sólo `MANAGER` ingesta; un `AGENT` recibe `403`. El detalle de las dos fases (recepción y
procesamiento) está en [Ingesta](../modulos/ingesta.md) y en
[ADR-0010](../decisiones/0010-recepcion-y-procesamiento-separados.md).

## Comprobar el resultado

El `job_id` de la respuesta anterior identifica el trabajo de ingesta:

```bash
curl -s http://localhost:8001/api/v1/intake/jobs/550e8400-e29b-41d4-a716-446655440000 \
  -b /tmp/leads.cookies
```

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "source_id": "22222222-2222-2222-2222-222222222222",
  "kind": "SINGLE",
  "status": "COMPLETED",
  "total_items": 1,
  "succeeded": 1,
  "failed": 0,
  "created_at": "2026-08-08T10:00:00+00:00",
  "completed_at": "2026-08-08T10:00:01+00:00"
}
```

Con `status: "COMPLETED"` y `succeeded: 1`, el lead ya existe. Para verlo:

```bash
curl -s http://localhost:8001/api/v1/leads -b /tmp/leads.cookies
```

La referencia completa de estos endpoints está en [API · Referencia](api-referencia.md).

## Cuando algo no arranca

- **Estado de los contenedores**: `docker compose ps` muestra si `db`, `lead-core` y `gateway` están
  `healthy`. `lead-core` no arranca hasta que `db` lo está. Un `gateway` sano sólo prueba que nginx
  responde: `/health` lo contesta él mismo, no lead-core. Un `503 SERVICE_UNAVAILABLE` en la API
  significa que el gateway no alcanza `lead-core`; mira `docker compose logs lead-core`.
- **Logs**: `docker compose logs -f lead-core` — las migraciones se aplican al arrancar el proceso
  (antes de aceptar peticiones), así que un contenedor que reinicia en bucle casi siempre señala un
  fallo de migración o de conexión a la base, visible ahí.
- **Puerto ocupado**: si `8001`, `5433`, `80` u `8002` ya los usa otro proceso en el host, `docker
  compose up -d` falla al publicar el puerto. Libera el puerto o cambia el mapeo en
  `docker-compose.yml`.
- **Arranque en limpio**: si el volumen de PostgreSQL quedó en un estado irrecuperable,

  ```bash
  docker compose down -v
  docker compose up -d
  ```

  borra el volumen y vuelve a aplicar las migraciones desde cero. No hace falta para el día a día;
  ver [Validación](validacion.md) para cuándo sí hace falta reconstruir la imagen.
