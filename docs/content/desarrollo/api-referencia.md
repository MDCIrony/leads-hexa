# API · Referencia

Referencia completa de la API HTTP, organizada por recurso. Todas las rutas cuelgan de `/api/v1`,
salvo `GET /health`. En desarrollo local, con la plataforma levantada, la API responde en
`http://localhost:8001`, que es el gateway nginx (`backend` no publica puerto); ver
[Puesta en marcha](puesta-en-marcha.md). Los códigos de error se
explican una sola vez, completos, en [API · Errores](api-errores.md); aquí sólo se nombra cuáles
puede devolver cada endpoint.

## Resumen de endpoints

| Recurso | Método y ruta | Rol | Éxito |
|---|---|---|---|
| Salud | `GET /health` | Público | 200 |
| Autenticación | `POST /api/v1/auth/login`, `POST /api/v1/auth/logout` | Público/cookie | 200/204 |
| OAuth | `GET /api/v1/auth/oauth/providers`, `/{provider}/start`, `/{provider}/callback` | Público/navegador | 200/303 |
| MFA | `POST /api/v1/auth/mfa/setup`, `/setup/confirm`, `/recovery-codes/regenerate`, `/disable` | Cookie de sesión humana | 200/204 |
| Verificación MFA | `POST /api/v1/auth/mfa/verify` | Cookie temporal de desafío MFA | 200 |
| Autenticación | `GET /api/v1/auth/me` | Cualquiera autenticado | 200 |
| Organizaciones | `POST /api/v1/tenants` | `ADMIN` | 201 |
| Organizaciones | `GET /api/v1/tenants` | `ADMIN` | 200 |
| Organizaciones | `PATCH /api/v1/tenants/{tenant_id}` | `ADMIN` | 200 |
| Agentes | `POST /api/v1/agents` | Bootstrap sin credencial; luego `MANAGER` | 201 |
| Agentes | `POST /api/v1/agents/integration-credential` | `MANAGER` | 201 |
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
| Leads | `GET /api/v1/leads` | `MANAGER` o `X-Api-Key` de integración | 200 |
| Leads | `GET /api/v1/leads/mine` | `MANAGER` o `AGENT` | 200 |
| Leads | `GET /api/v1/leads/stats` | `MANAGER` | 200 |
| Leads | `GET /api/v1/leads/{lead_id}` | `MANAGER` o `AGENT` (el suyo) | 200 |
| Leads | `POST /api/v1/leads/{lead_id}/assign` | `MANAGER` | 200 |
| Leads | `POST /api/v1/leads/{lead_id}/discard` | `MANAGER` | 200 |
| Reglas | `POST /api/v1/rules/scoring` | `MANAGER` | 201 |
| Reglas | `GET /api/v1/rules/scoring` | `MANAGER` | 200 |
| Reglas | `PATCH /api/v1/rules/scoring/{rule_id}` | `MANAGER` | 200 |
| Reglas | `DELETE /api/v1/rules/scoring/{rule_id}` | `MANAGER` | 204 |
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

**Autenticación humana.** Cookie HttpOnly `leads_session`, fijada por `POST /api/v1/auth/login` después
del segundo factor cuando MFA está activo. Durante la verificación se usa la cookie temporal
`leads_mfa_challenge`. La organización de quien llama sale siempre de la sesión — nunca de la URL ni del cuerpo de la petición;
ver [ADR-0004](../decisiones/0004-organizacion-desde-el-token.md). Los endpoints que exigen sesión
humana responden `401 Unauthorized` sin una sesión válida; `/mfa/verify` usa en su lugar el desafío
temporal descrito abajo. Las listas de errores de cada endpoint sólo nombran lo específico de ese
recurso — el rol exigido y los códigos `404`/`400` propios.

