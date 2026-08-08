# Puertos de Entrada, DTOs y Endpoints API

Los controladores de FastAPI actúan estrictamente como **Adaptadores de Entrada (Input Adapters)**. Tienen prohibido importar o acceder a repositorios de persistencia directamente; todas las operaciones se invocan a través de **Puertos de Entrada (Input Ports)** y **DTOs**.

---

## 🔐 Autenticación y Autorización

El sistema implementa seguridad mediante **JWT Bearer Tokens** y control de acceso basado en roles (RBAC) con aislamiento multitenant (Tenant Scoping).

### Mecanismo de Autenticación
- Los tokens de acceso se obtienen enviando credenciales a `POST /api/v1/auth/login`.
- Todos los endpoints protegidos requieren el encabezado HTTP: `Authorization: Bearer <token>`.

### Regla de Bootstrap
- Si la base de datos de agentes está vacía (`agents.count() == 0`), el endpoint `POST /api/v1/agents` permite la creación sin autenticación del **primer agente**, al cual se le asigna forzosamente el rol `ADMIN`.
- Una vez creado el primer agente, el endpoint exige autenticación y autorizaciones estándar.

### Los dos planos: plataforma y organización
Desde F0.5 el `ADMIN` y el resto de roles operan en planos disjuntos. Ninguna operación pertenece a los dos: el `ADMIN` administra organizaciones y sus gestores, y **no accede a ningún dato operativo** (leads, agentes, reglas) de ninguna organización, ni siquiera de la que acaba de crear.

### Roles y Permisos (`AgentRole`)
1. **`ADMIN`** — plano de plataforma:
   - No pertenece a ninguna organización (`tenant_id` siempre `None`).
   - Único que puede crear organizaciones (`POST /api/v1/tenants`), junto con su gestor inicial, en una sola transacción.
   - Lista organizaciones con el recuento de asesores de cada una, y puede activarlas/desactivarlas/renombrarlas.
   - Recibe `403 Forbidden` en todo endpoint operativo (`/api/v1/leads`, `/api/v1/agents`, `/api/v1/rules/*`), incluso estando autenticado.
2. **`MANAGER`** — plano de organización:
   - Acotado siempre a su propio `tenant_id`, tomado del token, nunca del cuerpo de la petición.
   - Puede crear agentes (`MANAGER` o `AGENT`) dentro de su propia organización. No puede crear otros `ADMIN`; el único nace del bootstrap.
   - Único rol que puede listar y consultar asesores (`GET /api/v1/agents`, `GET /api/v1/agents/{id}`), siempre acotado a su organización.
   - Puede gestionar y consultar grupos, reglas de scoring/asignación y leads de su organización.
   - Único rol que puede listar los leads de la organización (`GET /api/v1/leads`).
