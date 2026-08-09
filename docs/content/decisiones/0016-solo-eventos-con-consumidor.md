# ADR-0016 · Sólo eventos con consumidor

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · Aplicación |

## Contexto

El catálogo de eventos de dominio previsto para el sistema enumera ocho: calificado, descalificado,
asignado, sin asignar, reasignado, descartado, ingesta rechazada e ingesta promovida. De los ocho,
cuatro no tenían ningún manejador que reaccionara a ellos —ni notificación, ni métrica, ni nada—: su
casilla de «consumidor» estaba vacía en el diseño.

## Decisión

Sólo se implementan los cuatro eventos que tienen un consumidor real en el sistema: lead asignado,
lead reasignado, lead sin asignar, e ingesta rechazada, cada uno con el manejador que produce la
notificación correspondiente. Los otros cuatro no se construyen todavía. Añadir un evento más
adelante es barato precisamente porque **añade** información nueva sin reinterpretar nada de lo que
ya existe.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Implementar los ocho eventos del catálogo, aunque cuatro no tengan consumidor | Un evento que nadie escucha es una clase, una prueba y un punto de publicación que hay que mantener sin que nadie se beneficie de ello |
| Implementar sólo el primer evento y añadir el resto bajo demanda, sin catalogarlos antes | Perdería el catálogo completo como referencia de diseño; documentar los ocho deja claro qué falta y por qué, en vez de descartar los cuatro sin registro |

## Consecuencias

**Fácil:** cada evento del sistema tiene un motivo verificable de existir —se puede señalar
exactamente qué manejador lo consume—, y no hay código muerto esperando un consumidor que podría no
llegar nunca.

**Difícil:** capacidades que se apoyarían en los cuatro eventos no construidos —métricas de
conversión, paneles de actividad— no tienen todavía el punto de extensión enganchado; hay que
añadirlo cuando llegue esa necesidad, en vez de encontrarlo ya preparado.

## Ver también

- [ADR-0015 · Notificaciones por sondeo](0015-notificaciones-por-sondeo.md)
- [Notificaciones](../modulos/notificaciones.md)
