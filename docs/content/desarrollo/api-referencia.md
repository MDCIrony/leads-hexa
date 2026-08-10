# API · Referencia

Referencia completa de la API HTTP, organizada por recurso. Todas las rutas cuelgan de `/api/v1`,
salvo `GET /health`. En desarrollo local, con la plataforma levantada, la API responde en
`http://localhost:8001` — ver [Puesta en marcha](puesta-en-marcha.md). Los códigos de error se
explican una sola vez, completos, en [API · Errores](api-errores.md); aquí sólo se nombra cuáles
puede devolver cada endpoint.

## Resumen de endpoints

| Recurso | Método y ruta | Rol | Éxito |
|---|---|---|---|
| Salud | `GET /health` | Público | 200 |
| Autenticación | `POST /api/v1/auth/login` | Público | 200 |
| Autenticación | `GET /api/v1/auth/me` | Cualquiera autenticado | 200 |
| Organizaciones | `POST /api/v1/tenants` | `ADMIN` | 201 |
| Organizaciones | `GET /api/v1/tenants` | `ADMIN` | 200 |
| Organizaciones | `PATCH /api/v1/tenants/{tenant_id}` | `ADMIN` | 200 |
| Agentes | `POST /api/v1/agents` | Bootstrap sin auth; luego `MANAGER` | 201 |
| Agentes | `GET /api/v1/agents` | `MANAGER` | 200 |
| Agentes | `GET /api/v1/agents/{agent_id}` | `MANAGER` | 200 |
| Agentes | `PATCH /api/v1/agents/{agent_id}` | `MANAGER` | 200 |
| Agentes | `DELETE /api/v1/agents/{agent_id}` | `MANAGER` | 200 |
| Grupos de ventas | `POST /api/v1/groups` | `MANAGER` | 201 |
| Grupos de ventas | `GET /api/v1/groups` | `MANAGER` | 200 |
| Grupos de ventas | `PATCH /api/v1/groups/{group_id}` | `MANAGER` | 200 |
| Grupos de ventas | `DELETE /api/v1/groups/{group_id}` | `MANAGER` | 204 |
| Orígenes de leads | `POST /api/v1/sources` | `MANAGER` | 201 |
| Orígenes de leads | `GET /api/v1/sources` | `MANAGER` | 200 |
| Orígenes de leads | `PATCH /api/v1/sources/{source_id}` | `MANAGER` | 200 |
| Orígenes de leads | `DELETE /api/v1/sources/{source_id}` | `MANAGER` | 204 |
| Ingesta | `POST /api/v1/intake/leads/ingest` | `MANAGER` | 202 |
| Ingesta | `POST /api/v1/intake/leads/batch-upload` | `MANAGER` | 202 |
| Bandeja de entrada | `GET /api/v1/intake/records` | `MANAGER` | 200 |
| Bandeja de entrada | `POST /api/v1/intake/records/{record_id}/promote` | `MANAGER` | 200 |
| Bandeja de entrada | `POST /api/v1/intake/records/{record_id}/discard` | `MANAGER` | 204 |
| Trabajos de ingesta | `GET /api/v1/intake/jobs` | `MANAGER` | 200 |
| Trabajos de ingesta | `GET /api/v1/intake/jobs/{job_id}` | `MANAGER` | 200 |
| Trabajos de ingesta | `POST /api/v1/intake/jobs/{job_id}/reprocess` | `MANAGER` | 202 |
| Leads | `GET /api/v1/leads` | `MANAGER` | 200 |
| Leads | `GET /api/v1/leads/mine` | `MANAGER` o `AGENT` | 200 |
| Leads | `GET /api/v1/leads/{lead_id}` | `MANAGER` o `AGENT` (el suyo) | 200 |
| Leads | `POST /api/v1/leads/{lead_id}/assign` | `MANAGER` | 200 |
| Leads | `POST /api/v1/leads/{lead_id}/discard` | `MANAGER` | 200 |
| Reglas | `POST /api/v1/rules/scoring` | `MANAGER` | 201 |
| Reglas | `GET /api/v1/rules/scoring` | `MANAGER` | 200 |
| Reglas | `POST /api/v1/rules/assignment` | `MANAGER` | 201 |
| Reglas | `GET /api/v1/rules/assignment` | `MANAGER` | 200 |
| Reglas | `PATCH /api/v1/rules/assignment/{rule_id}` | `MANAGER` | 200 |
| Reglas | `DELETE /api/v1/rules/assignment/{rule_id}` | `MANAGER` | 204 |
| Reglas | `POST /api/v1/rules/disqualification` | `MANAGER` | 201 |
| Reglas | `GET /api/v1/rules/disqualification` | `MANAGER` | 200 |
| Reglas | `PATCH /api/v1/rules/disqualification/{rule_id}` | `MANAGER` | 200 |
| Reglas | `DELETE /api/v1/rules/disqualification/{rule_id}` | `MANAGER` | 204 |
| Notificaciones | `GET /api/v1/notifications` | `MANAGER` o `AGENT` | 200 |
| Notificaciones | `POST /api/v1/notifications/read-all` | `MANAGER` o `AGENT` | 204 |
| Notificaciones | `POST /api/v1/notifications/{notification_id}/read` | `MANAGER` o `AGENT` (la suya) | 204 |