3. **`AGENT`**:
   - Usuario estándar de operaciones comerciales, acotado a su organización.
   - **No** puede listar asesores (`403`); consulta su propia identidad por [`GET /api/v1/auth/me`](#get-apiv1authme).
   - **No** puede listar los leads de la organización (`403` en `GET /api/v1/leads`): ese endpoint devuelve la cartera completa, y pertenecer a la organización no basta para leer la de los compañeros. Su vista propia es [`GET /api/v1/leads/mine`](#get-apiv1leadsmine), acotada a los leads que tiene asignados.
   - **No** puede crear agentes ni administrar reglas ni organizaciones.

### Aislamiento por Tenant (Tenant Scoping)
El `RequestContext` construido por [`get_request_context`](../../backend/src/infrastructure/adapters/input/api/dependencies.py) deriva la organización siempre de la identidad verificada en el token, nunca de la petición. Las dependencias [`require_organization_manager`](../../backend/src/infrastructure/adapters/input/api/dependencies.py) y [`require_platform_admin`](../../backend/src/infrastructure/adapters/input/api/dependencies.py) invocan a [`AuthorizationPolicy`](../../backend/src/domain/policies/authorization_policy.py), en el dominio, para exigir el rol correcto de cada plano. Un `ADMIN` no tiene forma de acceder a recursos de organización: su `tenant_id` es siempre `None`, y `AuthorizationPolicy.can_access_tenant` es `False` para él por diseño.

---

## 🚪 Puertos de Entrada (Input Ports)

Definidos en [`src/application/ports/input/`](../../backend/src/application/ports/input/):

- **`ReceiveIntakeInputPort`**: Fase 1 de la ingesta (individual o masiva) — persiste el payload como `IntakeRecord` y crea su `IntakeJob` en una transacción propia, y responde antes de intentar interpretarlo.
- **`ProcessIntakeJobInputPort`**: Fase 2 — lee los registros `PENDING` de un `IntakeJob` y los interpreta vía `IngestLeadInputPort`, en una transacción distinta de la recepción. La ejecuta un `BackgroundTasks` de FastAPI tras responder.
- **`IngestLeadInputPort`**: Interpreta un payload ya persistido — puntúa, asigna y emite eventos de dominio. Lo invocan `ProcessIntakeJobInputPort` (fase 2) y `PromoteIntakeRecordInputPort` (reintento manual desde la bandeja).
- **`ProcessBatchInputPort`**: Parsea un archivo CSV/Excel y crea un `IntakeRecord` `PENDING` por fila; no las procesa, eso lo hace `ProcessIntakeJobInputPort` a continuación.
- **`GetIntakeJobsInputPort` / `GetIntakeJobInputPort` / `ReprocessIntakeJobInputPort`**: Consulta paginada de trabajos de ingesta, detalle de uno con sus contadores, y reproceso de los registros que sigan `PENDING` en un trabajo interrumpido.
- **`GetLeadsInputPort`**: Consulta leads paginados por tenant.
- **`AssignLeadInputPort` / `DiscardLeadInputPort` / `GetMyLeadsInputPort` / `GetLeadInputPort`**: Ciclo de vida manual del lead — asignación/reasignación, descarte, la vista propia del asesor y el detalle con desglose de puntuación.
- **`CreateAgentInputPort` / `GetAgentsInputPort` / `GetAgentInputPort` / `UpdateAgentInputPort` / `DeactivateAgentInputPort`**: Gestión y consulta de agentes comerciales.
- **`CreateScoringRuleInputPort` / `GetScoringRulesInputPort`**: Creación y consulta de reglas de scoring.
- **`CreateAssignmentRuleInputPort` / `GetAssignmentRulesInputPort` / `UpdateAssignmentRuleInputPort` / `DeleteAssignmentRuleInputPort`**: CRUD de reglas de asignación (banda de puntuación, grupo/asesores destino, prioridad, estrategia).
- **`CreateSalesGroupInputPort` / `GetSalesGroupsInputPort` / `UpdateSalesGroupInputPort` / `DeleteSalesGroupInputPort`**: CRUD de grupos de ventas.
- **`PromoteIntakeRecordInputPort` / `DiscardIntakeRecordInputPort` / `GetIntakeRecordsInputPort`**: Bandeja de entrada de ingesta — corrige y promueve un registro rechazado, lo descarta, o lo lista filtrando por estado.
- **`CreateLeadSourceInputPort` / `GetLeadSourcesInputPort` / `UpdateLeadSourceInputPort` / `DeleteLeadSourceInputPort`**: CRUD de orígenes de leads (`LeadSource`).
- **`LoginInputPort`**: Autenticación de agentes y generación de JWT.
- **`CreateTenantInputPort` / `GetTenantsInputPort` / `UpdateTenantInputPort`**: Alta, listado y edición de organizaciones (plano de plataforma).

---

## 📬 Endpoints Disponibles

### 0. Health Check (`GET /health`)

Verificación de estado de la aplicación.

- **Autenticación**: Ninguna (Público).
- **Response (200 OK)**:
```json
{
  "status": "ok"
}
```

---

### 1. Autenticación (`/api/v1/auth`)

#### `POST /api/v1/auth/login`

Autentica a un agente comercial mediante correo y contraseña.

- **Autenticación**: Ninguna (Público).
- **Content-Type**: `application/x-www-form-urlencoded` (`OAuth2PasswordRequestForm`)
- **Body Parameters**:
  - `username` (string): Correo electrónico del agente.
  - `password` (string): Contraseña en texto plano.
- **Response (200 OK)** ([`LoginResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```
- **Errores**: `401 Unauthorized` (`INVALID_CREDENTIALS` si el correo o contraseña son incorrectos, o si su organización está desactivada).

#### `GET /api/v1/auth/me`

Devuelve la identidad del agente autenticado. Es lo que el frontend necesita para decidir qué panel mostrar, incluido el caso del `AGENT`, que no tiene ningún otro endpoint para conocer su propio rol u organización.

- **Autenticación**: Requerida (`Bearer Token`), cualquier rol.
- **Response (200 OK)** ([`CurrentUserResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
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
- Para un `ADMIN`, `tenant_id` y `tenant_name` son siempre `null`: no pertenece a ninguna organización.

---

### 2. Ingesta de Lead (`POST /api/v1/intake/leads/ingest`)

Recibe un lead y responde `202 Accepted` **antes** de interpretarlo. La fase 1 (recepción) persiste
el payload como `IntakeRecord` y crea su `IntakeJob` en una transacción propia; la fase 2
(procesamiento) corre después, en segundo plano y en una transacción distinta, y es la que puntúa,
asigna y emite eventos de dominio. Ningún fallo en la fase 2 puede ya borrar la constancia de haber
recibido — es el objetivo de F2d. El resultado se consulta por el `job_id` (sección 8) o por el
registro (sección 6).

> **Desde F2b, exige credencial.** El endpoint ya no toma la organización de la URL: la deriva del token, como el resto de la API. Cierra el defecto registrado en la sección 2.3 del spec del MVP.
>
> **Desde F2d, responde `202` en vez de `201`.** El cuerpo ya no lleva el resultado del
> procesamiento — puntuación, asesor asignado —, porque cuando la petición responde ese procesamiento
> todavía no ha corrido.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `require_organization_manager`. Sólo `MANAGER`. La organización sale del token; un `tenant_id` en el cuerpo se ignora.
- **Request Body** ([`IngestLeadRequest`](../../backend/src/infrastructure/adapters/input/api/schemas.py)). `email` es opcional. **Desde F2d el esquema ya no valida su formato**: esa comprobación duplicaba peor la del dominio y producía un `422` que descartaba el payload sin dejar rastro (decisión V1 del diseño de F2d). Un correo mal formado llega ahora al dominio, que lo rechaza dejando el registro — con su detalle — en la bandeja (sección 6) en vez de perderlo.
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
- **Response (202 Accepted)** ([`IntakeAcceptedResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "record_ids": ["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
  "status": "PENDING"
}
```
- **Errores**: `401 Unauthorized`; `403 Forbidden` (un `AGENT` no ingesta); `404 Not Found` (`SOURCE_NOT_FOUND`, si la organización no tiene un origen `MANUAL_FORM` activo). Un payload que no interpreta ya **no** responde con un error síncrono: la petición igual responde `202`, y el registro queda `REJECTED` en la bandeja (sección 6) con el trabajo `COMPLETED` y `failed: 1`.

---

### 3. Carga Masiva de Leads (`POST /api/v1/intake/leads/batch-upload`)

Recibe un archivo CSV o Excel y responde `202 Accepted` **antes** de parsearlo. La fase 1 crea el
`IntakeJob` en su propia transacción; la fase 2 corre después, en segundo plano, parsea el fichero,
crea un `IntakeRecord` `PENDING` por fila y las procesa por el mismo pipeline que la ingesta
individual (sección 2) — la fila que falla no se pierde, queda como su propio `IntakeRecord` en la
bandeja (sección 6).

> **Desde F2d, responde `202` en vez de `200`.** El cuerpo ya no lleva `total_rows`,
> `successful_ingestions` ni `failed_rows`: el fichero todavía no se ha parseado cuando la petición
> responde. Esos datos se consultan después por el `job_id` (sección 8); sus filas, en la bandeja
> filtrada por `job_id` (sección 6). Ahí la fila fallida se identifica **por contenido** — su
> correo, por ejemplo — y no por `row_number`: `IntakeRecord` no guarda la posición original en el
> fichero.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `require_organization_manager`. Sólo `MANAGER`.
- **Form Data**: `file` (`UploadFile`, Multipart/form-data).
- **Response (202 Accepted)** ([`IntakeAcceptedResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "record_ids": [],
  "status": "PENDING"
}
```
`record_ids` siempre vacío aquí: las filas todavía no existen cuando la petición se acepta, sólo el
`IntakeJob` — la fase 2 es la que las crea al parsear el fichero.
- **Errores**: `401 Unauthorized`; `403 Forbidden`; `404 Not Found` (`SOURCE_NOT_FOUND`, si la
  organización no tiene un origen `FILE_UPLOAD` activo). Un fichero ilegible tampoco responde con un
  error: la petición ya contestó `202`, y el trabajo queda `FAILED` sin ningún registro (sección 8).

---

### 4. Listar Leads (`GET /api/v1/leads`)

Consulta de leads paginados. La organización sale del token, nunca de la URL. **Sólo para el gestor:** este endpoint devuelve el flujo completo de la organización, así que un asesor que lo alcanzara leería los leads de sus compañeros. La vista del asesor es [`GET /api/v1/leads/mine`](#get-apiv1leadsmine), en la sección 5.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `require_organization_manager`. Sólo `MANAGER`. Un `ADMIN` recibe `403`: el plano de plataforma no alcanza dato operativo.
- **Path Parameters**: ninguno. La organización se deriva del token.
- **Query Parameters**: `limit` (int, default=100), `offset` (int, default=0).
- **Response (200 OK)** ([`PaginatedLeadsResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "items": [
    {
      "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
      "first_name": "Maria",
      "last_name": "Gomez",
      "email": "mgomez@techcorp.com",
      "company": "TechCorp",
      "budget": 15000.0,
      "industry": "Technology",
      "custom_attributes": {"employee_count": 150},
      "phone": "+573001234567",
      "score": 45,
      "status": "QUALIFIED",
      "assigned_agent_id": "11111111-1111-1111-1111-111111111111",
      "created_at": "2026-08-05T10:00:00+00:00"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0,
  "has_more": false
}
```
- **Errores**: `401 Unauthorized`, `403 Forbidden`.

---

### 5. Ciclo de Vida del Lead (`/api/v1/leads`)

Asignación manual, descarte y las dos vistas de detalle que completan el ciclo iniciado en la ingesta (sección 2). **Orden de declaración:** `GET /leads/mine` está registrado antes que `GET /leads/{lead_id}` porque FastAPI resuelve rutas en el orden en que se declaran — al revés, `mine` caería en la ruta paramétrica y fallaría al intentar interpretarlo como UUID.

#### `GET /api/v1/leads/mine`
Los leads asignados al agente autenticado. Es la única vía que tiene un `AGENT` hacia sus propios leads, ya que `GET /api/v1/leads` es sólo del gestor.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER` o `AGENT`, cualquiera con organización propia. Un `ADMIN` recibe `403 Forbidden`: no tiene `tenant_id`.
- **Query Parameters**: `limit` (int, default=100), `offset` (int, default=0).
- **Response (200 OK)** ([`PaginatedLeadsResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): misma forma que `GET /api/v1/leads`, acotada a los leads cuyo `assigned_agent_id` es el del llamante.

#### `GET /api/v1/leads/{lead_id}`
Detalle de un lead, incluido el desglose de las reglas de scoring que se le aplicaron.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER` alcanza cualquier lead de su organización; un `AGENT` sólo el suyo.
- **Path Parameters**: `lead_id` (UUID).
- **Response (200 OK)** ([`LeadDetailResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): añade `score_breakdown` (una entrada `{rule_id, name, score_delta}` por cada regla de scoring que se cumplió), `assigned_at` y `discard_reason` sobre los campos de `LeadResponse`.
```json
{
  "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "first_name": "Maria",
  "last_name": "Gomez",
  "email": "mgomez@techcorp.com",
  "company": "TechCorp",
  "budget": 15000.0,
  "industry": "Technology",
  "custom_attributes": {"employee_count": 150},
  "phone": "+573001234567",
  "score": 50,
  "score_breakdown": [
    {"rule_id": "22222222-2222-2222-2222-222222222222", "name": "Tech leads", "score_delta": 50}
  ],
  "status": "UNASSIGNED",
  "assigned_agent_id": null,
  "assigned_at": null,
  "discard_reason": null,
  "created_at": "2026-08-05T10:00:00+00:00"
}
```
- **Errores**: `404 Not Found` (`LEAD_NOT_FOUND`) si el identificador no existe, si pertenece a otra organización, o si un `AGENT` pide el detalle de un lead ajeno — nunca `403`, para no confirmarle que ese lead existe en su organización.

#### `POST /api/v1/leads/{lead_id}/assign`
Asigna el lead a un asesor a mano. Si el lead ya está `ASSIGNED`, reasigna: es la misma operación para el gestor sin importar el estado de partida, y la entidad decide internamente entre `assign_to` y `reassign_to`.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `lead_id` (UUID).
- **Request Body** ([`AssignLeadRequest`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "agent_id": "11111111-1111-1111-1111-111111111111"
}
```
- **Response (200 OK)** ([`LeadDetailResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)) con `status: "ASSIGNED"` y `assigned_at` no nulo.
- **Errores**: `404 Not Found` (`LEAD_NOT_FOUND` o `AGENT_NOT_FOUND` si el lead o el asesor no existen o pertenecen a otra organización; el asesor se resuelve acotado a la organización del gestor, así que uno ajeno se lee como inexistente, nunca como `403`); `400 Bad Request` (`INVALID_LEAD_TRANSITION` si el lead está en un estado no asignable, como `DISCARDED`).

#### `POST /api/v1/leads/{lead_id}/discard`
Descarta el lead con un motivo obligatorio.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `lead_id` (UUID).
- **Request Body** ([`DiscardLeadRequest`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "reason": "Presupuesto insuficiente"
}
```
- **Response (200 OK)** ([`LeadDetailResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)) con `status: "DISCARDED"` y `discard_reason` con el motivo enviado.
- **Errores**: `404 Not Found` (`LEAD_NOT_FOUND`); `400 Bad Request` (`DISCARD_WITHOUT_REASON` si el motivo llega vacío).

---

### 6. Bandeja de Entrada (`/api/v1/intake/records`)

Todo payload que llega a la ingesta (sección 2 y 3) se persiste como `IntakeRecord` **antes** de intentar interpretarlo, así que nada de lo que no valida se pierde: queda aquí, con el motivo exacto del fallo, para que el gestor lo corrija y lo reintente o lo descarte.

#### `GET /api/v1/intake/records`
Lista los registros de ingesta de la organización, paginados.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Query Parameters**: `status` (opcional: `PENDING` · `PROMOTED` · `REJECTED` · `DISCARDED`), `limit` (int, default=100), `offset` (int, default=0).
- **Response (200 OK)** ([`IntakeRecordsPageResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "items": [
    {
      "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "source_id": "22222222-2222-2222-2222-222222222222",
      "status": "REJECTED",
      "payload": {"first_name": "Jane", "last_name": "Doe", "email": "jane@@example.com", "company": "Acme", "industry": "Tech", "budget": 3000},
      "errors": [
        {"field": "email", "message": "Formato de correo electrónico inválido", "received_value": "jane@@example.com", "error_code": "INVALID_EMAIL"}
      ],
      "received_at": "2026-08-08T10:00:00+00:00",
      "processed_at": "2026-08-08T10:00:00+00:00",
      "lead_id": null
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0,
  "has_more": false
}
```
- **Errores**: `401 Unauthorized`; `403 Forbidden`.

#### `POST /api/v1/intake/records/{record_id}/promote`
Reintenta un registro con el `payload` corregido. Si valida, genera el lead y marca el registro como `PROMOTED` reutilizando la misma fila — nunca añade una segunda.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `record_id` (UUID).
- **Request Body** ([`PromoteIntakeRecordRequest`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "payload": {"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com", "company": "Acme", "industry": "Tech", "budget": 3000}
}
```
- **Response (200 OK)** ([`LeadProcessedResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): misma forma que la ingesta individual (sección 2).
- **Response Error (400 Bad Request)**: si el payload corregido sigue sin validar, el registro permanece `REJECTED` con los nuevos errores; misma forma que el error de la sección 2.
- **Errores**: `404 Not Found` (`INTAKE_RECORD_NOT_FOUND` si no existe o pertenece a otra organización); `400 Bad Request` (`INVALID_INTAKE_TRANSITION` si el registro no está en un estado promovible — por ejemplo, ya `PROMOTED` —, o el `error_code` de dominio si el payload corregido sigue sin validar).

#### `POST /api/v1/intake/records/{record_id}/discard`
Descarta el registro: el gestor decide no recuperarlo.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `record_id` (UUID).
- **Response**: `204 No Content`.
- **Errores**: `404 Not Found` (`INTAKE_RECORD_NOT_FOUND`); `400 Bad Request` (`INVALID_INTAKE_TRANSITION` si ya está `PROMOTED`).

---

### 7. Orígenes de Leads (`/api/v1/sources`)

`LeadSource` es la entidad que responde «¿de dónde vienen mis leads?»: cada lead ingerido lleva el `source_id` de la fuente por la que entró. Al crear una organización nacen automáticamente dos fuentes, `MANUAL_FORM` y `FILE_UPLOAD`, que son las que usan el formulario individual y la carga de ficheros.

#### `POST /api/v1/sources`
Crea una fuente en la organización del gestor autenticado.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Request Body** ([`LeadSourceCreate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "name": "Facebook Lead Ads — Campaña Verano",
  "kind": "MANUAL_FORM",
  "field_mapping": {}
}
```
- **Response (201 Created)** ([`LeadSourceResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "id": "22222222-2222-2222-2222-222222222222",
  "name": "Facebook Lead Ads — Campaña Verano",
  "kind": "MANUAL_FORM",
  "field_mapping": {},
  "is_active": true,
  "created_at": "2026-08-08T10:00:00+00:00"
}
```
- **Errores**: `400 Bad Request` (`SOURCE_ALREADY_EXISTS` si ya existe una fuente con ese nombre en la organización; el mismo nombre sí se acepta en otra organización).

#### `GET /api/v1/sources`
Lista las fuentes de la organización, paginadas.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Query Parameters**: `limit` (int, default=100), `offset` (int, default=0).
- **Response (200 OK)** ([`PaginatedSourcesResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): misma forma que las demás listas paginadas.

#### `PATCH /api/v1/sources/{source_id}`
Actualiza nombre, mapeo de campos o estado de una fuente. Todos los campos son opcionales.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `source_id` (UUID).
- **Request Body** ([`LeadSourceUpdate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "is_active": false
}
```
- **Response (200 OK)** ([`LeadSourceResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)).
- **Errores**: `404 Not Found` (`SOURCE_NOT_FOUND` si no existe o pertenece a otra organización).

#### `DELETE /api/v1/sources/{source_id}`
Borra la fuente, sólo si ningún lead la referencia.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `source_id` (UUID).
- **Response**: `204 No Content`.
- **Errores**: `404 Not Found` (`SOURCE_NOT_FOUND`); `400 Bad Request` (`SOURCE_IN_USE` si tiene leads asociados — no se borra en silencio la trazabilidad de esos leads).

---

### 8. Trabajos de Ingesta (`/api/v1/intake/jobs`)

`IntakeJob` es lo que la fase 1 de la ingesta (secciones 2 y 3) crea y responde como `job_id`: por él
se sabe si la fase 2 —el procesamiento en segundo plano— ya terminó, y cómo le fue.

#### `GET /api/v1/intake/jobs`
Lista los trabajos de ingesta de la organización, paginados.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Query Parameters**: `status` (opcional: `PENDING` · `PROCESSING` · `COMPLETED` · `FAILED`), `limit` (int, default=100), `offset` (int, default=0).
- **Response (200 OK)** ([`IntakeJobsPageResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "items": [
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
  ],
  "total": 1,
  "limit": 100,
  "offset": 0,
  "has_more": false
}
```
- **Errores**: `401 Unauthorized`; `403 Forbidden`; `400 Bad Request` (`INVALID_JOB_STATUS` si `status` no es un valor conocido).

#### `GET /api/v1/intake/jobs/{job_id}`
Detalle de un trabajo: estado y contadores. `total_items` es `null` en una carga masiva hasta que la
fase 2 parsea el fichero — no se conoce todavía al aceptar la petición (sección 3).

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `job_id` (UUID).
- **Response (200 OK)** ([`IntakeJobResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): misma forma que un elemento de la lista anterior.
- **Errores**: `404 Not Found` (`INTAKE_JOB_NOT_FOUND` si no existe o pertenece a otra organización — nunca `403`, por la misma razón que el resto de la API).

#### `POST /api/v1/intake/jobs/{job_id}/reprocess`
Relanza un trabajo que se quedó a medias — interrumpido antes de que la fase 2 llegara a correr, o
detenido por un fallo imprevisto. Reinicia sus contadores y vuelve a leer únicamente los
`IntakeRecord` que sigan `PENDING`: los que ya llegaron a un estado terminal no se tocan, así que
reprocesar dos veces nunca duplica un lead ni cuenta un registro dos veces — es la propiedad que hará
segura la cola cuando exista (fuera de alcance de F2d).

No corre en segundo plano como la ingesta (secciones 2 y 3): la comprobación de propiedad y de
estado es síncrona, porque una excepción lanzada dentro de una tarea de fondo ya no puede convertirse
en un `404`/`400` limpio una vez que la respuesta ha empezado a enviarse — se pierde como error de
servidor sin que el llamante lo vea. El propio reproceso queda acotado al mismo límite de registros
por ejecución que el procesamiento normal.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `job_id` (UUID).
- **Response (202 Accepted)** ([`IntakeJobResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): el trabajo ya en su estado final, `COMPLETED` o `FAILED`.
- **Errores**: `404 Not Found` (`INTAKE_JOB_NOT_FOUND`); `400 Bad Request` (`INVALID_JOB_TRANSITION` si el trabajo ya está `COMPLETED` o `FAILED` — un trabajo terminado no se reprocesa).

---

### 9. Plano de Plataforma — Organizaciones (`/api/v1/tenants`)

Todos los endpoints de esta sección exigen `Depends(require_platform_admin)`: sólo un `ADMIN` los alcanza. Un `MANAGER` o `AGENT` recibe `403 Forbidden`.

#### `POST /api/v1/tenants`
Crea una organización junto con su gestor inicial, en una sola transacción (decisión E2 del diseño de F0.5): si la creación del gestor falla — por ejemplo por correo duplicado —, la organización tampoco queda creada.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `ADMIN`.
- **Request Body** ([`TenantCreate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "name": "Acme Corp",
  "manager": {
    "name": "Ana Ruiz",
    "email": "ana@acme.test",
    "password": "securepassword123"
  }
}
```
- **Response (201 Created)** ([`TenantResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
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
- **Errores**: `400 Bad Request` (`TENANT_ALREADY_EXISTS` si el nombre ya existe como organización; `EMAIL_ALREADY_EXISTS` si el correo del gestor ya está en uso).

#### `GET /api/v1/tenants`
Lista organizaciones paginadas. Cada elemento lleva `agent_count` —el recuento de asesores activos— pero no `manager`: es un agregado, no una lista de identidades (decisión E3).

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `ADMIN`.
- **Query Parameters**: `limit` (int, default=100), `offset` (int, default=0).
- **Response (200 OK)** ([`PaginatedTenantsResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "items": [
    {
      "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
      "name": "Acme Corp",
      "slug": "acme-corp",
      "is_active": true,
      "created_at": "2026-08-07T10:00:00+00:00",
      "agent_count": 3,
      "manager": null
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0,
  "has_more": false
}
```

#### `PATCH /api/v1/tenants/{tenant_id}`
Renombra y/o activa/desactiva una organización. Desactivarla (`is_active: false`) desactiva en cascada a todos sus usuarios (decisión E7): pierden acceso de inmediato, aunque su token siga sin expirar, porque `POST /auth/login` vuelve a comprobar el estado en base de datos.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `ADMIN`.
- **Path Parameters**: `tenant_id` (UUID).
- **Request Body** ([`TenantUpdate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): `name` y/o `is_active`, ambos opcionales.
```json
{
  "is_active": false
}
```
- **Response (200 OK)** ([`TenantResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "is_active": false,
  "created_at": "2026-08-07T10:00:00+00:00",
  "agent_count": null,
  "manager": null
}
```
- **Errores**: `404 Not Found` (`TENANT_NOT_FOUND`).

---

### 10. Gestión de Agentes (`/api/v1/agents`)

Restringido al plano de organización: un `ADMIN` recibe `403 Forbidden` en los tres endpoints.

#### `POST /api/v1/agents`
Crea un nuevo agente de ventas.

- **Autenticación**: Requerida (`Bearer Token`), excepto en estado Bootstrap (base de datos sin agentes: el primer agente creado es forzosamente `ADMIN`).
- **Permisos**: `MANAGER`, y sólo dentro de su propia organización. No puede crear otros `ADMIN`; el único nace del bootstrap.
- **Request Body** ([`AgentCreate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)). Sin `tenant_id`: la organización es siempre la del gestor autenticado, tomada del contexto, nunca de la petición. `group_id` (UUID, opcional) reemplazó al antiguo `team` de F0: un string libre no se puede renombrar sin huérfanos y no permite expresar capacidad. `active_leads_count` desapareció por completo — la carga de un asesor se deriva de los leads que tiene realmente asignados (`GET /api/v1/leads` a través del propietario, o el campo interno `active_load_by_agent`), nunca de un contador de mano.
```json
{
  "name": "Carlos Ruiz",
  "email": "cruiz@techcorp.com",
  "group_id": "22222222-2222-2222-2222-222222222222",
  "is_active": true,
  "password": "securepassword123",
  "role": "AGENT"
}
```
- **Response (201 Created)** ([`AgentResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
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

#### `GET /api/v1/agents`
Obtiene la lista paginada de agentes comerciales de la propia organización. Cierra la fuga cross-tenant que tenía antes de F0.5: ya no basta con estar autenticado, y nunca devuelve asesores de otra organización.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`. Un `AGENT` recibe `403 Forbidden`.
- **Query Parameters**: `group_id` (UUID, opcional), `limit` (int, default=100), `offset` (int, default=0).
- **Response (200 OK)** ([`PaginatedAgentsResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "items": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "name": "Carlos Ruiz",
      "email": "cruiz@techcorp.com",
      "group_id": "22222222-2222-2222-2222-222222222222",
      "is_active": true,
      "role": "AGENT",
      "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0,
  "has_more": false
}
```

#### `GET /api/v1/agents/{agent_id}`
Obtiene el detalle de un agente por su UUID, sólo si pertenece a la propia organización.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `agent_id` (UUID).
- **Response (200 OK)** ([`AgentResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
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
- **Errores**: `404 Not Found` (`AGENT_NOT_FOUND`) tanto si el identificador no existe como si pertenece a otra organización — nunca `403`, para no confirmar con el código de estado que ese identificador existe en otro sitio.

#### `PATCH /api/v1/agents/{agent_id}`
Cambia el nombre y/o el grupo de un asesor.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `agent_id` (UUID).
- **Request Body** ([`AgentUpdate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): `name` y/o `group_id`, ambos opcionales.
```json
{
  "group_id": "33333333-3333-3333-3333-333333333333"
}
```
- **Response (200 OK)** ([`AgentResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)).
- **Errores**: `404 Not Found` (`AGENT_NOT_FOUND` si el asesor no existe o es de otra organización; `GROUP_NOT_FOUND` si `group_id` no existe o pertenece a otra organización).

#### `DELETE /api/v1/agents/{agent_id}`
**Desactiva** al asesor; no lo borra. Los leads que ya tiene asignados siguen apuntando a su identificador, y borrar la fila los dejaría con una referencia rota. Un asesor desactivado deja de recibir asignaciones automáticas (`get_available_agents` sólo devuelve activos) pero su historial permanece legible.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `agent_id` (UUID).
- **Response (200 OK)** ([`AgentResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)) con `is_active: false`.
- **Errores**: `404 Not Found` (`AGENT_NOT_FOUND`).

---

### 11. Grupos de Ventas (`/api/v1/groups`)

Un grupo agrupa asesores bajo una política de asignación compartida (estrategia por defecto, capacidad por asesor). Reemplaza al antiguo campo `team` de texto libre. Los cuatro endpoints exigen `Depends(require_organization_manager)`: un `ADMIN` o un `AGENT` reciben `403 Forbidden`.

#### `POST /api/v1/groups`
Crea un grupo en la organización del gestor autenticado.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Request Body** ([`SalesGroupCreate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "name": "Enterprise",
  "description": "Cuentas grandes",
  "default_strategy": "LOWEST_LOAD",
  "capacity_per_agent": 5
}
```
- **Response (201 Created)** ([`SalesGroupResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "id": "22222222-2222-2222-2222-222222222222",
  "name": "Enterprise",
  "description": "Cuentas grandes",
  "default_strategy": "LOWEST_LOAD",
  "capacity_per_agent": 5,
  "is_active": true,
  "agent_count": null
}
```
- **Errores**: `400 Bad Request` (`GROUP_ALREADY_EXISTS` si ya existe un grupo con ese nombre en la organización; el mismo nombre sí se acepta en otra organización).

#### `GET /api/v1/groups`
Lista los grupos de la organización, cada uno con el recuento de asesores que tiene actualmente.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Query Parameters**: `limit` (int, default=100), `offset` (int, default=0).
- **Response (200 OK)** ([`PaginatedGroupsResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): igual forma que las demás listas paginadas, con `agent_count` poblado en cada elemento.

#### `PATCH /api/v1/groups/{group_id}`
Actualiza nombre, descripción, estrategia por defecto, capacidad o estado de un grupo. Desactivar un grupo (`is_active: false`) **no** desactiva a sus asesores — dejan de recibir asignaciones automáticas pero siguen pudiendo atender los leads que ya tienen; es la diferencia con desactivar una organización, que sí corta el acceso.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `group_id` (UUID).
- **Request Body** ([`SalesGroupUpdate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): todos los campos opcionales; un campo ausente se deja sin cambios.
- **Response (200 OK)** ([`SalesGroupResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)).
- **Errores**: `404 Not Found` (`GROUP_NOT_FOUND` si el grupo no existe o pertenece a otra organización).

#### `DELETE /api/v1/groups/{group_id}`
Borra el grupo. Sus asesores **no** se borran: quedan sin grupo (`group_id: null`), tanto en Postgres (FK `ON DELETE SET NULL`, migración 003) como en el caso de prueba en memoria.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `group_id` (UUID).
- **Response**: `204 No Content`.
- **Errores**: `404 Not Found` (`GROUP_NOT_FOUND`).

---

### 12. Gestión de Reglas (`/api/v1/rules`)

Todos los endpoints de reglas exigen `Depends(require_organization_manager)`; el tenant sale siempre del token, nunca de la URL o del cuerpo.

Desde F2c, las condiciones de toda regla —puntuación, asignación o descalificación— viajan como una
lista de `Criterion` (`{"field", "operator", "value"}`), nunca como un `field`/`operator`/`value`
suelto en la regla. Una regla se cumple cuando se cumplen **todas** sus condiciones; no hay `OR`. Los
operadores `IS_EMPTY` / `IS_NOT_EMPTY` ignoran `value`. La lista blanca de campos evaluables
(`EVALUABLE_FIELDS` en [`criterion.py`](../../backend/src/domain/value_objects/criterion.py)) es la
misma en las tres etapas.

#### `POST /api/v1/rules/scoring`
Crea una regla de scoring para la organización del gestor autenticado. Suma `score_delta` cuando se
cumplen **todas** sus condiciones.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Request Body** ([`ScoringRuleCreate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "name": "High Budget Rule",
  "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 10000}],
  "score_delta": 20
}
```
- **Response (201 Created)** ([`ScoringRuleResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "id": "22222222-2222-2222-2222-222222222222",
  "name": "High Budget Rule",
  "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 10000}],
  "score_delta": 20,
  "priority": 0,
  "is_active": true
}
```
- **Errores**: `400 Bad Request` (`INVALID_RULE_FIELD` si algún campo llega vacío; `FIELD_NOT_SCORABLE` si no está en la lista blanca; `INVALID_RULE_VALUE` si el operador `IN` no recibe una lista).

#### `GET /api/v1/rules/scoring`
Obtiene las reglas de scoring de la organización del gestor autenticado.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Response (200 OK)** (`List[`[`ScoringRuleResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)`]`):
```json
[
  {
    "id": "22222222-2222-2222-2222-222222222222",
    "name": "High Budget Rule",
    "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 10000}],
    "score_delta": 20,
    "priority": 0,
    "is_active": true
  }
]
```

#### `POST /api/v1/rules/assignment`
Crea una regla de asignación. Tiene nombre (mostrable en una interfaz), banda con techo (`max_score`, no sólo `min_score`), prioridad explícita para desempatar bandas solapadas, un `rr_cursor` que persiste en base de datos en vez de vivir en memoria y, desde F2c, condiciones sobre atributos del lead — el eje de canal o zona que la banda por sí sola no puede expresar.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Request Body** ([`AssignmentRuleCreate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)). La regla debe apuntar a un grupo (`target_group_id`), a asesores concretos (`target_agent_ids`) o a ambos; `agent_match_mode` decide si son la unión (`ANY`, por defecto) o la intersección (`ONLY`) con el grupo. `strategy` es opcional: si se omite, se usa la estrategia por defecto del grupo destino. `conditions` es opcional y por defecto vacía: una regla sin condiciones discrimina sólo por banda, que es como se comportaban todas antes de F2c.
```json
{
  "name": "Enterprise band",
  "min_score": 70,
  "max_score": 100,
  "target_group_id": "22222222-2222-2222-2222-222222222222",
  "agent_match_mode": "ANY",
  "strategy": "ROUND_ROBIN",
  "priority": 10,
  "conditions": [{"field": "custom_attributes.channel", "operator": "EQUALS", "value": "referral"}]
}
```
- **Response (201 Created)** ([`AssignmentRuleResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "id": "33333333-3333-3333-3333-333333333333",
  "name": "Enterprise band",
  "min_score": 70,
  "max_score": 100,
  "target_group_id": "22222222-2222-2222-2222-222222222222",
  "target_agent_ids": [],
  "agent_match_mode": "ANY",
  "strategy": "ROUND_ROBIN",
  "priority": 10,
  "is_active": true,
  "rr_cursor": 0,
  "conditions": [{"field": "custom_attributes.channel", "operator": "EQUALS", "value": "referral"}]
}
```

#### `GET /api/v1/rules/assignment`
Lista las reglas de asignación de la organización, ordenadas por prioridad descendente (la misma prioridad con la que el motor las evalúa).

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Response (200 OK)** ([`PaginatedAssignmentRulesResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): el motor carga todas las reglas en cada ingesta, así que esta lista no pagina de verdad — siempre es una única página con todo.

#### `PATCH /api/v1/rules/assignment/{rule_id}`
Actualiza una regla existente. Todos los campos son opcionales y se dejan sin cambios si se omiten; `rr_cursor` no es uno de ellos a propósito, así que una actualización parcial nunca reinicia una rotación en curso.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `rule_id` (UUID).
- **Request Body** ([`AssignmentRuleUpdate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)).
- **Response (200 OK)** ([`AssignmentRuleResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)).
- **Errores**: `404 Not Found` (`ASSIGNMENT_RULE_NOT_FOUND` si la regla no existe o pertenece a otra organización).

#### `DELETE /api/v1/rules/assignment/{rule_id}`
Borra la regla. No toca a los asesores que nombraba ni a los que pertenecían a su grupo destino.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `rule_id` (UUID).
- **Response**: `204 No Content`.
- **Errores**: `404 Not Found` (`ASSIGNMENT_RULE_NOT_FOUND`).

#### `POST /api/v1/rules/disqualification`
Crea una regla de descalificación — la etapa de viabilidad (F2c). Se evalúa **antes** de puntuar y **corta el flujo**: si se cumple, el lead queda `DISQUALIFIED` con `name` como motivo, y no llega a puntuarse ni a repartirse.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Request Body** ([`DisqualificationRuleCreate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)). `conditions` no puede llegar vacía (R3): una regla sin condiciones se cumple siempre y descalificaría a toda la organización.
```json
{
  "name": "Sin vía de contacto",
  "conditions": [
    {"field": "phone", "operator": "IS_EMPTY"},
    {"field": "email", "operator": "IS_EMPTY"}
  ],
  "priority": 0
}
```
- **Response (201 Created)** ([`DisqualificationRuleResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "id": "44444444-4444-4444-4444-444444444444",
  "name": "Sin vía de contacto",
  "conditions": [
    {"field": "phone", "operator": "IS_EMPTY", "value": null},
    {"field": "email", "operator": "IS_EMPTY", "value": null}
  ],
  "priority": 0,
  "is_active": true
}
```
- **Errores**: `400 Bad Request` (`INVALID_RULE_NAME` si el nombre llega vacío; `INVALID_RULE_CONDITIONS` si `conditions` llega vacía).

#### `GET /api/v1/rules/disqualification`
Lista las reglas de descalificación de la organización, paginadas.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Query Parameters**: `limit` (int, default=100), `offset` (int, default=0).
- **Response (200 OK)** ([`PaginatedDisqualificationRulesResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)): misma forma que las demás listas paginadas, con `items` de tipo `DisqualificationRuleResponse`.

#### `PATCH /api/v1/rules/disqualification/{rule_id}`
Actualiza una regla existente. Todos los campos son opcionales y se dejan sin cambios si se omiten, con la misma validación que `create()`: un `name` o `conditions` enviados vacíos se rechazan en vez de guardarse.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `rule_id` (UUID).
- **Request Body** ([`DisqualificationRuleUpdate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)).
- **Response (200 OK)** ([`DisqualificationRuleResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)).
- **Errores**: `404 Not Found` (`DISQUALIFICATION_RULE_NOT_FOUND` si la regla no existe o pertenece a otra organización); `400 Bad Request` (`INVALID_RULE_NAME`, `INVALID_RULE_CONDITIONS`).

#### `DELETE /api/v1/rules/disqualification/{rule_id}`
Borra la regla.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`.
- **Path Parameters**: `rule_id` (UUID).
- **Response**: `204 No Content`.
- **Errores**: `404 Not Found` (`DISQUALIFICATION_RULE_NOT_FOUND`).
