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
   - Puede gestionar y consultar reglas de scoring/routing y leads de su organización.
   - Único rol que puede listar los leads de la organización (`GET /api/v1/leads`).
3. **`AGENT`**:
   - Usuario estándar de operaciones comerciales, acotado a su organización.
   - **No** puede listar asesores (`403`); consulta su propia identidad por [`GET /api/v1/auth/me`](#get-apiv1authme).
   - **No** puede listar los leads de la organización (`403` en `GET /api/v1/leads`): ese endpoint devuelve la cartera completa, y pertenecer a la organización no basta para leer la de los compañeros. Su vista propia será `GET /api/v1/leads/mine`, pendiente de F2.
   - **No** puede crear agentes ni administrar reglas ni organizaciones.

### Aislamiento por Tenant (Tenant Scoping)
El `RequestContext` construido por [`get_request_context`](../../backend/src/infrastructure/adapters/input/api/dependencies.py) deriva la organización siempre de la identidad verificada en el token, nunca de la petición. Las dependencias [`require_organization_manager`](../../backend/src/infrastructure/adapters/input/api/dependencies.py) y [`require_platform_admin`](../../backend/src/infrastructure/adapters/input/api/dependencies.py) invocan a [`AuthorizationPolicy`](../../backend/src/domain/policies/authorization_policy.py), en el dominio, para exigir el rol correcto de cada plano. Un `ADMIN` no tiene forma de acceder a recursos de organización: su `tenant_id` es siempre `None`, y `AuthorizationPolicy.can_access_tenant` es `False` para él por diseño.

---

## 🚪 Puertos de Entrada (Input Ports)

Definidos en [`src/application/ports/input/`](../../backend/src/application/ports/input/):

- **`IngestLeadInputPort`**: Procesa la ingesta de un lead individual.
- **`ProcessBatchInputPort`**: Procesa la ingesta masiva de leads desde archivos CSV/Excel.
- **`GetLeadsInputPort`**: Consulta leads paginados por tenant.
- **`CreateAgentInputPort` / `GetAgentsInputPort` / `GetAgentInputPort`**: Gestión y consulta de agentes comerciales.
- **`CreateScoringRuleInputPort` / `GetScoringRulesInputPort`**: Creación y consulta de reglas de scoring.
- **`CreateRoutingRuleInputPort` / `GetRoutingRulesInputPort`**: Creación y consulta de reglas de ruteo.
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

### 2. Ingesta de Lead (`POST /api/v1/tenants/{tenant_id}/leads/ingest`)

Recibe un comando de ingesta de lead, evalúa reglas de scoring y routing, asigna un agente y emite eventos de dominio.

- **Autenticación**: Ninguna por diseño (endpoint de ingesta pública).
- **Path Parameters**: `tenant_id` (UUID).
- **Request Body** ([`IngestLeadRequest`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
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
- **Response (201 Created)** ([`LeadProcessedResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "lead_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "QUALIFIED",
  "score": 45,
  "assigned_agent_id": "11111111-1111-1111-1111-111111111111",
  "applied_rules_count": 2,
  "webhook_dispatched": true,
  "error": null,
  "error_code": null
}
```
- **Response Error (400 Bad Request)** (si falla la validación de dominio a nivel de fila):
```json
{
  "error": true,
  "error_code": "INVALID_EMAIL",
  "message": "Formato de correo electrónico inválido"
}
```

---

### 3. Carga Masiva de Leads (`POST /api/v1/tenants/{tenant_id}/leads/batch-upload`)

Procesa un archivo CSV o Excel para la ingesta masiva de leads de un tenant.

- **Autenticación**: Ninguna por diseño (endpoint público de ingesta masiva).
- **Path Parameters**: `tenant_id` (UUID).
- **Form Data**: `file` (`UploadFile`, Multipart/form-data).
- **Response (200 OK)** ([`BatchProcessResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_rows": 10,
  "successful_ingestions": 9,
  "failed_rows": [
    {
      "row_number": 3,
      "email": "invalid-email",
      "error": "Formato de correo electrónico inválido",
      "error_code": "INVALID_EMAIL"
    }
  ]
}
```

---

### 4. Listar Leads (`GET /api/v1/tenants/{tenant_id}/leads`)

Consulta de leads paginados pertenecientes a un tenant.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: Requiere acceso al tenant vía `verify_tenant_access` (cualquier agente autenticado perteneciente a `tenant_id`, o un `ADMIN`).
- **Path Parameters**: `tenant_id` (UUID).
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

### 5. Plano de Plataforma — Organizaciones (`/api/v1/tenants`)

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
    "team": "Management",
    "active_leads_count": 0,
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

### 6. Gestión de Agentes (`/api/v1/agents`)

Restringido al plano de organización: un `ADMIN` recibe `403 Forbidden` en los tres endpoints.

#### `POST /api/v1/agents`
Crea un nuevo agente de ventas.

- **Autenticación**: Requerida (`Bearer Token`), excepto en estado Bootstrap (base de datos sin agentes: el primer agente creado es forzosamente `ADMIN`).
- **Permisos**: `MANAGER`, y sólo dentro de su propia organización. No puede crear otros `ADMIN`; el único nace del bootstrap.
- **Request Body** ([`AgentCreate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)). Sin `tenant_id`: la organización es siempre la del gestor autenticado, tomada del contexto, nunca de la petición.
```json
{
  "name": "Carlos Ruiz",
  "email": "cruiz@techcorp.com",
  "team": "Sales",
  "active_leads_count": 0,
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
  "team": "Sales",
  "active_leads_count": 0,
  "is_active": true,
  "role": "AGENT",
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
}
```

#### `GET /api/v1/agents`
Obtiene la lista paginada de agentes comerciales de la propia organización. Cierra la fuga cross-tenant que tenía antes de F0.5: ya no basta con estar autenticado, y nunca devuelve asesores de otra organización.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `MANAGER`. Un `AGENT` recibe `403 Forbidden`.
- **Query Parameters**: `team` (string, opcional), `limit` (int, default=100), `offset` (int, default=0).
- **Response (200 OK)** ([`PaginatedAgentsResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "items": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "name": "Carlos Ruiz",
      "email": "cruiz@techcorp.com",
      "team": "Sales",
      "active_leads_count": 0,
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
  "team": "Sales",
  "active_leads_count": 0,
  "is_active": true,
  "role": "AGENT",
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
}
```
- **Errores**: `404 Not Found` (`AGENT_NOT_FOUND`) tanto si el identificador no existe como si pertenece a otra organización — nunca `403`, para no confirmar con el código de estado que ese identificador existe en otro sitio.

---

### 7. Gestión de Reglas (`/api/v1/tenants/{tenant_id}/rules`)

Todos los endpoints de reglas están acotados por tenant y requieren la dependencia `require_role_and_tenant(AgentRole.ADMIN, AgentRole.MANAGER)`.

#### `POST /api/v1/tenants/{tenant_id}/rules/scoring`
Crea una regla de scoring para el tenant.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `ADMIN` o `MANAGER` perteneciente a `tenant_id`.
- **Path Parameters**: `tenant_id` (UUID).
- **Request Body** ([`ScoringRuleCreate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "name": "High Budget Rule",
  "field": "budget",
  "operator": "GREATER_THAN",
  "value": 10000,
  "score_delta": 20
}
```
- **Response (201 Created)** ([`ScoringRuleResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "id": "22222222-2222-2222-2222-222222222222",
  "name": "High Budget Rule",
  "field": "budget",
  "operator": "GREATER_THAN",
  "value": 10000,
  "score_delta": 20
}
```

#### `GET /api/v1/tenants/{tenant_id}/rules/scoring`
Obtiene las reglas de scoring asociadas a un tenant.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `ADMIN` o `MANAGER` perteneciente a `tenant_id`.
- **Path Parameters**: `tenant_id` (UUID).
- **Response (200 OK)** (`List[`[`ScoringRuleResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)`]`):
```json
[
  {
    "id": "22222222-2222-2222-2222-222222222222",
    "name": "High Budget Rule",
    "field": "budget",
    "operator": "GREATER_THAN",
    "value": 10000,
    "score_delta": 20
  }
]
```

#### `POST /api/v1/tenants/{tenant_id}/rules/routing`
Crea una regla de ruteo para el tenant.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `ADMIN` o `MANAGER` perteneciente a `tenant_id`.
- **Path Parameters**: `tenant_id` (UUID).
- **Request Body** ([`RoutingRuleCreate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "min_score": 40,
  "target_team": "Enterprise Sales",
  "assignment_strategy": "ROUND_ROBIN",
  "target_agent_ids": [
    "11111111-1111-1111-1111-111111111111"
  ]
}
```
- **Response (201 Created)** ([`RoutingRuleResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "id": "33333333-3333-3333-3333-333333333333",
  "min_score": 40,
  "target_team": "Enterprise Sales",
  "assignment_strategy": "ROUND_ROBIN",
  "target_agent_ids": [
    "11111111-1111-1111-1111-111111111111"
  ]
}
```

#### `GET /api/v1/tenants/{tenant_id}/rules/routing`
Obtiene las reglas de ruteo asociadas a un tenant.

- **Autenticación**: Requerida (`Bearer Token`).
- **Permisos**: `ADMIN` o `MANAGER` perteneciente a `tenant_id`.
- **Path Parameters**: `tenant_id` (UUID).
- **Response (200 OK)** (`List[`[`RoutingRuleResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)`]`):
```json
[
  {
    "id": "33333333-3333-3333-3333-333333333333",
    "min_score": 40,
    "target_team": "Enterprise Sales",
    "assignment_strategy": "ROUND_ROBIN",
    "target_agent_ids": [
      "11111111-1111-1111-1111-111111111111"
    ]
  }
]
```
