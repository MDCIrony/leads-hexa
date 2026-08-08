# Diagramas

> # ⚠️ ESTOS TRES `.drawio` ESTÁN OBSOLETOS
>
> Describen la arquitectura anterior a F1 y **no reflejan el sistema actual**. No los uses como
> fuente para entender el código ni para implementar nada.
>
> Fuentes vigentes: los diagramas Mermaid del [README](../../README.md) y el
> [spec del MVP](../specs/2026-08-07-lead-router-mvp-design.md).

## Qué tienen de desactualizado

| Fichero | Desfase |
|---|---|
| `hexagonal_architecture.drawio` | Nombra `RoutingRule` y `RouterEngine`, que ya no existen: hoy son `AssignmentRule` y `AssignmentEngine`. Le faltan `SalesGroup`, `Tenant`, la `AuthorizationPolicy` y el Unit of Work |
| `c4_context_container.drawio` | Anterior a la multi-tenencia real y a la separación de planos: no distingue el plano de plataforma del de organización |
| `lead_processing_flow.drawio` | El flujo de ingesta cambió: la carga del asesor se deriva por consulta, el motor cascadea entre reglas y el cursor rotatorio se persiste |

## Cuándo se regeneran

En **F4**, junto con el frontend, que es cuando vuelven a tener lectores. Regenerarlos ahora sería
rehacerlos otra vez tras F2 y F3a.

Se conservan en vez de borrarse porque el trazado y la disposición son reaprovechables: cuesta menos
actualizar las cajas que dibujarlas de cero.

Al regenerarlos, seguir `~/.claude/skills/drawio/SKILL.md`.
