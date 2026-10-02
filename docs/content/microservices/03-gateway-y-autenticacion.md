# 03 · Gateway y autenticación

Una petición entra por un único punto, se autentica una vez y llega a cada servicio con una
identidad que el servicio puede verificar por sí mismo. El navegador no cambia: sigue usando la
cookie opaca de [ADR-0029](../decisiones/0029-sesiones-opacas.md). Decisión registrada en
[ADR-0032](../decisiones/0032-gateway-y-phantom-token.md).

## El gateway

Un contenedor `gateway` con nginx. Ocupa el puerto **8001** del host, el que hoy usa `backend`, así
que `verify-e2e.sh`, las colecciones de Bruno y los `GOOGLE_REDIRECT_URI`/`GITHUB_REDIRECT_URI`
siguen apuntando al mismo sitio. El nginx del frontend cambia una línea:
`proxy_pass http://gateway:8080/api/v1/`.

El gateway no tiene lógica de negocio ni base de datos. Hace sólo lo que es del borde:

| Responsabilidad | Hoy | Después |
|---|---|---|
| Enrutar por prefijo | — (un único upstream) | Tabla de abajo |
| Autenticar | `get_current_agent` en el backend | `auth_request` contra identity |
| CORS | `CORSMiddleware` en `main.py` | `map $http_origin` en nginx |
| `Origin` en escrituras | Middleware `reject_untrusted_browser_origins` | `map` + `return 403` con el mismo sobre JSON |
| `X-Request-Id` | — | Genera uno si no llega (`$request_id`) y lo propaga |
| Límites | — | `client_max_body_size` y `limit_req` por IP |

### Tabla de enrutado

| Prefijo | Upstream | `auth_request` | Motivo |
|---|---|---|---|
| `/api/v1/auth/` | identity | **No** | Es la frontera de autenticación: valida su propia cookie y emite la sesión |
| `/api/v1/tenants/`, `/api/v1/agents/` | identity | Sí | |
| `/api/v1/sources/`, `/api/v1/intake/` | intake | Sí | |
| `/api/v1/leads/`, `/api/v1/rules/`, `/api/v1/groups/`, `/api/v1/advisors/` | lead-core | Sí | |
| `/api/v1/notifications/` | notifications | Sí | |
| `/internal/` | — | — | `return 404`: nunca se publica |
| `/health` | el propio gateway | No | |

Durante la migración, un prefijo cuyo servicio todavía no existe apunta a `lead-core` (el monolito).
Mover una capacidad es cambiar una línea de `upstream`.

## *Phantom token*

```mermaid
sequenceDiagram
    autonumber
    participant B as Navegador
    participant GW as gateway
    participant ID as identity
    participant S as servicio

    B->>GW: GET /api/v1/leads (Cookie: leads_session)
    GW->>ID: auth_request → GET /internal/v1/auth/introspect<br/>Cookie, X-Api-Key, X-Request-Id
    ID->>ID: SHA-256 → auth_sessions vigente → agente activo
    ID->>ID: firma JWT interno (Ed25519, 60 s)
    ID-->>GW: 200 + X-Internal-Token
    GW->>S: Authorization: Bearer <jwt><br/>sin Cookie, sin X-Api-Key
    S->>S: verifica firma (JWKS en caché), iss, aud, exp
    S->>S: Principal → RequestContext → guardas
    S-->>GW: respuesta
    GW-->>B: respuesta
```

El nombre del patrón describe lo que hace: fuera de la red interna el token no existe. El navegador
sólo ve su cookie opaca; los servicios sólo ven un JWT de vida corta que nadie fuera ha visto.

### Contrato de introspección

```text
GET /internal/v1/auth/introspect
  Cookie: leads_session=…        (opcional)
  X-Api-Key: {agent_id}.{secreto} (opcional; si llega, tiene prioridad, como hoy)
  X-Request-Id: …

200  X-Internal-Token: <jwt>      cuerpo vacío
401                               sin credencial, sesión caducada o revocada, agente inactivo, clave inválida
```

La introspección **no autoriza**: no devuelve 403 ni mira la ruta. Sólo dice quién es. La
autorización sigue en cada servicio, sobre el `Principal`.

