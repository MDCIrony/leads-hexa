# ADR-0032 · Gateway nginx y *phantom token*

| | |
|---|---|
| **Estado** | Aceptada — implantada en F0, con la introspección en el monolito; desde F3 la sirve identity, igual que la JWKS y los tokens de servicio |
| **Fecha** | 2026-10-01 |
| **Ámbito** | Seguridad · Infraestructura |

## Contexto

Con varios servicios, cada uno tiene que saber quién hace la petición y de qué organización, sin leer
las tablas de sesión de otro. [ADR-0029](0029-sesiones-opacas.md) fija que el navegador usa una
cookie opaca, que el servidor sólo guarda su hash y que desactivar a alguien corta su acceso en la
petición siguiente. Esa propiedad tiene que sobrevivir a la separación.

## Decisión

- **Un gateway nginx** es la única entrada a la API (`:8001`). Enruta por prefijo y concentra lo que
  es del borde: CORS, comprobación de `Origin`, `X-Request-Id`, límites de tamaño (10 MB) y de
  peticiones (sólo `/api/v1/auth/`). `/internal/*` nunca se publica; lo que no es `/api/v1/`, `/health`,
  `/openapi.json`, `/docs` ni `/openapi/{identity,notifications,intake}.json` responde 404. Estas
  últimas publican el OpenAPI de cada servicio extraído, sin `Cookie`, para generar los tipos del
  frontend.
- **Introspección en cada petición** con `auth_request` contra
  `GET /internal/v1/auth/introspect` de identity, que valida la cookie o la `X-Api-Key` y devuelve un
  **JWT interno** firmado con **Ed25519**, de **60 s**: `iss`, `aud`, `sub`, `tid`, `role`, `ptype`,
  `iat`, `exp`, `jti` y `kid`.
- El gateway reenvía el JWT en `Authorization` y **elimina** `Cookie` y `X-Api-Key`. El cliente nunca
  puede inyectar un `Authorization` propio.
- Cada servicio **verifica el token en local** con la JWKS de identity (en caché) y construye su
  `RequestContext`. La autorización sigue en el servicio. La regla «`X-Api-Key` sólo en `GET /leads`»
  se mantiene en lead-core (`ptype=integration`).
- **Llamadas entre servicios** con tokens de servicio (*client credentials*) emitidos por identity,
  con audiencia por destino y 5 minutos de vida.
- Se falla cerrado: introspección fallida → 401; identity inalcanzable → 503.
- `POST /agents` usa una introspección **opcional**: sin credencial pasa sin `Authorization` y el
  servicio decide (sólo crea al `ADMIN` sobre una base vacía); una credencial presente debe ser válida.
- El gateway vuelve a resolver sus `upstream` por DNS, así que arranca sin sus servicios y no declara
  `depends_on`.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| JWT emitido al navegador y verificado en cada servicio | Revierte ADR-0029: el token vive en el navegador y la revocación exige listas, *refresh tokens* o tokens muy cortos con renovación. Desactivar a alguien dejaría de cortar su acceso en la petición siguiente |
| Introspección en cada servicio | Cada servicio llama a identity en cada petición; se multiplica la carga y la lógica de sesión |
| El gateway inyecta cabeceras planas (`X-Tenant-Id`, `X-User-Id`) | Cualquier proceso de la red podría escribirlas; la identidad no sería verificable en el servicio |
| Gateway con código propio (BFF en FastAPI) | No hace falta: los dos puntos que mezclaban contextos se resuelven con cambios de contrato acotados ([ADR-0036](0036-cambios-de-contrato-publico.md)) |
| Traefik ForwardAuth, Kong, KrakenD | Resuelven lo mismo con más superficie; nginx ya está en el proyecto y `auth_request` es exactamente el patrón |
| Firma HMAC compartida | Cualquier servicio con el secreto podría fabricar tokens; con Ed25519 los servicios sólo tienen la clave pública |
| gRPC para las llamadas internas | Sin ganancia medible para dos llamadas, y `auth_request` sólo hace HTTP; ver [Evoluciones](../microservices/07-evoluciones-y-riesgos.md) |

## Consecuencias

**Fácil:** el navegador no cambia y ADR-0029 se conserva entero: el JWT nunca sale de la red interna.
La revocación sigue aplicándose en la petición siguiente. Cada servicio verifica la identidad sin
llamar a nadie. Llevar un prefijo a otro servicio es cambiar un `upstream`.

**Difícil:** identity está en el camino de cada petición autenticada, y su caída deja la API en 503.
Cada petición paga un salto interno y una firma: ≈ 3 ms en p50 medidos en F0
([Mediciones](../microservices/07-evoluciones-y-riesgos.md#mediciones)). El `message` de un 401 es
siempre «Authentication required», porque lo compone el gateway. Rotar la clave de firma exige publicar
la nueva en la JWKS antes de usarla. Vuelve PyJWT como dependencia, ahora sólo para tokens internos.
Los orígenes permitidos viven en dos sitios (el `map` del gateway y `CORS_ORIGINS`). Un `X-Api-Key`
sigue costando un bcrypt por petición (≈ 290 ms), ahora dentro de la introspección.

## Ver también

- [Gateway y autenticación](../microservices/03-gateway-y-autenticacion.md)
- [ADR-0004 · La organización sale del token](0004-organizacion-desde-el-token.md)
- [ADR-0029 · Sesiones humanas opacas](0029-sesiones-opacas.md)
- [ADR-0028 · Autenticación de la mensajería](0028-autenticacion-de-la-mensajeria.md)
