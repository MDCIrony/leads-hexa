# 03 · Gateway y autenticación

Una petición entra por un único punto, se autentica una vez y llega a cada servicio con una
identidad que el servicio puede verificar por sí mismo. El navegador no cambia: sigue usando la
cookie opaca de [ADR-0029](../decisiones/0029-sesiones-opacas.md). Decisión registrada en
[ADR-0032](../decisiones/0032-gateway-y-phantom-token.md).

## El gateway

Un contenedor `gateway` con nginx. Ocupa el puerto **8001** del host, el de la API antes del
gateway, así que `verify-e2e.sh`, las colecciones de Bruno y los
`GOOGLE_REDIRECT_URI`/`GITHUB_REDIRECT_URI` siguen apuntando al mismo sitio. El `backend` ya no
publica puerto. El nginx del frontend apunta al gateway
(`proxy_pass http://gateway_api/api/v1/`, con `gateway_api` un `upstream` que se vuelve a resolver
por DNS, igual que en el gateway).

El gateway no tiene lógica de negocio ni base de datos. Hace sólo lo que es del borde:

| Responsabilidad | Antes | Con el gateway |
|---|---|---|
| Enrutar por prefijo | — (un único upstream) | Tabla de abajo |
| Autenticar | `get_current_agent` en el backend | `auth_request` contra la introspección (backend en F0, identity desde F3) |
| CORS | `CORSMiddleware` en `main.py` | `map $http_origin` en nginx |
| `Origin` en escrituras | Middleware `reject_untrusted_browser_origins` | `map` + `return 403` con el mismo sobre JSON |
| `X-Request-Id` | — | Conserva el que llega si es seguro para un log (`[A-Za-z0-9._-]{1,128}`); si no, genera uno (`$request_id`). Lo propaga y lo devuelve |
| Límites | — | `client_max_body_size 10m`; `limit_req` sólo en `/api/v1/auth/` |

**Orígenes permitidos.** Viven en dos sitios: el `map $http_origin` del gateway (comparación exacta,
nunca por prefijo) y `CORS_ORIGINS` del backend, que éste sólo usa ya para validar que
`FRONTEND_ORIGIN` es uno de ellos. Añadir un origen es tocar los dos.

**Límites.** `limit_req` (20 r/s por IP, `burst=60`, 429) sólo protege `/api/v1/auth/`: es donde está
la fuerza bruta de login, y la carga legítima del frontend y de `verify-e2e.sh` no debe toparse con él.

### Tabla de enrutado