### El token interno

| Claim | Valor |
|---|---|
| `iss` | `identity` |
| `aud` | `lead-router` |
| `sub` | `agent_id` |
| `tid` | `tenant_id`, o `null` para `ADMIN` |
| `role` | `ADMIN`, `MANAGER`, `AGENT` o `INTEGRATION` |
| `ptype` | `human` o `integration` |
| `iat`, `exp` | `exp = iat + 60 s` |
| `jti` | UUID, para trazas |
| cabecera `kid` | Identificador de la clave de firma |

- **Firma Ed25519 (`EdDSA`).** Asimétrica: identity firma con la privada y los servicios sólo tienen
  la pública. Un servicio comprometido no puede fabricar identidades. Se verifica, no se descifra: el
  contenido no es secreto, su integridad sí.
- **JWKS** en `GET /internal/v1/jwks`. `chassis.auth` la cachea y la vuelve a pedir si llega un `kid`
  desconocido. Rotar es publicar la clave nueva junto a la anterior, firmar con la nueva y retirar la
  vieja pasados 60 s.
- **PyJWT** (`pyjwt[crypto]`) en `chassis`. `cryptography` ya es dependencia del backend.
- **Revocación igual que hoy.** Cada petición vuelve a introspeccionar: logout, desactivación de un
  agente o suspensión de un tenant se aplican en la petición siguiente. Los 60 s no son una ventana
  de revocación; sólo acotan cuánto vale un token si se filtrara dentro de la red.

### Lo que cada servicio hace con él

`get_current_agent` desaparece de los servicios. `dependencies.py` queda así en todos:

```python
def get_request_context(request: Request) -> RequestContext:
    claims = verify_user_token(_bearer(request))          # chassis.auth: firma, iss, aud, exp
    if claims.ptype != "human":
        raise UnauthorizedException("Authentication required")
    return build_request_context(Principal.from_claims(claims))
```

Las guardas `require_platform_admin`, `require_organization_manager` y `require_organization_member`
no cambian: siguen componiéndose sobre `get_request_context`.

### La credencial de integración

`X-Api-Key` usa la misma introspección y produce un token con `ptype=integration`. La regla «sólo
`GET /leads`» **sigue en el servicio**: `get_request_context` rechaza `ptype=integration` con 401,
exactamente lo que ocurre hoy porque una integración no puede obtener sesión, y sólo
`require_manager_or_integration` de lead-core lo acepta. Es autorización por ruta, el patrón que el
código ya usa; el gateway no conoce ninguna regla de negocio.

### Fallos: siempre cerrado

| Situación | Respuesta del gateway |
|---|---|
| Introspección `401` | `401 {"error": true, "error_code": "UNAUTHORIZED", "message": "Authentication required"}` |
| Identity no responde (`proxy_connect_timeout 1s`, `proxy_read_timeout 2s`) | `503 {"error": true, "error_code": "SERVICE_UNAVAILABLE", …}` |
| Servicio destino no responde | `503` con el mismo sobre |
| `Authorization` enviado por el cliente | Se sobrescribe siempre; nunca llega al servicio |

`auth_request` sólo propaga el código de estado, no el cuerpo; los sobres los compone el gateway con
`error_page`. El `error_code` es el de hoy. El `message` de un 401 pasa a ser uno fijo: hoy varía
según la causa («Agent no longer exists or is inactive», «Invalid API key») y unificarlo además deja
de revelar cuál de las credenciales falló.

### Esqueleto de la configuración

