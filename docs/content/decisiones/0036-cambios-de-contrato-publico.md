# ADR-0036 · Dos cambios en el contrato público

| | |
|---|---|
| **Estado** | Aceptada — cambio 1 implantado en F3; cambio 2 en F4 |
| **Fecha** | 2026-10-01 |
| **Ámbito** | API · Frontend |

## Contexto

Dos respuestas de la API pública mezclan datos de dos contextos que van a vivir en servicios distintos:

1. **El grupo del asesor.** `POST/PATCH /agents` aceptan `group_id` y `GET /agents` filtra por él, pero
   el grupo es un concepto de enrutado (lead-core) y la cuenta es de identity.
2. **Los pendientes de ingesta.** `GET /leads/stats` devuelve `pending_intake`, que cuenta
   `intake_records`.

Mantener el contrato idéntico exigiría componer las respuestas en un BFF con código propio, o hacer
que identity guarde `group_id` y replique los grupos desde lead-core (una dependencia en los dos
sentidos).

## Decisión

1. **El grupo pasa a lead-core.** `/agents` deja de admitir `group_id` (`extra="forbid"`, que devuelve
   422 en lugar de ignorarlo en silencio). Se añaden `GET /advisors?group_id=&is_active=` (id, nombre,
   grupo y carga activa) y `PATCH /advisors/{agent_id}` `{group_id}`.
2. **`pending_intake` pasa a intake.** `GET /leads/stats` lo pierde; se añade `GET /intake/stats` →
   `{pending, rejected, pending_intake}`.

El resto de rutas, cuerpos, códigos de estado y el sobre de error no cambian. Los tipos del frontend se
regeneran desde el OpenAPI de cada servicio.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Contrato idéntico con un BFF en FastAPI | Un servicio más que mantener y probar para componer dos respuestas |
| `group_id` en identity, con una proyección de grupos desde lead-core | Dependencia bidireccional entre identity y lead-core; un concepto de enrutado dentro de identidad |
| Lead-core consulta los pendientes a intake en cada `/leads/stats` | Pone a intake en el camino del panel para un dato que no es suyo |

## Consecuencias

**Fácil:** cada respuesta tiene un solo dueño y el gateway sigue siendo declarativo. La dirección de
dependencia es única: identity → lead-core.

**Difícil:** el panel hace dos lecturas (cambio 2). La asignación de grupo inmediatamente después de
crear un agente depende de la hidratación de `AdvisorDirectory`, y responde `503` si identity no
contesta mientras hidrata. El cambio 1 no tuvo coste en el frontend: el MVP nunca tuvo interfaz de
grupo ([Frontend](../roadmap/frontend.md), fila «Asesores»), así que sólo quitó `group_id` de su
contrato de `/agents` y no llama a `/advisors`.

## Ver también

- [Servicios y datos · Cambios en el contrato público](../microservices/02-servicios-y-datos.md#cambios-en-el-contrato-publico)
- [ADR-0022 · Agregados del panel](0022-agregados-del-panel.md)