## Convenciones comunes

**Autenticación.** `Authorization: Bearer <token>`, obtenido de `POST /api/v1/auth/login`. La
organización de quien llama sale siempre del token — nunca de la URL ni del cuerpo de la petición;
ver [ADR-0004](../decisiones/0004-organizacion-desde-el-token.md). Todo endpoint fuera de `GET
/health` y `POST /api/v1/auth/login` responde `401 Unauthorized` sin un token válido; las listas de
errores de cada endpoint, más abajo, sólo nombran lo específico de ese recurso — el rol exigido y
los códigos `404`/`400` propios.

**Paginación.** Todo endpoint de lista acepta `limit` (por defecto 100, rango `1`-`1000`) y `offset`
(por defecto 0, mínimo `0`), y responde con la misma envoltura — con dos excepciones señaladas donde
aparecen: `GET /rules/scoring` devuelve un array liso sin envoltura, y `GET /rules/assignment` usa la
envoltura pero no acepta `limit`/`offset`: siempre devuelve todas las reglas en una única página. Un
`limit` u `offset` fuera de rango responde `422 VALIDATION_ERROR` con `details[].field` señalando el
parámetro, la misma envoltura de error que el resto de la API.

```json
{
  "items": ["…"],
  "total": 1,
  "limit": 100,
  "offset": 0,
  "has_more": false
}
```

**Roles.** `ADMIN` opera el plano de plataforma (organizaciones) y no alcanza ningún dato
operativo — recibe `403 Forbidden` en todo lo demás. `MANAGER` administra su propia organización.
`AGENT` es un usuario operativo acotado a lo suyo. El razonamiento completo está en
[Identidad y acceso](../modulos/identidad-y-acceso.md).

## Salud

### `GET /health`

Sin autenticación.

```http
GET /health HTTP/1.1
```

```json
{"status": "ok"}
```

## Autenticación

### `POST /api/v1/auth/login`

Público. El cuerpo va como formulario (`application/x-www-form-urlencoded`), no como JSON — es el
esquema estándar `OAuth2PasswordRequestForm` de FastAPI.

```http
POST /api/v1/auth/login HTTP/1.1
Content-Type: application/x-www-form-urlencoded

username=ana%40acme.test&password=Secret123
```

```json
{"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "token_type": "bearer"}
```

Errores: `401 Unauthorized` (`INVALID_CREDENTIALS`).

### `GET /api/v1/auth/me`

Cualquier rol autenticado. Es la única vía que tiene un `AGENT` para conocer su propio rol y
organización.

```json
{
  "id": "11111111-1111-1111-1111-111111111111",
  "name": "Ana Ruiz",
  "email": "ana@acme.test",
  "role": "MANAGER",
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "tenant_name": "Acme Corp"
}
```

Para un `ADMIN`, `tenant_id` y `tenant_name` son siempre `null`. Errores: `401 Unauthorized`.

## Organizaciones

Plano de plataforma. Los tres endpoints exigen `ADMIN`; cualquier otro rol recibe `403 Forbidden`.

### `POST /api/v1/tenants`

Crea una organización junto con su primer gestor, en una sola transacción: si el correo del gestor
ya está en uso, la organización tampoco se crea. La misma transacción crea además dos orígenes de
leads (`MANUAL_FORM` y `FILE_UPLOAD`) para la organización nueva.