| Prefijo | Upstream | `auth_request` | Motivo |
|---|---|---|---|
| `/api/v1/auth/` | identity | **No** | Es la frontera de autenticación: valida su propia cookie y emite la sesión. Es el único prefijo con `limit_req` |
| `/api/v1/agents` y `/api/v1/agents/` (ruta exacta) | identity | **Opcional** | `POST /agents` crea al administrador de plataforma sin credencial sobre una base vacía; ver [Bootstrap](#bootstrap-anonimo-de-post-agents) |
| `/api/v1/tenants/`, `/api/v1/agents/` (resto) | identity | Sí | |
| `/api/v1/sources/`, `/api/v1/intake/` | intake | Sí | |
| `/api/v1/leads/`, `/api/v1/rules/`, `/api/v1/groups/`, `/api/v1/advisors/` | lead-core | Sí | |
| `/api/v1/notifications/` | notifications | Sí | |
| `/openapi.json`, `/docs` | lead-core | **No** | Documentación de la API; el gateway quita `Cookie` |
| `/internal/` | — | — | `return 404`: nunca se publica |
| `/health` | el propio gateway | No | |
| Cualquier otra ruta | — | — | `404` con el sobre `NOT_FOUND` |

Durante la migración, un prefijo cuyo servicio todavía no existe apunta a `lead-core` (el monolito).
Mover una capacidad es añadir un `location` más específico con su `upstream`.

!!! note "Hasta F2"
    Todos los prefijos apuntan a `backend`, que además sirve la introspección y la JWKS, salvo
    `/api/v1/notifications` (y con barra final), que ya va a `notifications` (F2). El contenedor
    `identity` no existe todavía. El prefijo se declara en las dos formas, exacta y con barra, como
    `/agents`: un `location` de prefijo solo mandaría la ruta sin barra al monolito.

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
GET /internal/v1/auth/introspect[?optional=true]
  Cookie: leads_session=…        (opcional)
  X-Api-Key: {agent_id}.{secreto} (opcional; si llega, tiene prioridad, como hoy)
  X-Request-Id: …

200  X-Internal-Token: <jwt>      cuerpo vacío
204                               sólo con ?optional=true y sin ninguna credencial
401                               sin credencial, sesión caducada o revocada, agente inactivo, clave inválida
```

La introspección **no autoriza**: no devuelve 403 ni mira la ruta. Sólo dice quién es. La
autorización sigue en cada servicio, sobre el `Principal`.

#### Bootstrap anónimo de `POST /agents`

La ruta exacta `/api/v1/agents` (con o sin barra final) usa la introspección opcional
(`?optional=true`): sin credencial devuelve `204` y el gateway reenvía la petición sin `Authorization`.
**Cualquier credencial que llegue debe ser válida**: una inválida es `401`, nunca degrada a anónimo.
La decisión es del servicio: una petición anónima sólo crea al `ADMIN` de plataforma sobre una base de
agentes vacía, y un principal de máquina en esa ruta es `401` (`get_optional_human_principal`).

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
- **JWKS** en `GET /internal/v1/jwks`. `chassis.auth.JwksCache` la cachea así:
    - **Camino rápido:** un `kid` conocido y fresco se resuelve sin tomar el *lock*.
    - **Edad máxima de 60 s.** Pasada, el siguiente token vuelve a pedir el documento y **sustituye
      el conjunto entero**: una clave que ya no se publica deja de valer. Así se aplica la retirada
      al rotar.
    - **`kid` desconocido:** se vuelve a pedir, como mucho una vez cada 10 s (`min_refresh`), para que una
      avalancha de tokens con `kid` inventados no se convierta en una avalancha contra la JWKS.
    - **Reintento tras un fallo:** si la última petición falló (o todavía no hay claves cargadas
      porque la JWKS no respondía al arrancar), la siguiente sale a 1 s en vez de 10 s.
    - **Si la petición falla,** conserva las claves ya conocidas y registra un `WARNING`: se prefiere
      una clave caducada a una caída. **Límite conocido:** mientras la JWKS no responde, una clave
      retirada sigue valiendo.
    - **`401` sólo con prueba.** Un `kid` da `TokenError` (`401`) únicamente si en esa misma llamada se
      ha descargado el documento y el `kid` no está. Un `kid` que todavía no se puede comprobar contra
      un documento recién pedido (la petición está limitada por `min_refresh` o acaba de fallar), o
      un frío sin claves, lanza `KeysUnavailable`, subclase de `TokenError`. Cada servicio la contesta
      `503 SERVICE_UNAVAILABLE`, nunca `401`: durante una rotación ese `kid` puede ser válido, y un
      `401` el SPA lo lee como sesión terminada.

  Rotar es publicar la clave nueva junto a la anterior, firmar con la nueva y retirar la vieja pasados
  60 s; los servicios la dejan de aceptar como mucho 60 s después de que se deje de publicar.
- **`TokenVerifier`** (el mismo código en todos los servicios) fija `ISSUER` y `AUDIENCE` como
  constantes, rechaza un `ptype` fuera de {`human`, `integration`} y un par `role`/`ptype` incoherente
  (`INTEGRATION` si y sólo si `integration`).
- **`SIGNING_KEYS`** es una lista `kid=<semilla>[,kid=<semilla>…]`, donde la semilla es la semilla
  Ed25519 de 32 bytes en base64url sin relleno (no PEM). La primera firma; todas se publican en la
  JWKS. El valor de desarrollo vive en `docker-compose.yml`.
- **PyJWT** (`pyjwt[crypto]`) en `chassis`. `cryptography` ya es dependencia del backend.
- **Revocación igual que hoy.** Cada petición vuelve a introspeccionar: logout, desactivación de un
  agente o suspensión de un tenant se aplican en la petición siguiente. Los 60 s no son una ventana
  de revocación; sólo acotan cuánto vale un token si se filtrara dentro de la red.

### Lo que cada servicio hace con él

`get_current_agent` desaparece de los servicios. `dependencies.py` queda así en todos:

```python
def get_principal(request, container) -> Principal:
    try:
        claims = container.token_verifier.verify(_bearer_token(request))   # chassis.auth
        return Principal(agent_id=UUID(claims.sub), tenant_id=..., role=claims.role, principal_type=claims.ptype)
    except KeysUnavailable:                  # antes que TokenError: es su subclase
        raise DomainException("Signing keys unavailable", error_code="SERVICE_UNAVAILABLE")
    except (TokenError, ValueError):
        raise UnauthorizedException()

def get_request_context(principal = Depends(get_principal)) -> RequestContext:
    if principal.principal_type == "integration":
        raise UnauthorizedException()
    return RequestContext(principal=principal, tenant_id=principal.tenant_id)
```

El `Principal` es de cada servicio (en `application/dtos/context.py`); `chassis` entrega las
`Claims` ya verificadas y no lo construye.

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
| Identity no responde (`proxy_connect_timeout 1s`, `proxy_read_timeout 2s`) | `503 {"error": true, "error_code": "SERVICE_UNAVAILABLE", "message": "Service unavailable"}` |
| Servicio destino no responde | `503` con el mismo sobre |
| Un servicio no puede obtener las claves de la JWKS | El servicio responde `503 SERVICE_UNAVAILABLE`; el gateway lo reenvía tal cual |
| Escritura con `Origin` no permitido | `403 FORBIDDEN`, «Origen no permitido», antes de introspeccionar |
| Ruta fuera de las publicadas | `404 NOT_FOUND` |
| Cuerpo mayor de 10 MB | `413 PAYLOAD_TOO_LARGE` |
| Más de 20 r/s por IP (+ ráfaga de 60) en `/api/v1/auth/` | `429 TOO_MANY_REQUESTS` |
| `Authorization` enviado por el cliente | Se sobrescribe siempre; nunca llega al servicio |

`auth_request` sólo propaga el código de estado, no el cuerpo; los sobres los compone el gateway con
`error_page`. Los `error_code` previos no cambian, y el contrato hacia el navegador tampoco. El
`message` de un 401 es siempre «Authentication required», sea cual sea la causa («Agent no longer
exists or is inactive», «Invalid API key» eran los anteriores): unificarlo deja de revelar cuál de las
credenciales falló.

El esquema de seguridad `X-Api-Key` ya no aparece en OpenAPI, porque la valida el gateway y no la API;
[API · Referencia](../desarrollo/api-referencia.md) lo documenta a mano.

### Esqueleto de la configuración

Extracto de `gateway/nginx.conf`. Los `include` de abajo viven en el mismo directorio y comparten
todos los `location`; ver [Includes compartidos](#includes-compartidos).

```nginx
# Docker's embedded DNS: a recreated container (new IP) is picked up without a restart.
resolver 127.0.0.11 valid=10s ipv6=off;

upstream backend {
    zone backend 64k;
    server backend:8000 resolve;
    keepalive 32;
}

location = /_introspect {
    internal;
    proxy_pass http://backend/internal/v1/auth/introspect;
    include    /etc/nginx/conf.d/introspect.inc;   # no body; Cookie, X-Api-Key, X-Request-Id; 1 s / 2 s
}

# Extracted service: both forms, or the bare path would fall through to the monolith.
location = /api/v1/notifications  { include /etc/nginx/conf.d/protected.inc; proxy_pass http://notifications; }
location   /api/v1/notifications/ { include /etc/nginx/conf.d/protected.inc; proxy_pass http://notifications; }

location /api/v1/ {
    include    /etc/nginx/conf.d/protected.inc;   # auth_request + proxy_headers.inc + no Cookie
    proxy_pass http://backend;
}

location /internal/ { return 404 '{"error":true,"error_code":"NOT_FOUND","message":"Not Found"}'; }
error_page 401 = @unauthorized;
# auth_request turns any subrequest failure other than 401/403 into a 500.
error_page 500 502 503 504 = @unavailable;
```

`resolve` en un `upstream` exige nginx 1.27.3 o posterior. Con él, el gateway arranca sin que sus
servicios existan y sobrevive a que uno se recree, por lo que **no declara `depends_on`**. Un
`proxy_pass` con nombre estático falla al arrancar si el nombre no resuelve. Cada `location` incluye
`proxy_headers.inc` (directa o a través de `protected.inc`) en vez de repetir las cabeceras: nginx descarta los `proxy_set_header` del
nivel `server` en cuanto un `location` declara uno propio, y lo mismo pasa con `add_header`, que por
eso se queda a nivel `server`.

Sin `proxy_intercept_errors`, `error_page` sólo actúa sobre las respuestas que genera el propio nginx:
un 401 o un 500 que devuelva un servicio llega al cliente tal cual, con su sobre.

`keepalive` en los `upstream` con `proxy_http_version 1.1` y `Connection ""` es obligatorio: sin eso
cada introspección y cada petición abren una conexión TCP nueva.

### Includes compartidos

| Fichero | Contenido |
|---|---|
| `proxy_headers.inc` | Cabeceras de todo `location` proxificado: `X-Request-Id`, `Host`, `X-Forwarded-*`; vacía `X-Api-Key`; sobrescribe `Authorization` con el token interno (vacío si no hubo introspección) |
| `introspect.inc` | Lo que usan los dos `location` de introspección: sin cuerpo, `Cookie`, `X-Api-Key` y `X-Request-Id`, con los *timeouts* de 1 s y 2 s |
| `protected.inc` | `auth_request /_introspect`, captura el token, incluye `proxy_headers.inc` y quita `Cookie` |
| `protected_optional.inc` | Igual, contra `/_introspect_optional`: sin credencial pasa como anónimo; una presente debe ser válida |

Un `location` nuevo de `/api/v1/` toma sus líneas de autenticación de `protected.inc`, y por eso no
puede olvidarlas. `verify_ms_f0` lo comprueba de forma estática sobre `nginx -T`: todo `location`
bajo `/api/v1/`, salvo `/api/v1/auth/`, incluye `protected.inc` o `protected_optional.inc`.

### Operación

`gateway/` está montado como directorio en `/etc/nginx/conf.d`: tanto `nginx.conf` como los `*.inc`
se ven al editarlos. Tras editarlos:

```bash
docker compose exec gateway nginx -s reload
```

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

Hoy `MFA_ENCRYPTION_KEY` y `SIGNING_KEYS` (la semilla privada de firma) están en `backend`,
`intake-worker` y `backend-test` porque comparten `Settings`. Tras F3 sólo los tiene identity.

## Fuera de alcance, a propósito

- **mTLS entre servicios y principales SASL de Kafka por servicio.** La red de Compose sigue siendo
  el perímetro de confianza, como ya asume [ADR-0028](../decisiones/0028-autenticacion-de-la-mensajeria.md)
  para el listener interno de Kafka. El token firmado ya impide que un proceso de la red fabrique
  identidades; mTLS añadiría cifrado y autenticación del transporte. Ver
  [Evoluciones y riesgos](07-evoluciones-y-riesgos.md).
- **Caché de introspección en el gateway.** Ahorraría la consulta a identity a cambio de que una
  revocación tarde lo que dure la caché. La medición de F0 (≈3 ms por petición) no la justifica; ver
  [Mediciones](07-evoluciones-y-riesgos.md#mediciones).
