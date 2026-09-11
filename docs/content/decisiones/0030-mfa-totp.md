# ADR-0030: MFA TOTP opt-in para cuentas humanas

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-09-11 |
| **Ámbito** | Autenticación humana |

## Contexto

Las sesiones opacas de [ADR-0029](0029-sesiones-opacas.md) permiten introducir un segundo factor sin
crear otra identidad ni almacenar tokens en el navegador. Las cuentas humanas necesitan una protección
adicional, mientras que `INTEGRATION` sigue usando `X-Api-Key`.

## Decisión

Se adopta TOTP RFC 6238 opt-in para `ADMIN`, `MANAGER` y `AGENT`. El secreto se cifra con
`MFA_ENCRYPTION_KEY`; los códigos de recuperación sólo se almacenan como hash y se consumen una vez.
El login con MFA crea un desafío de verificación `MFA_LOGIN` de cinco minutos y cinco intentos; la sesión
`leads_session` sólo se emite después de verificar TOTP o un código de recuperación.

La configuración usa seis dígitos, periodo de 30 segundos y tolerancia de un periodo. El mismo timestep
no puede reutilizarse. La clave de cifrado es obligatoria y su pérdida invalida los enrolamientos.

## Alternativas consideradas

- SMS o correo: se descartan por dependencia operativa y menor resistencia al fraude.
- WebAuthn: queda como evolución posterior; requiere un contrato y UX distintos.
- Hacer MFA obligatorio inmediatamente: se descarta para no bloquear cuentas existentes; la obligatoriedad
  por rol requiere una decisión de producto separada.

## Consecuencias

La migración `013_mfa.sql` añade el enrolamiento, los códigos y el soporte de desafíos de verificación.
El frontend debe
completar el flujo antes de considerar autenticada la sesión y nunca debe persistir secretos o códigos.

## Ver también

- [ADR-0029 · Sesiones humanas opacas](0029-sesiones-opacas.md)
- [Identidad y acceso](../modulos/identidad-y-acceso.md)
