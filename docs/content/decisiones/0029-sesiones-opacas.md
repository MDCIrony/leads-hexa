# ADR-0029: sesiones humanas opacas persistidas

## Estado

Aceptada.

## Decisión

Las sesiones humanas usan una cookie `leads_session` HttpOnly, SameSite=Lax y de duración absoluta configurable (8 horas por defecto). El valor es aleatorio de 256 bits y PostgreSQL conserva sólo su SHA-256 en `auth_sessions`.

Cada petición resuelve sesión vigente/no revocada y vuelve a cargar el agente activo. `POST /auth/logout` revoca la sesión y elimina la cookie. Las escrituras con `Origin` sólo aceptan orígenes incluidos en CORS. `X-Api-Key` permanece como la vía independiente de integraciones.

`auth_challenges` también soporta el desafío de verificación `MFA_LOGIN` de la Fase 2. La decisión específica de TOTP,
cifrado y códigos de recuperación está en [ADR-0030](0030-mfa-totp.md).

## Consecuencias

Se retira JWT/Bearer humano y PyJWT. El frontend no conserva tokens en almacenamiento web: inicia sesión y después consulta `/auth/me` usando la cookie.