```json
{
  "name": "Acme Corp",
  "manager": {"name": "Ana Ruiz", "email": "ana@acme.test", "password": "Secret123"}
}
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

Errores: `400 Bad Request` (`INVALID_TENANT_NAME` si el nombre no deja ningún carácter
alfanumérico con el que construir su identificador; `TENANT_ALREADY_EXISTS`;
`EMAIL_ALREADY_EXISTS`).

### `GET /api/v1/tenants`

Lista paginada. Cada elemento trae `agent_count` —el número de asesores activos— pero no
`manager`: es un agregado, no una lista de identidades.

### `PATCH /api/v1/tenants/{tenant_id}`

Renombra y/o activa/desactiva una organización. `name` e `is_active` son opcionales.
Desactivarla (`is_active: false`) desactiva en cascada a todos sus agentes: pierden acceso de
inmediato, aunque su token siga sin caducar, porque el login vuelve a comprobar el estado en base
de datos.

Errores: `400 Bad Request` — no `404` — si la organización no existe (`TENANT_NOT_FOUND`; ver la
nota en [API · Errores](api-errores.md)), o si el nuevo nombre no deja caracteres alfanuméricos
(`INVALID_TENANT_NAME`).

## Agentes

`MANAGER` en los cinco endpoints, siempre dentro de su propia organización. Un `ADMIN` o un
`AGENT` reciben `403 Forbidden`.

### `POST /api/v1/agents`

Crea un agente comercial. Mientras la tabla de agentes esté vacía, no exige credencial y el agente
creado nace siempre `ADMIN`, sin importar qué `role` traiga el cuerpo — es el único punto de
entrada al plano de plataforma. Fuera de ese estado inicial, exige `MANAGER` autenticado, la
organización es siempre la suya (no hay `tenant_id` en el cuerpo) y no puede crear otro `ADMIN`.

```json
{
  "name": "Carlos Ruiz",
  "email": "cruiz@techcorp.com",
  "group_id": "22222222-2222-2222-2222-222222222222",
  "password": "Secret123",
  "role": "AGENT"
}
```

```json
{
  "id": "11111111-1111-1111-1111-111111111111",
  "name": "Carlos Ruiz",
  "email": "cruiz@techcorp.com",
  "group_id": "22222222-2222-2222-2222-222222222222",
  "is_active": true,
  "role": "AGENT",
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
}
```

Errores: `401 Unauthorized` (fuera del bootstrap, sin token); `403 Forbidden` (no es `MANAGER`, o
intenta crear un `ADMIN`); `400 Bad Request` (`EMAIL_ALREADY_EXISTS`) si el correo ya está en uso —
la unicidad es de toda la plataforma, no sólo de la organización, porque el login resuelve la
cuenta por correo sin filtrar por organización.

### `GET /api/v1/agents`

Lista paginada de la propia organización. Acepta `group_id` para filtrar.

### `GET /api/v1/agents/{agent_id}`

Errores: `404 Not Found` (`AGENT_NOT_FOUND`, tanto si no existe como si es de otra organización).

### `PATCH /api/v1/agents/{agent_id}`

`name` y/o `group_id`, ambos opcionales. Errores: `404 Not Found` (`AGENT_NOT_FOUND`;
`GROUP_NOT_FOUND` si el grupo no existe o es de otra organización).

### `DELETE /api/v1/agents/{agent_id}`

**Desactiva**, no borra: los leads que ya tiene asignados siguen apuntando a su identificador.
Responde `200 OK` con el agente y `is_active: false`, no `204` — no es un borrado real. Un asesor
desactivado deja de recibir asignaciones automáticas pero su historial sigue legible. Errores:
`404 Not Found` (`AGENT_NOT_FOUND`).

## Grupos de ventas

Un grupo agrupa asesores bajo una política de asignación compartida (estrategia por defecto,
capacidad por asesor). Los cuatro endpoints exigen `MANAGER`.

### `POST /api/v1/groups`

```json
{
  "name": "Enterprise",
  "description": "Cuentas grandes",
  "default_strategy": "LOWEST_LOAD",
  "capacity_per_agent": 5
}
```

Errores: `400 Bad Request` (`GROUP_ALREADY_EXISTS` si el nombre ya existe en la organización;
`INVALID_GROUP_NAME`; `INVALID_GROUP_CAPACITY` si `capacity_per_agent` es menor o igual que cero).

### `GET /api/v1/groups`

Lista paginada; cada elemento trae `agent_count`.

### `PATCH /api/v1/groups/{group_id}`

Todos los campos opcionales. Desactivar un grupo (`is_active: false`) **no** desactiva a sus
asesores: dejan de recibir asignaciones automáticas, pero siguen atendiendo lo que ya tienen — es
la diferencia con desactivar una organización, que sí corta el acceso.

Errores: `404 Not Found` (`GROUP_NOT_FOUND`); `400 Bad Request` (`INVALID_GROUP_NAME` si el nuevo
nombre llega vacío). A diferencia de la creación, `capacity_per_agent` no se vuelve a validar aquí:
se sobrescribe tal cual llega.

### `DELETE /api/v1/groups/{group_id}`

Sus asesores no se borran: quedan sin grupo (`group_id: null`). Errores: `404 Not Found`
(`GROUP_NOT_FOUND`).

## Orígenes de leads

`LeadSource` responde «¿de dónde vienen mis leads?»: cada lead ingerido lleva el `source_id` de la
fuente por la que entró. Al crear una organización nacen automáticamente dos, `MANUAL_FORM` y
`FILE_UPLOAD` — las que usan la ingesta individual y la carga de ficheros. Los cuatro endpoints
exigen `MANAGER`.

### `POST /api/v1/sources`

```json
{"name": "Facebook Lead Ads — Campaña Verano", "kind": "MANUAL_FORM", "field_mapping": {}}
```

Errores: `400 Bad Request` (`SOURCE_ALREADY_EXISTS` si el nombre ya existe en la organización —
el mismo nombre sí se acepta en otra; `SOURCE_WITHOUT_NAME` si el nombre llega vacío;
`INVALID_FIELD_MAPPING` si `field_mapping` trae una clave o un valor vacíos).

### `GET /api/v1/sources`

Lista paginada.

### `PATCH /api/v1/sources/{source_id}`

`name`, `field_mapping` e `is_active`, todos opcionales. Errores: `404 Not Found`
(`SOURCE_NOT_FOUND`); `400 Bad Request` (`SOURCE_WITHOUT_NAME`, `INVALID_FIELD_MAPPING` — se
validan igual que en la creación).

### `DELETE /api/v1/sources/{source_id}`

Errores: `404 Not Found` (`SOURCE_NOT_FOUND`); `400 Bad Request` (`SOURCE_IN_USE` si tiene leads
asociados — no se borra en silencio la trazabilidad de esos leads).

## Ingesta

Recibe un lead y responde **antes** de interpretarlo: la recepción persiste el payload y crea su
`IntakeJob` en una transacción propia; el procesamiento —viabilidad, puntuación, asignación— corre
después, en segundo plano, en una transacción distinta. Ningún fallo en esa segunda fase puede ya
borrar la constancia de haber recibido el lead. El resultado se consulta por `job_id` (más abajo,
_Trabajos de ingesta_) o por el registro (_Bandeja de entrada_). El razonamiento completo está en
[ADR-0009](../decisiones/0009-registrar-antes-de-interpretar.md) y
[ADR-0010](../decisiones/0010-recepcion-y-procesamiento-separados.md).

### `POST /api/v1/intake/leads/ingest`

`MANAGER`. La organización sale del token; un `tenant_id` en el cuerpo se ignora.

```json
{
  "first_name": "Maria",
  "last_name": "Gomez",
  "email": "mgomez@techcorp.com",
  "company": "TechCorp",
  "budget": 15000.0,
  "industry": "Technology",
  "custom_attributes": {"employee_count": 150},
  "phone": "+573001234567"
}
```

`email` es opcional, y el esquema de entrada no valida su formato — esa comprobación la hace el
dominio, más adelante en el pipeline. Un correo mal formado ya no descarta el payload con un `422`:
llega al dominio, que lo rechaza dejando el registro en la bandeja con su detalle, en vez de
perderlo (ver _Bandeja de entrada_ más abajo). Ver
[ADR-0008](../decisiones/0008-correo-opcional.md).

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "record_ids": ["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
  "status": "PENDING"
}
```

