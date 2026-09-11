# Puesta en marcha

De cero a un lead ingerido: requisitos, arranque, el primer usuario, la primera organización y la
primera ingesta. Todos los comandos son `curl` reales, verificados contra el código.

## Requisitos

Docker y el plugin `docker compose`. Nada más: las variables de entorno del backend están fijadas
en `docker-compose.yml` para desarrollo local, así que no hace falta crear ningún `.env`.

## Arrancar la plataforma

```bash
docker compose up -d
```

Levanta cuatro servicios: `db` (PostgreSQL 16), `backend` (la API, que aplica las migraciones
pendientes al arrancar y recarga en caliente lo que cambie en `backend/src`), `frontend` (nginx
sirviendo el esqueleto de interfaz) y `docs` (este sitio). `backend` espera a que `db` esté sano;
`frontend` espera a que `backend` lo esté.

Puertos reales en el host:

| Servicio | Puerto | Por qué no el estándar |
|---|---|---|
| API | `8001` | `8000` es un puerto común y suele estar ocupado |
| Base de datos | `5433` | `5432` es el puerto por defecto de un PostgreSQL local |
| Interfaz web | `80` | — |
| Documentación | `8002` | `8000` y `8001` ya están tomados por la API |

Dentro de la red de `compose` cada servicio sigue escuchando en su puerto estándar (la API en
`8000`, la base en `5432`); el remapeo sólo afecta a cómo se les llega desde el host.

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
  "group_id": null,
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

`FRONTEND_ORIGIN` debe estar incluido exactamente en `CORS_ORIGINS`. Al completar las tres variables
de un proveedor aparece su botón en el login; sólo permite entrar a agentes humanos ya existentes con
correo de proveedor verificado. La vuelta conserva PKCE y, si MFA está activo, continúa en `/mfa`.

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
    "group_id": null,
    "is_active": true,
    "role": "MANAGER",
    "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
  }
}
```

La misma transacción crea también dos orígenes de leads (`LeadSource`) para la organización,
`MANUAL_FORM` y `FILE_UPLOAD`: sin uno de ellos activo, la ingesta de la siguiente sección
respondería `404 SOURCE_NOT_FOUND`.

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

- **Estado de los contenedores**: `docker compose ps` muestra si `db` y `backend` están `healthy`.
  `backend` no arranca hasta que `db` lo está.
- **Logs**: `docker compose logs -f backend` — las migraciones se aplican al arrancar el proceso
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
