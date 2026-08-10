# Identidad y acceso

Autentica cada petición con JWT, recarga la identidad del actor desde base de datos y decide qué
puede hacer según su rol y su organización.

## Cómo funciona

`POST /auth/login` recibe correo y contraseña, y `LoginUseCase` responde con un único fallo
—`InvalidCredentialsException`— tanto si la cuenta no existe como si la contraseña no coincide: un
llamante no puede distinguir un caso del otro. Si coincide, `JwtTokenService` firma un JWT (HS256)
con el identificador del asesor, su rol y su organización como reclamaciones.

Cada petición posterior vuelve a resolver la identidad completa: `get_current_agent` verifica la
firma y la caducidad del token, y **recarga el agente desde base de datos** por su identificador en
lugar de confiar en lo que el token dice. Un asesor desactivado deja de poder operar en su siguiente
petición, aunque su token todavía no haya caducado.

La desactivación es reversible: `PATCH /agents/{agent_id}` con `{"is_active": true}` reactiva al
asesor y le devuelve el acceso en el acto, por la misma razón que se lo cortó — la próxima petición
suya vuelve a recargar el agente, que ya aparece activo. `GET /agents` (sin parámetro) sólo lista
activos; `?is_active=false` es la vía para encontrar a quien reactivar.

El correo es único en **toda la plataforma**, no sólo dentro de una organización:
`LoginUseCase.execute` resuelve la cuenta con `agents.get_by_email(email)` sin filtrar por
`tenant_id`, así que dos organizaciones no pueden compartir un correo sin que el login se quede con
«la fila que la base devuelva primero». `CreateAgentUseCase` comprueba lo mismo antes de guardar y
responde `400 EMAIL_ALREADY_EXISTS` si el correo ya existe en cualquier organización.

```mermaid
sequenceDiagram
    participant C as Cliente
    participant API as Endpoint FastAPI
    participant L as LoginUseCase
    participant H as BcryptPasswordHasher
    participant T as JwtTokenService
    participant P as AuthorizationPolicy

    C->>API: POST /auth/login (email, password)
    API->>L: execute(email, password)
    L->>L: agents.get_by_email(email)
    L->>H: verify(password, hashed_password)
    L->>T: issue(TokenClaims)
    T-->>L: JWT
    L-->>API: access_token
    API-->>C: 200 con el token

    C->>API: petición con Authorization Bearer
    API->>T: verify(token)
    T-->>API: TokenClaims
    API->>API: recarga el agente por id, exige is_active
    API->>P: ensure_can_manage_organization / ensure_can_access_tenant / ...
    P-->>API: ForbiddenException si el rol no alcanza
    API-->>C: 200, o 401/403/404 según el fallo
```

### Los tres roles

| Rol | Plano | Alcance |
|---|---|---|
| `ADMIN` | Plataforma | Da de alta organizaciones. Sin `tenant_id`: no pertenece a ninguna |
| `MANAGER` | Organización | Administra asesores, grupos, reglas y fuentes de su organización |
| `AGENT` | Organización | Sólo sus propios leads asignados y sus notificaciones |

### La regla de bootstrap

`POST /agents` no exige autenticación cuando la tabla de asesores está vacía
(`uow.agents.count() == 0`): esa única petición fuerza el rol `ADMIN` y descarta cualquier
`tenant_id`, sea lo que sea que pida el cuerpo de la petición. En cuanto existe un primer asesor, la
misma ruta exige un `MANAGER` autenticado, y `AuthorizationPolicy.ensure_can_create_agent_with_role`
impide crear un segundo `ADMIN` por esa vía: el único que existirá siempre es el de arranque.

!!! warning
    La ventana de bootstrap depende únicamente del recuento de la tabla, no de un flag de entorno.
    Un despliegue que arranca con la base ya poblada no vuelve a abrirla.

### Los dos planos

`AuthorizationPolicy` separa explícitamente el plano de plataforma del de organización:
`can_manage_platform` sólo lo satisface `ADMIN`, y el resto de métodos —`can_access_tenant`,
`can_manage_organization`, `can_view_lead`— operan siempre dentro de la organización del actor. El
aislamiento entre organizaciones no es una comprobación añadida: `RequestContext.tenant_id` se
construye una única vez por petición a partir del agente verificado, así que ningún caso de uso
recibe un `tenant_id` que el cliente pudiera escribir en la URL o en el cuerpo.

Un fallo de rol y un recurso de otra organización no se distinguen igual: pedir una acción que el
rol no cubre responde `403` (`ForbiddenException`); pedir un recurso que pertenece a otra
organización responde `404`, no `403` —confirmar que existe en otro sitio ya sería una fuga—.

## Piezas

| Pieza | Responsabilidad |
|---|---|
| `AuthorizationPolicy` | Único punto que decide quién puede hacer qué, por plano y por rol |
| `get_current_agent` / `resolve_current_agent` | Verifica el JWT y recarga el agente en BD |
| `require_organization_manager` | Exige rol `MANAGER` sobre la organización del actor |
| `require_platform_admin` | Exige rol `ADMIN` |
| `require_organization_member` | Exige pertenecer a una organización, con cualquier rol |
| `RequestContext` | Actor y organización, resueltos una vez por petición desde el token |
| `LoginUseCase` | Verifica credenciales y emite el JWT |
| `JwtTokenService` | Adaptador PyJWT: firma y verifica el token |
| `BcryptPasswordHasher` | Adaptador passlib/bcrypt para el hash de la contraseña |

## Decisiones que lo explican

- [ADR-0003](../decisiones/0003-dos-planos-disjuntos.md): por qué no se mezclan los dos planos.
- [ADR-0004](../decisiones/0004-organizacion-desde-el-token.md): nunca lo manda el cliente.
- [ADR-0005](../decisiones/0005-404-en-vez-de-403.md): por qué un recurso ajeno responde 404.

## Dónde vive

- `backend/src/domain/policies/authorization_policy.py`
- `backend/src/infrastructure/adapters/input/api/dependencies.py`
- `backend/src/application/use_cases/auth_use_cases.py`
- `backend/src/infrastructure/adapters/input/api/auth_router.py`
- `backend/src/infrastructure/adapters/output/security/jwt_token_service.py`
- `backend/src/infrastructure/adapters/output/security/bcrypt_password_hasher.py`