Errores: `401 Unauthorized`; `403 Forbidden` (un `AGENT` no ingesta); `404 Not Found`
(`SOURCE_NOT_FOUND`, si la organización no tiene un origen `MANUAL_FORM` activo). Un payload que no
interpreta **no** responde con un error síncrono: la petición igual responde `202`, y el registro
queda `REJECTED` en la bandeja con el trabajo `COMPLETED` y `failed: 1`.

### `POST /api/v1/intake/leads/batch-upload`

`MANAGER`. Recibe un archivo CSV o Excel como `multipart/form-data` (campo `file`) y responde antes
de parsearlo: la fase de recepción sólo crea el `IntakeJob`, así que `record_ids` siempre llega
vacío — las filas todavía no existen. El procesamiento en segundo plano parsea el fichero, crea un
`IntakeRecord` por fila y las procesa por el mismo pipeline que la ingesta individual; la fila que
falla no se pierde, queda como su propio registro en la bandeja.

```http
POST /api/v1/intake/leads/batch-upload HTTP/1.1
Content-Type: multipart/form-data; boundary=...

--...
Content-Disposition: form-data; name="file"; filename="leads.csv"
Content-Type: text/csv

first_name,last_name,email,company,industry,budget
Maria,Gomez,mgomez@techcorp.com,TechCorp,Technology,15000
--...--
```