```nginx
upstream identity  { server identity:8000;  keepalive 16; }
upstream lead_core { server lead-core:8000; keepalive 32; }

location = /_introspect {
    internal;
    proxy_pass              http://identity/internal/v1/auth/introspect;
    proxy_pass_request_body off;
    proxy_set_header        Content-Length "";
    proxy_set_header        Cookie       $http_cookie;
    proxy_set_header        X-Api-Key    $http_x_api_key;
    proxy_set_header        X-Request-Id $request_id;
    proxy_connect_timeout   1s;
    proxy_read_timeout      2s;
}

location /api/v1/leads/ {
    auth_request     /_introspect;
    auth_request_set $internal_token $upstream_http_x_internal_token;
    proxy_set_header Authorization "Bearer $internal_token";
    proxy_set_header Cookie        "";
    proxy_set_header X-Api-Key     "";
    proxy_set_header X-Request-Id  $request_id;
    proxy_http_version 1.1;
    proxy_set_header Connection    "";
    proxy_pass       http://lead_core;
}

location /internal/ { return 404; }
error_page 401 = @unauthorized;
# auth_request turns any subrequest failure other than 401/403 into a 500.
error_page 500 502 503 504 = @unavailable;
```

Sin `proxy_intercept_errors`, `error_page` sólo actúa sobre las respuestas que genera el propio nginx:
un 401 o un 500 que devuelva un servicio llega al cliente tal cual, con su sobre.

`keepalive` en los `upstream` con `proxy_http_version 1.1` y `Connection ""` es obligatorio: sin eso
cada introspección y cada petición abren una conexión TCP nueva.

## Llamadas entre servicios

Algunas llamadas no tienen un usuario detrás: el worker de intake pidiendo una admisión, lead-core
hidratando un asesor. Usan **tokens de servicio**, emitidos por identity con el patrón *client
credentials* y verificados con el mismo código de `chassis`.

```text
POST /internal/v1/service-tokens
{ "client_id": "intake", "client_secret": "…", "audience": "lead-core" }

200 { "access_token": "<jwt>", "expires_in": 300 }
     claims: iss=identity, sub=intake, aud=lead-core, ptype=service, exp=iat+300
```

| Llamante | Audiencia permitida | Para |
|---|---|---|
| `intake` | `lead-core` | `POST /internal/v1/admissions` |
| `lead-core` | `identity` | `GET /internal/v1/agents/{agent_id}` |

- Los clientes y sus audiencias permitidas son configuración de identity (`SERVICE_CLIENTS`), no una
  tabla: son un conjunto fijo que sólo cambia cuando cambia la arquitectura. Identity guarda el hash
  del secreto, nunca el secreto.
- El llamante cachea el token y lo renueva cuando le quedan menos de 30 s.
- Las rutas `/internal/v1/*` exigen `ptype=service`, `aud` igual al propio servicio y un `sub` de la
  lista de llamantes permitidos para esa ruta.
- **El `tenant_id` de una llamada interna sale del dato persistido del llamante**, no de una entrada
  del usuario: la admisión lleva el `tenant_id` del `intake_record`, que a su vez se derivó del token
  del usuario al recibirlo. ADR-0004 se mantiene de punta a punta.

## Secretos por contenedor

| Secreto | identity | intake | lead-core | notifications | gateway |
|---|:-:|:-:|:-:|:-:|:-:|
| Clave privada de firma | ✓ | | | | |
| `MFA_ENCRYPTION_KEY` | ✓ | | | | |
| Secretos OAuth Google/GitHub | ✓ | | | | |
| Hashes de los secretos de servicio | ✓ | | | | |
| Secreto de servicio propio | | ✓ | ✓ | | |
| DSN de su base | ✓ | ✓ | ✓ | ✓ | |
| URL de la JWKS | | ✓ | ✓ | ✓ | |

Hoy `MFA_ENCRYPTION_KEY` está en `backend`, `intake-worker` y `backend-test` porque comparten
`Settings`. Tras F3 sólo la tiene identity.

## Fuera de alcance, a propósito

- **mTLS entre servicios y principales SASL de Kafka por servicio.** La red de Compose sigue siendo
  el perímetro de confianza, como ya asume [ADR-0028](../decisiones/0028-autenticacion-de-la-mensajeria.md)
  para el listener interno de Kafka. El token firmado ya impide que un proceso de la red fabrique
  identidades; mTLS añadiría cifrado y autenticación del transporte. Ver
  [Evoluciones y riesgos](07-evoluciones-y-riesgos.md).
- **Caché de introspección en el gateway.** Ahorraría la consulta a identity a cambio de que una
  revocación tarde lo que dure la caché. Se activa sólo si la medición de F0 lo pide.
