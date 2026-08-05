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

### Roles y Permisos (`AgentRole`)
1. **`ADMIN`**:
   - Acceso global sin restricción de tenant (omite verificaciones de `tenant_id`).
   - Puede crear agentes con cualquier rol (`ADMIN`, `MANAGER`, `AGENT`).
   - Puede consultar y gestionar leads, agentes y reglas de cualquier tenant.
2. **`MANAGER`**:
   - Administrador acotado a su propio `tenant_id`.
   - Puede crear agentes (`MANAGER` o `AGENT`) únicamente dentro de su propio tenant (`request.tenant_id == current_agent.tenant_id`). No puede crear otros `ADMIN`.
   - Puede gestionar y consultar reglas de scoring/routing de su tenant (`require_role_and_tenant`).
   - Puede consultar leads de su tenant (`verify_tenant_access`).
3. **`AGENT`**:
   - Usuario estándar de operaciones comerciales.
   - Puede consultar la lista e información de agentes (`GET /api/v1/agents`).
   - Puede consultar los leads asignados a su tenant (`verify_tenant_access`).
   - **No** puede crear agentes ni administrar reglas.

### Aislamiento por Tenant (Tenant Scoping)
Las dependencias [`verify_tenant_access`](../../backend/src/infrastructure/adapters/input/api/dependencies.py) y [`require_role_and_tenant`](../../backend/src/infrastructure/adapters/input/api/dependencies.py) garantizan que un `MANAGER` o `AGENT` solo pueda acceder a recursos cuyo `tenant_id` coincida exactamente con el de su usuario. Los usuarios con rol `ADMIN` sobrepasan esta restricción.

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

### 1. Autenticación (`POST /api/v1/auth/login`)

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
- **Errores**: `401 Unauthorized` (`INVALID_CREDENTIALS` si el correo o contraseña son incorrectos).

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

### 5. Gestión de Agentes (`/api/v1/agents`)

#### `POST /api/v1/agents`
Crea un nuevo agente de ventas.

- **Autenticación**: Requerida (`Bearer Token`), excepto en estado Bootstrap (base de datos sin agentes).
- **Permisos**: `ADMIN` o `MANAGER` (Managers solo pueden crear dentro de su propio `tenant_id` y no pueden crear otros `ADMIN`).
- **Request Body** ([`AgentCreate`](../../backend/src/infrastructure/adapters/input/api/schemas.py)):
```json
{
  "name": "Carlos Ruiz",
  "email": "cruiz@techcorp.com",
  "team": "Sales",
  "active_leads_count": 0,
  "is_active": true,
  "password": "securepassword123",
  "role": "MANAGER",
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
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
  "role": "MANAGER",
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
}
```

#### `GET /api/v1/agents`
Obtiene la lista paginada de agentes comerciales.

- **Autenticación**: Requerida (`Bearer Token` - cualquier agente autenticado).
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
      "role": "MANAGER",
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
Obtiene el detalle de un agente por su UUID.

- **Autenticación**: Requerida (`Bearer Token` - cualquier agente autenticado).
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
  "role": "MANAGER",
  "tenant_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
}
```
- **Errores**: `404 Not Found` (`AGENT_NOT_FOUND`).

---

### 6. Gestión de Reglas (`/api/v1/tenants/{tenant_id}/rules`)

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