```json
{"job_id": "550e8400-e29b-41d4-a716-446655440000", "record_ids": [], "status": "PENDING"}
```

Errores: `401 Unauthorized`; `403 Forbidden`; `404 Not Found` (`SOURCE_NOT_FOUND`, si la
organización no tiene un origen `FILE_UPLOAD` activo). Un fichero ilegible tampoco responde con un
error: la petición ya contestó `202`, y el trabajo queda `FAILED` sin ningún registro.

## Bandeja de entrada

Todo payload que llega a la ingesta se persiste como `IntakeRecord` **antes** de intentar
interpretarlo, así que nada de lo que no valida se pierde: queda aquí, con el motivo exacto del
fallo, para que el gestor lo corrija y lo reintente o lo descarte.

### `GET /api/v1/intake/records`

`MANAGER`. Filtra por `status` (`PENDING` · `PROMOTED` · `REJECTED` · `DISCARDED`) y por `job_id`.

```json
{
  "items": [
    {
      "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "source_id": "22222222-2222-2222-2222-222222222222",
      "status": "REJECTED",
      "payload": {"first_name": "Jane", "email": "jane@@example.com", "company": "Acme"},
      "errors": [
        {"field": "email", "message": "Formato de correo electrónico inválido",
         "received_value": "jane@@example.com", "error_code": "INVALID_EMAIL"}
      ],
      "received_at": "2026-08-08T10:00:00+00:00",
      "processed_at": "2026-08-08T10:00:00+00:00",
      "lead_id": null
    }
  ],
  "total": 1, "limit": 100, "offset": 0, "has_more": false
}
```

Errores: `401 Unauthorized`; `403 Forbidden`; `400 Bad Request` (`INVALID_INTAKE_STATUS` si
`status` no es un valor conocido).

### `POST /api/v1/intake/records/{record_id}/promote`

`MANAGER`. Reintenta un registro con el `payload` corregido. Si valida, genera el lead y marca el
registro `PROMOTED` reutilizando la misma fila — nunca añade una segunda.

```json
{"payload": {"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com",
             "company": "Acme", "industry": "Tech", "budget": 3000}}
```

Éxito (`200 OK`), misma forma que el resultado interno de la ingesta:

```json
{
  "lead_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "QUALIFIED",
  "score": 40,
  "assigned_agent_id": null,
  "applied_rules_count": 1,
  "error": null,
  "error_code": null,
  "intake_record_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
}
```

Si el `payload` corregido sigue sin validar, el registro permanece `REJECTED` con los errores
nuevos y la respuesta es `400 Bad Request` con la misma forma más `error` y `error_code` rellenos.
Errores: `404 Not Found` (`INTAKE_RECORD_NOT_FOUND`); `400 Bad Request`
(`INVALID_INTAKE_TRANSITION` si el registro no está en un estado promovible — por ejemplo, ya
`PROMOTED`).

### `POST /api/v1/intake/records/{record_id}/discard`

`MANAGER`. El gestor decide no recuperar el registro. Errores: `404 Not Found`
(`INTAKE_RECORD_NOT_FOUND`); `400 Bad Request` (`INVALID_INTAKE_TRANSITION` si ya está
`PROMOTED` o `DISCARDED`).

## Trabajos de ingesta

`IntakeJob` es lo que la recepción crea y responde como `job_id`: por él se sabe si el
procesamiento en segundo plano ya terminó, y cómo le fue.

### `GET /api/v1/intake/jobs`

