# ADR-0004 · La organización sale del token

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-07 |
| **Ámbito** | Backend · Autorización |

## Contexto

El diseño original hacía viajar el identificador de organización en la URL, con rutas del tipo
`/tenants/{tenant_id}/...`. Varias fugas cross-tenant medidas en el código de partida compartían la
misma causa: una consulta que no filtraba por organización porque el identificador llegaba como un
dato más de la petición, controlado por quien la enviaba.

## Decisión

La organización sobre la que opera una petición se deriva **siempre** del token JWT, nunca de la
URL ni del cuerpo. Una única dependencia construye un contexto de petición —actor autenticado más
`tenant_id`— a partir del token, una vez por petición, y los casos de uso lo reciben dentro de su
comando. Ningún caso de uso recibe un `tenant_id` que venga del cliente. Consecuencia directa:
`{tenant_id}` desaparece de todas las rutas de la API.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Mantener `/tenants/{tenant_id}/...` con una comprobación de autorización en el borde | La comprobación se puede olvidar en cualquier punto donde alguien la añada, y eso es exactamente lo que producía las fugas medidas |
| Aceptar `tenant_id` en el cuerpo de la petición para las escrituras | Mismo problema de fondo: un dato de confianza que decide el cliente en vez del servidor |

## Consecuencias

**Fácil:** las fugas cross-tenant de esta familia dejan de depender de que alguien recuerde un
filtro por organización: se vuelven imposibles por construcción. El frontend no necesita transportar
ni sincronizar un identificador de organización en cada ruta o llamada.

**Difícil:** el administrador de plataforma, que por definición no tiene organización, se queda sin
ningún mecanismo para operar sobre una en concreto —hueco que resuelve la separación de planos—.
Cualquier caso legítimo de actuar «en nombre de» otra organización —soporte, migración de datos—
necesita su propio mecanismo explícito y auditado, porque el atajo de un parámetro en la URL queda
cerrado a propósito.

## Ver también

- [ADR-0003 · Dos planos disjuntos](0003-dos-planos-disjuntos.md)
- [ADR-0005 · 404 en vez de 403](0005-404-en-vez-de-403.md)
- [Identidad y acceso](../modulos/identidad-y-acceso.md)