**Credencial de integración (`X-Api-Key`).** Formato `{agent_id}.{secreto}`. La valida el gateway, en
la introspección, antes de que la petición llegue a la API; por eso **no aparece como esquema de
seguridad en OpenAPI ni en `/docs`** y se documenta aquí a mano. Sólo `GET /api/v1/leads` la acepta: en
cualquier otra ruta protegida responde `401 UNAUTHORIZED`. Cada petición con clave cuesta un bcrypt
(≈ 290 ms medidos, ver [Mediciones](../microservices/07-evoluciones-y-riesgos.md#mediciones)); una
clave inválida es `401`, con el mismo mensaje que cualquier otra credencial fallida.

**Errores del gateway.** Algunas respuestas las genera el gateway sin llegar a la API: `401`
(`UNAUTHORIZED`, siempre con el mensaje «Authentication required»), `403` por `Origin` no permitido en
una escritura, `404` en rutas no publicadas, `413` por cuerpos de más de 10 MB, `429` en
`/api/v1/auth/` y `503` si la API no responde. Llevan el mismo sobre JSON y se listan en
[API · Errores](api-errores.md#errores-del-gateway). Toda respuesta, incluidas ésas, lleva
`X-Request-Id`.

**Paginación.** Todo endpoint de lista acepta `limit` (por defecto 100, rango `1`-`1000`) y `offset`
(por defecto 0, mínimo `0`), y responde con la misma envoltura `{items, total, limit, offset,
has_more}`. `GET /rules/assignment` es la única con una salvedad interna: el repositorio de reglas de
asignación no pagina por sí mismo —el motor de asignación carga siempre la organización entera—, así
que el recorte de página ocurre sobre esa lista ya completa, no en la consulta SQL; el contrato hacia
fuera es idéntico al resto. Un `limit` u `offset` fuera de rango responde `422 VALIDATION_ERROR` con
`details[].field` señalando el parámetro, la misma envoltura de error que el resto de la API.

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
{"status": "AUTHENTICATED"}
```

Con MFA activo responde `{"status":"MFA_REQUIRED"}` y fija `leads_mfa_challenge`; todavía no crea
una sesión autenticada.

Errores: `401 Unauthorized` (`INVALID_CREDENTIALS`).

### OAuth de Google y GitHub

`GET /api/v1/auth/oauth/providers` devuelve sólo los proveedores configurados:

```json
{"providers":["GOOGLE","GITHUB"]}
```

El navegador abre `GET /api/v1/auth/oauth/{provider}/start?return_path=/ruta-interna`; la API crea un
desafío de cinco minutos ligado a una cookie HttpOnly y responde `303` al proveedor con Authorization
Code + PKCE S256. El callback también responde `303`: para una cuenta humana existente, activa y con
correo verificado crea la cookie de sesión opaca o el desafío MFA existente. Nunca registra cuentas,
persiste tokens del proveedor ni devuelve `code`, `state` o correo en la URL final. Un fallo redirige
de forma genérica a `/login?oauth_error=1`. `return_path` sólo admite una ruta interna sin consulta ni
fragmento; el destino final siempre empieza en `FRONTEND_ORIGIN`. Un proveedor incompleto no aparece
en `/oauth/providers` y sus rutas responden `404`.

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
  "tenant_name": "Acme Corp",
  "mfa_enabled": false,
  "linked_oauth_providers": ["GOOGLE"]
}
```

Para un `ADMIN`, `tenant_id` y `tenant_name` son siempre `null`. Errores: `401 Unauthorized`.
`linked_oauth_providers` enumera únicamente las identidades sociales ya vinculadas a la cuenta; no
debe confundirse con los proveedores disponibles globalmente en `GET /auth/oauth/providers`.

### MFA

`POST /api/v1/auth/mfa/verify` recibe `{"code":"123456"}` y la cookie temporal
`leads_mfa_challenge`; acepta TOTP o un código de recuperación y, al verificarlo, crea la sesión
humana. Sin un desafío vigente o con un factor inválido responde `401 Unauthorized`
(`INVALID_CREDENTIALS`); se puede reintentar hasta cinco veces, tras lo cual se elimina la cookie
del desafío y hay que iniciar sesión de nuevo. El enrolamiento usa `setup` con contraseña,
`setup/confirm` con TOTP y devuelve los ocho códigos una sola vez.
`recovery-codes/regenerate` y `disable` exigen contraseña y factor vigente.

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
`manager`: es un agregado, no una lista de identidades. El orden es `created_at DESC, id`: la
organización más nueva sale primero, igual que `GET /leads` y `GET /notifications`.

### `PATCH /api/v1/tenants/{tenant_id}`

Renombra y/o activa/desactiva una organización. `name` e `is_active` son opcionales.
Desactivarla (`is_active: false`) desactiva en cascada a todos sus agentes: pierden acceso de
inmediato, aunque su token siga sin caducar, porque el login vuelve a comprobar el estado en base
de datos.

Errores: `400 Bad Request` — no `404` — si la organización no existe (`TENANT_NOT_FOUND`; ver la
nota en [API · Errores](api-errores.md)), o si el nuevo nombre no deja caracteres alfanuméricos
(`INVALID_TENANT_NAME`).

## Agentes

`MANAGER` en los seis endpoints, siempre dentro de su propia organización. Un `ADMIN` o un
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

El gateway la trata con introspección opcional: sin credencial la deja pasar y la API decide (sólo el
bootstrap sobre una base de agentes vacía es válido anónimo). Una credencial que llegue debe ser
válida, y una de integración aquí es `401`.

Errores: `401 Unauthorized` (fuera del bootstrap, sin sesión); `403 Forbidden` (no es `MANAGER`, o
intenta crear un `ADMIN`); `400 Bad Request` (`EMAIL_ALREADY_EXISTS`) si el correo ya está en uso —
la unicidad es de toda la plataforma, no sólo de la organización, porque el login resuelve la
cuenta por correo sin filtrar por organización.

### `POST /api/v1/agents/integration-credential`

Emite o rota la credencial de máquina de la propia organización — upsert, no dos rutas separadas
para alta y rotación: si ya existe, sustituye el secreto en el acto, sin ventana de solape. Detalle
completo en [Autenticación de la mensajería](../eventos/autenticacion.md).

```json
{
  "agent_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "api_key": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d.xR2k9F...",
  "kafka_username": "tenant-a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "kafka_password": "wL8pQ...",
  "kafka_bootstrap_servers": "localhost:9094",
  "kafka_topic": "leads.a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
}
```

`api_key` va en la cabecera `X-Api-Key` de `GET /api/v1/leads`, el único endpoint que la acepta.
Revocar es `DELETE /api/v1/agents/{agent_id}` — el mismo endpoint de siempre, sin ruta especial.
Errores: `403 Forbidden` (no es `MANAGER`); `503 Service Unavailable` (`MESSAGING_UNAVAILABLE`) si
Kafka no admite la credencial en ese instante — la operación entera falla sin dejar un agente a
medias.

### `GET /api/v1/agents`

Lista paginada de la propia organización. Acepta `group_id` para filtrar, y `is_active` para elegir
qué franja de activación se lista:

| Petición | Devuelve |
|---|---|
| `GET /agents` | sólo activos — el comportamiento de siempre, sin cambios |
| `GET /agents?is_active=false` | sólo desactivados |
| `GET /agents?is_active=true` | sólo activos, explícito |

### `GET /api/v1/agents/{agent_id}`

Errores: `404 Not Found` (`AGENT_NOT_FOUND`, tanto si no existe como si es de otra organización).

### `PATCH /api/v1/agents/{agent_id}`

`name`, `group_id` y/o `is_active`, los tres opcionales. `is_active: true` **reactiva** a un asesor
desactivado con `DELETE` — no hay un endpoint aparte para eso, activar y desactivar son el mismo
atributo. Reactivar sólo cambia `is_active`: `group_id` y las asignaciones que ya tenía no se tocan,
y el asesor recupera el acceso en el acto porque cada petición suya vuelve a resolver su identidad
contra base de datos. Errores: `404 Not Found` (`AGENT_NOT_FOUND`; `GROUP_NOT_FOUND` si el grupo no
existe o es de otra organización).

### `DELETE /api/v1/agents/{agent_id}`

**Desactiva**, no borra: los leads que ya tiene asignados siguen apuntando a su identificador.
Responde `200 OK` con el agente y `is_active: false`, no `204` — no es un borrado real. Un asesor
desactivado deja de recibir asignaciones automáticas pero su historial sigue legible, y deja de
aparecer en `GET /agents` sin parámetro (sigue visible con `?is_active=false`). La operación inversa
es `PATCH /api/v1/agents/{agent_id}` con `{"is_active": true}`. Errores: `404 Not Found`
(`AGENT_NOT_FOUND`).

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
de parsearlo: la fase de recepción crea el `IntakeJob` y guarda el fichero tal cual llegó, así que
`record_ids` siempre llega vacío — las filas todavía no existen. Un cuerpo de más de 10 MB responde
`413` (`PAYLOAD_TOO_LARGE`). El `intake-worker` parsea el fichero guardado, crea un
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
El orden es `received_at DESC, id`: el último registro que llegó sale primero, igual que
`GET /leads` y `GET /notifications` — lo que un gestor abre a mirar es lo que acaba de entrar.

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

`MANAGER`. Filtra por `status` (`PENDING` · `PROCESSING` · `COMPLETED` · `FAILED`). El orden es
`created_at DESC, id`: el trabajo más reciente sale primero.

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

La comprobación de propiedad y de estado es síncrona, para que un trabajo ajeno o ya terminado sea
un `404`/`400` limpio. La ejecución no: la orden se registra en el outbox (canal `job`), la procesa el
`intake-worker`, y la respuesta es `202 Accepted` con el trabajo `PENDING` y los contadores a cero. El
resultado se lee después con `GET /api/v1/intake/jobs/{job_id}`. Errores:
`404 Not Found` (`INTAKE_JOB_NOT_FOUND`); `400 Bad Request` (`INVALID_JOB_TRANSITION` si el
trabajo ya está `COMPLETED` o `FAILED`).

## Leads

Ciclo de vida completo del lead: listado, las dos vistas de detalle, asignación manual y descarte.

### `GET /api/v1/leads`

`MANAGER`, o una credencial de máquina por la cabecera `X-Api-Key` — la única ruta que la acepta
(`POST /agents/integration-credential` la emite; ver
[Autenticación de la mensajería](../eventos/autenticacion.md)). Devuelve el flujo completo de la
organización, así que un `AGENT` que lo alcanzara leería los leads de sus compañeros. Un `ADMIN`
recibe `403`: el plano de plataforma no alcanza dato operativo.

Filtra por `status`, `assigned_agent_id`, `group_id`, `source_id`, `q` y `updated_since`, todos
opcionales y combinables con `AND`:

| Parámetro | Tipo | Contra qué |
|---|---|---|
| `status` | string | `NEW` · `QUALIFIED` · `DISQUALIFIED` · `UNASSIGNED` · `ASSIGNED` · `DISCARDED` |
| `assigned_agent_id` | UUID | el asesor asignado. Un id inexistente devuelve página vacía, no `404` |
| `group_id` | UUID | el grupo del asesor asignado, resuelto por subconsulta |
| `source_id` | UUID | el origen del lead |
| `q` | string | búsqueda literal (`ILIKE '%...%'`) sobre `first_name`, `last_name`, `email` y `company` |
| `updated_since` | datetime ISO 8601 | `updated_at >= valor` — para que un consumidor recupere sólo lo que cambió desde la última vez que preguntó |

`q` no usa índice de texto completo ni `unaccent`: es un `ILIKE` sobre cuatro columnas, suficiente
para el volumen de un MVP docente. `%` y `_` viajan escapados, así que buscar `50%` encuentra un
`50%` literal, no "cualquier cosa que empiece por 50". Un `status` que no es uno de los seis
valores responde `400 Bad Request` (`INVALID_LEAD_STATUS`) en vez de ignorarse.

`updated_since` cambia también el orden de la página: `ORDER BY updated_at, id` en vez del
`created_at DESC, id` por defecto, para que paginar mientras se filtra por fecha de actualización no
salte una fila que se toca entre una página y la siguiente — justo el lead que el consumidor estaba
preguntando.

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

Filtra por `status` y `q`, con el mismo significado que en `GET /api/v1/leads`. **No** admite
`assigned_agent_id` ni `group_id`: aquí el asesor es siempre quien llama, y ofrecer un filtro que
sólo puede devolver todo o nada engañaría más que ayudaría. El orden es
`assigned_at DESC NULLS LAST, id` — no `created_at` — porque la vista es "mis leads por cuándo me
llegaron", y la columna es nula hasta que el lead se asigna.

### `GET /api/v1/leads/stats`

`MANAGER` únicamente: la foto de la organización entera, igual que `GET /api/v1/leads`. Un `AGENT`
recibe `403` (su vista es `GET /api/v1/leads/mine`, no un panel de organización), y también un
`ADMIN` (el plano de plataforma no alcanza dato operativo). Declarada antes de `/{lead_id}` en el
router, misma razón que `/mine`: si fuera después, `stats` caería en la ruta paramétrica y se
rechazaría como UUID inválido.

Los cinco indicadores que pinta el Panel, en una sola petición:

| Parámetro | Tipo | Contra qué |
|---|---|---|
| `from` | fecha | `leads.created_at >=` este valor. Ausente: sin límite inferior |
| `to` | fecha | `leads.created_at <=` este valor. Ausente: sin límite superior |

Ambos opcionales; sin ninguno, la cifra es "desde siempre". Nada se cachea ni se materializa: las
cuatro consultas viajan en una única transacción, así que las cinco cifras son la misma foto.

```json
{
  "total": 1240,
  "by_status": {
    "NEW": 12, "QUALIFIED": 300, "DISQUALIFIED": 88,
    "UNASSIGNED": 40, "ASSIGNED": 700, "DISCARDED": 100
  },
  "unassigned": 40,
  "pending_intake": 17,
  "load_by_agent": [
    {"agent_id": "5c8a1234-...", "name": "Ana Ruiz", "active_leads": 23}
  ]
}
```

`by_status` lleva siempre los seis valores de `LeadStatus`, con `0` donde no haya leads. `unassigned`
es redundante a propósito con `by_status["UNASSIGNED"]`: el indicador propio que pide el Panel, sin
que el cliente tenga que conocer ese nombre de estado interno. `pending_intake` suma los registros
de entrada en `PENDING` y `REJECTED` — los dos estados sobre los que un gestor tiene algo pendiente.
`load_by_agent` reutiliza la misma consulta que el motor de asignación (`active_load_by_agent`), con
el nombre de cada asesor añadido para que el Panel no necesite una segunda petición a
`GET /api/v1/agents`.

Errores: `400 Bad Request` (`INVALID_DATE_RANGE`, ver [API · Errores](api-errores.md)) si `from` es
posterior a `to`. Ver [ADR-0022](../decisiones/0022-agregados-del-panel.md).

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

```json
{
  "items": [
    {
      "id": "22222222-2222-2222-2222-222222222222",
      "name": "High Budget Rule",
      "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 10000}],
      "score_delta": 20, "priority": 0, "is_active": true
    }
  ],
  "total": 1, "limit": 100, "offset": 0, "has_more": false
}
```

### `PATCH /api/v1/rules/scoring/{rule_id}`

Todos los campos opcionales; los ausentes se dejan sin cambios. Reconstruye la regla entera por
`ScoringRule.create()`, igual que `PATCH /rules/disqualification/{rule_id}` — un `PATCH` no puede
dejar la regla en un estado que la creación habría rechazado, como un `name` vaciado o una lista de
`conditions` vacía.

Errores: `404 Not Found` (`SCORING_RULE_NOT_FOUND`); `400 Bad Request` (`INVALID_RULE_NAME`,
`INVALID_RULE_CONDITIONS`, `INVALID_RULE_FIELD`, `FIELD_NOT_SCORABLE`, `INVALID_RULE_VALUE`, si el
cuerpo trae `name` o `conditions`).

### `DELETE /api/v1/rules/scoring/{rule_id}`

Borra la fila de verdad, no la desactiva: a diferencia de las reglas de asignación y descalificación,
ninguna otra entidad referencia una regla de puntuación por `id` — el desglose de un lead ya puntuado
guarda nombre y puntos materializados, no una referencia viva. Para «apagar sin perder» está
`is_active`. Errores: `404 Not Found` (`SCORING_RULE_NOT_FOUND`).

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

Ordenadas por prioridad descendente — la misma con la que el motor las evalúa. Acepta `limit` y
`offset` como el resto de listas, pero el repositorio no pagina por sí mismo — el motor carga
siempre la organización entera en cada ingesta — así que el recorte ocurre en memoria, sobre la
lista completa ya traída. Deuda declarada: llevarlo a la consulta SQL exigiría ensanchar el puerto
del repositorio (`get_assignment_rules_by_tenant`), fuera del alcance de este cambio.

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