`MANAGER`. Filtra por `status` (`PENDING` · `PROCESSING` · `COMPLETED` · `FAILED`).

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "source_id": "22222222-2222-2222-2222-222222222222",
      "kind": "SINGLE",
      "status": "COMPLETED",
      "total_items": 1, "succeeded": 1, "failed": 0,
      "created_at": "2026-08-08T10:00:00+00:00",
      "completed_at": "2026-08-08T10:00:01+00:00"
    }
  ],
  "total": 1, "limit": 100, "offset": 0, "has_more": false
}
```

Errores: `401 Unauthorized`; `403 Forbidden`; `400 Bad Request` (`INVALID_JOB_STATUS`).

### `GET /api/v1/intake/jobs/{job_id}`

`total_items` es `null` en una carga masiva hasta que el fichero se parsea en segundo plano — no se
conoce todavía al aceptar la petición. Errores: `404 Not Found` (`INTAKE_JOB_NOT_FOUND`).

### `POST /api/v1/intake/jobs/{job_id}/reprocess`

`MANAGER`. Relanza un trabajo que quedó a medias — interrumpido antes de procesarse, o detenido por
un fallo imprevisto. Reinicia sus contadores y vuelve a leer sólo los registros que sigan
`PENDING`: los que ya llegaron a un estado terminal no se tocan, así que reprocesar dos veces nunca
duplica un lead.

A diferencia de la ingesta, **no** corre en segundo plano: la comprobación de propiedad y de estado
es síncrona, porque una vez que la respuesta ha empezado a enviarse, una excepción lanzada dentro
de una tarea de fondo ya no puede convertirse en un `404`/`400` limpio.

Responde `202 Accepted` con el trabajo ya en su estado final (`COMPLETED` o `FAILED`). Errores:
`404 Not Found` (`INTAKE_JOB_NOT_FOUND`); `400 Bad Request` (`INVALID_JOB_TRANSITION` si el
trabajo ya está `COMPLETED` o `FAILED`).

## Leads

Ciclo de vida completo del lead: listado, las dos vistas de detalle, asignación manual y descarte.

### `GET /api/v1/leads`

`MANAGER` únicamente: devuelve el flujo completo de la organización, así que un `AGENT` que lo
alcanzara leería los leads de sus compañeros. Un `ADMIN` recibe `403`: el plano de plataforma no
alcanza dato operativo.

```json
{
  "items": [
    {
      "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
      "first_name": "Maria", "last_name": "Gomez", "email": "mgomez@techcorp.com",
      "company": "TechCorp", "budget": 15000.0, "industry": "Technology",
      "custom_attributes": {"employee_count": 150}, "phone": "+573001234567",
      "score": 45, "status": "QUALIFIED",
      "assigned_agent_id": "11111111-1111-1111-1111-111111111111",
      "created_at": "2026-08-05T10:00:00+00:00"
    }
  ],
  "total": 1, "limit": 100, "offset": 0, "has_more": false
}
```

### `GET /api/v1/leads/mine`

`MANAGER` o `AGENT`. Los leads asignados a quien llama — la única vía que tiene un `AGENT` hacia
sus propios leads. Declarada antes de `/{lead_id}` en el router: FastAPI resuelve rutas en el orden
en que se declaran, y al revés `mine` caería en la ruta paramétrica y fallaría al interpretarse
como UUID.

### `GET /api/v1/leads/{lead_id}`

`MANAGER` alcanza cualquier lead de su organización; un `AGENT` sólo el suyo. Añade
`score_breakdown` (una entrada por cada regla de puntuación que se aplicó), `assigned_at` y
`discard_reason` o `disqualification_reason` sobre los campos del listado.

```json
{
  "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "first_name": "Maria", "last_name": "Gomez", "email": "mgomez@techcorp.com",
  "company": "TechCorp", "budget": 15000.0, "industry": "Technology",
  "custom_attributes": {"employee_count": 150}, "phone": "+573001234567",
  "score": 50,
  "score_breakdown": [
    {"rule_id": "22222222-2222-2222-2222-222222222222", "name": "Tech leads", "score_delta": 50}
  ],
  "status": "UNASSIGNED",
  "assigned_agent_id": null, "assigned_at": null,
  "discard_reason": null, "disqualification_reason": null,
  "created_at": "2026-08-05T10:00:00+00:00"
}
```

Errores: `404 Not Found` (`LEAD_NOT_FOUND`) si el identificador no existe, pertenece a otra
organización, o un `AGENT` pide el detalle de un lead ajeno — nunca `403`, para no confirmarle que
ese lead existe en su organización.

### `POST /api/v1/leads/{lead_id}/assign`

`MANAGER`. Asigna el lead a un asesor. Si ya está `ASSIGNED`, reasigna: es la misma operación sin
importar el estado de partida.

```json
{"agent_id": "11111111-1111-1111-1111-111111111111"}
```

Errores: `404 Not Found` (`LEAD_NOT_FOUND` o `AGENT_NOT_FOUND` — el asesor se resuelve acotado a la
organización del gestor, así que uno ajeno se lee como inexistente, nunca como `403`);
`400 Bad Request` (`INVALID_LEAD_TRANSITION` si el lead está en un estado no asignable, como
`DISCARDED`).

### `POST /api/v1/leads/{lead_id}/discard`

`MANAGER`. Motivo obligatorio.

```json
{"reason": "Presupuesto insuficiente"}
```

Errores: `404 Not Found` (`LEAD_NOT_FOUND`); `400 Bad Request` (`DISCARD_WITHOUT_REASON` si el
motivo llega vacío).

## Reglas

`MANAGER` en los diez endpoints; el tenant sale siempre del token. Las condiciones de toda regla
—puntuación, asignación o descalificación— viajan como una lista de `Criterion`
(`{"field", "operator", "value"}`): una regla se cumple cuando se cumplen **todas** sus
condiciones, no hay `OR` entre ellas — las alternativas se escriben como reglas separadas. Los
operadores `IS_EMPTY` e `IS_NOT_EMPTY` ignoran `value`. La lista blanca de campos evaluables
(`first_name`, `last_name`, `email`, `company`, `industry`, `budget`, `phone`, `score`, más
cualquier `custom_attributes.<clave>`) es la misma en las tres etapas. Ver
[ADR-0011](../decisiones/0011-gramatica-de-condiciones.md) y
[ADR-0012](../decisiones/0012-y-dentro-o-entre.md).

**Reglas de puntuación**

### `POST /api/v1/rules/scoring`

Suma `score_delta` cuando se cumplen todas sus condiciones.

```json
{
  "name": "High Budget Rule",
  "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 10000}],
  "score_delta": 20
}
```

Errores: `400 Bad Request` (`INVALID_RULE_FIELD` si algún `field` llega vacío;
`FIELD_NOT_SCORABLE` si no está en la lista blanca; `INVALID_RULE_VALUE` si el operador `IN` no
recibe una lista).

### `GET /api/v1/rules/scoring`

!!! note
    Único endpoint de lista que **no** usa la envoltura de paginación: responde un array JSON
    liso (`List[ScoringRuleResponse]`), no `{items, total, ...}`. Tampoco existen `PATCH` ni
    `DELETE` para reglas de puntuación hoy — a diferencia de las de asignación y descalificación,
    que sí los tienen.

```json
[
  {
    "id": "22222222-2222-2222-2222-222222222222",
    "name": "High Budget Rule",
    "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 10000}],
    "score_delta": 20, "priority": 0, "is_active": true
  }
]
```

**Reglas de asignación**

### `POST /api/v1/rules/assignment`

La regla debe apuntar a un grupo (`target_group_id`), a asesores concretos (`target_agent_ids`), o
a ambos; `agent_match_mode` decide si son la unión (`ANY`, por defecto) o la intersección (`ONLY`)
con el grupo. `strategy` es opcional: si se omite, se usa la del grupo destino. `conditions` es
opcional y vacía por defecto — sin condiciones, la regla discrimina sólo por banda de puntuación.

```json
{
  "name": "Enterprise band",
  "min_score": 70, "max_score": 100,
  "target_group_id": "22222222-2222-2222-2222-222222222222",
  "agent_match_mode": "ANY", "strategy": "ROUND_ROBIN", "priority": 10,
  "conditions": [{"field": "custom_attributes.channel", "operator": "EQUALS", "value": "referral"}]
}
```

Errores: `404 Not Found` (`GROUP_NOT_FOUND` si `target_group_id` no existe o pertenece a otra
organización); `400 Bad Request` (`INVALID_RULE_NAME`; `INVALID_SCORE_BAND` si `max_score` es menor
que `min_score`; `RULE_WITHOUT_TARGET` si no se indica ni grupo ni asesores; y las de `Criterion`
—`INVALID_RULE_FIELD`, `FIELD_NOT_SCORABLE`, `INVALID_RULE_VALUE`— sobre cada condición).

### `GET /api/v1/rules/assignment`

Ordenadas por prioridad descendente — la misma con la que el motor las evalúa. El motor carga
todas las reglas en cada ingesta, así que esta lista no pagina de verdad: siempre es una única
página con todo.

### `PATCH /api/v1/rules/assignment/{rule_id}`

Todos los campos opcionales; los ausentes se dejan sin cambios. `rr_cursor` no es uno de ellos a
propósito, así que una actualización parcial nunca reinicia una rotación en curso. Las condiciones
se validan igual que en la creación (a través de `Criterion`), y el nombre y la banda de puntuación
**no** se vuelven a comprobar: se sobrescriben tal cual llegan. `target_group_id` es la excepción:
se resuelve acotado a la organización del token, igual que en la creación.

Errores: `404 Not Found` (`ASSIGNMENT_RULE_NOT_FOUND`; `GROUP_NOT_FOUND` si el nuevo
`target_group_id` no existe o es de otra organización); `400 Bad Request` (`INVALID_RULE_FIELD`,
`FIELD_NOT_SCORABLE`, `INVALID_RULE_VALUE`, si `conditions` viene en el cuerpo).

### `DELETE /api/v1/rules/assignment/{rule_id}`

No toca a los asesores que nombraba ni a los que pertenecían a su grupo destino. Errores:
`404 Not Found` (`ASSIGNMENT_RULE_NOT_FOUND`).

**Reglas de descalificación**

La etapa de viabilidad: se evalúa **antes** de puntuar y corta el flujo. Si una regla se cumple, el
lead queda `DISQUALIFIED` con el nombre de la regla como motivo, y no llega a puntuarse ni a
repartirse.

### `POST /api/v1/rules/disqualification`

`conditions` no puede llegar vacía: una regla sin condiciones se cumpliría siempre y descalificaría
a toda la organización.

```json
{
  "name": "Sin vía de contacto",
  "conditions": [
    {"field": "phone", "operator": "IS_EMPTY"},
    {"field": "email", "operator": "IS_EMPTY"}
  ]
}
```

Errores: `400 Bad Request` (`INVALID_RULE_NAME`; `INVALID_RULE_CONDITIONS` si `conditions` llega
vacía; y las de `Criterion` sobre cada condición).

### `GET /api/v1/rules/disqualification`

Lista paginada.

### `PATCH /api/v1/rules/disqualification/{rule_id}`

Todos los campos opcionales, con la misma validación que la creación: un `name` o `conditions`
enviados vacíos se rechazan en vez de guardarse.

Errores: `404 Not Found` (`DISQUALIFICATION_RULE_NOT_FOUND`); `400 Bad Request`
(`INVALID_RULE_NAME`, `INVALID_RULE_CONDITIONS`, y las de `Criterion`).

### `DELETE /api/v1/rules/disqualification/{rule_id}`

Errores: `404 Not Found` (`DISQUALIFICATION_RULE_NOT_FOUND`).

## Notificaciones

La campana que avisa a quien debe actuar sin que tenga que ir a buscarlo. La crea
`NotificationHandler` al
asignarse o reasignarse un lead, al quedar uno sin asesor, o al rechazarse un registro de ingesta.
Los tres endpoints exigen organización propia (`MANAGER` o `AGENT`); el destinatario sale siempre
del token, nunca de la URL. Un `ADMIN` recibe `403 Forbidden`: no pertenece a ninguna organización.

### `GET /api/v1/notifications`

Acepta `unread_only` (por defecto `false`).

```json
{
  "items": [
    {
      "id": "55555555-5555-5555-5555-555555555555",
      "kind": "LEAD_ASSIGNED",
      "message": "Tienes un lead nuevo asignado",
      "lead_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "intake_record_id": null,
      "is_read": false,
      "created_at": "2026-08-08T10:00:00+00:00"
    }
  ],
  "total": 1, "limit": 100, "offset": 0, "has_more": false,
  "unread_count": 1
}
```

`unread_count` es siempre el total de no leídas del destinatario, no el de la página: viaja junto a
la lista porque la campana necesita las dos cosas a la vez, y dos peticiones para pintar un icono
es lo que convierte el sondeo en un problema. Ver
[ADR-0015](../decisiones/0015-notificaciones-por-sondeo.md).

### `POST /api/v1/notifications/read-all`

Marca todas las notificaciones de quien llama como leídas. Idempotente. Declarada antes que
`/{notification_id}/read` por la misma razón que `leads/mine`: si no, `read-all` caería en la ruta
paramétrica.

### `POST /api/v1/notifications/{notification_id}/read`

Sólo sobre las propias. Errores: `404 Not Found` (`NOTIFICATION_NOT_FOUND` si no existe o
pertenece a otro destinatario — nunca `403`).

## Ver también

- [API · Errores](api-errores.md) — el catálogo completo de códigos de error.
- [Ingesta](../modulos/ingesta.md), [Reglas y motores](../modulos/reglas.md),
  [Asignación](../modulos/asignacion.md), [Notificaciones](../modulos/notificaciones.md) — el
  porqué de negocio detrás de cada recurso.
