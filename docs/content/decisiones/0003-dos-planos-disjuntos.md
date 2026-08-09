# ADR-0003 · Dos planos disjuntos

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-07 |
| **Ámbito** | Backend · Autorización |

## Contexto

Al derivar la organización del token en vez de la URL, quedó una pregunta sin cerrar: el
administrador de plataforma (`ADMIN`) no pertenece a ninguna organización, así que no tiene forma de
expresar sobre cuál quiere operar. Las filas de la matriz de permisos que le concedían ver leads o
gestionar reglas quedaban inalcanzables en la práctica, sin un error claro que lo explicara.

En la misma revisión se confirmó una fuga activa de la misma familia: los endpoints de listado y
detalle de asesores sólo exigían estar autenticado, sin filtrar por organización, así que un asesor
de una organización podía enumerar y leer los asesores de cualquier otra.

## Decisión

El `ADMIN` opera en un **plano de plataforma**, separado del **plano de organización**: crea
organizaciones y su gestor inicial, las lista, las activa o desactiva, y nada más. Nunca accede a
datos operativos —leads, reglas, grupos, asesores— de ninguna organización. `MANAGER` y `AGENT`
operan siempre en el plano de organización, acotados a la suya. Ninguna operación pertenece a los
dos planos: la frontera es «¿esta operación toca datos de negocio de una organización concreta?».

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Impersonación explícita: un `?tenant_id=` que sólo `ADMIN` puede usar | Reintroduce un identificador de organización controlado por el cliente —justo lo que derivar el tenant del token elimina— aunque restringido a un rol |
| Separación de planos (elegida) | Corrige la matriz de permisos en vez de gestionar la ambigüedad, y acota el daño de una credencial de plataforma comprometida |

## Consecuencias

**Fácil:** una credencial de `ADMIN` comprometida no expone ningún dato comercial de ningún
cliente; el plano que alcanza es metadatos de organización. La matriz de permisos se vuelve una
pregunta con una sola respuesta por fila, fácil de comprobar. La fuga de listado de asesores se
cierra en el mismo movimiento, porque pertenece a la misma pregunta de «quién ve qué».

**Difícil:** el `ADMIN` no tiene ninguna visibilidad operativa de un cliente, ni siquiera para
soporte o depuración —ve un recuento de asesores por organización, no la lista—. Si en el futuro
hiciera falta una vía de soporte que sí necesite mirar dentro de una organización, tendría que
diseñarse como un mecanismo propio y auditado, no como una ampliación del rol `ADMIN`.

## Ver también

- [ADR-0004 · La organización sale del token](0004-organizacion-desde-el-token.md)
- [Identidad y acceso](../modulos/identidad-y-acceso.md)
- [Organizaciones](../modulos/organizaciones.md)
