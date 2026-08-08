# F3a — Notificaciones: diseño

**Estado:** implementado. Sucede a F2c.

**Documento maestro:** [spec del MVP](2026-08-07-lead-router-mvp-design.md). Este desarrolla §6.11,
§6.15 y la fila `F3a` de §15.

**Objetivo en una frase:** que quien tiene que actuar sobre un lead se entere sin ir a buscarlo.

---

## 1. El problema

El recorrido de un lead termina en silencio. Un asesor no sabe que le han asignado uno hasta que
entra a mirar; un gestor no sabe que un payload quedó rechazado ni que un lead se quedó sin cubrir.
Toda la información existe —el estado, el asesor, el registro de ingesta— pero **nadie la empuja
hacia la persona que debe actuar**, así que el valor del enrutamiento automático depende de que
alguien recuerde revisar una pantalla.

Y hay un defecto medido que esta fase arrastra por herencia: la respuesta de la ingesta afirma
`webhook_dispatched: true` **en toda ingesta**, porque se calcula como:

```python
webhook_dispatched=True if self.event_publisher else False
```

Eso no comprueba nada sobre el webhook. Comprueba que el publicador exista, y el publicador se
inyecta siempre. El campo es `true` aunque la organización no tenga ningún webhook configurado y
aunque la entrega HTTP haya fallado: `WebhookEventHandler` descarta el booleano que `dispatch()`
devuelve.

## 2. Lo que ya existe y lo que no

Medido contra el código, no contra el maestro:

| Pieza | Estado real |
|---|---|
| Puerto `DomainEventPublisherPort` | ✅ Existe |
| `InMemoryEventPublisher` con `subscribe`/`publish` | ✅ Existe, es la única implementación |
| Suscripción de un handler en el arranque | ✅ Existe, una: el webhook saliente |
| `LeadProcessedEvent` | ✅ Existe, y es el **único** evento |
| Los otros ocho eventos de §6.15 | ❌ No existen en el código, sólo en la tabla del maestro |
| `Notification`, su tabla, sus endpoints | ❌ No existe nada |

El publicador ya captura las excepciones de sus manejadores sin propagarlas, que es la propiedad que
esta fase necesita: **un fallo al notificar no puede hacer fallar la ingesta**.

## 3. Alcance

1. **`Notification`** — entidad, tabla, repositorio
2. **Cuatro eventos de dominio nuevos**, sólo los que tienen consumidor
3. **`NotificationHandler`** — suscrito a los cuatro
4. **Tres endpoints** de consulta y marcado, con contador de no leídas
5. **Retirada de `webhook_dispatched`**
6. Migración `008`

**No entra:** SSE ni WebSocket (decisión D5 del maestro: el cliente sondea), notificaciones por
correo, preferencias de notificación por usuario, agrupación de avisos repetidos, y el webhook
entrante, que es F3b.

## 4. Cuatro decisiones que el maestro deja abiertas

### 4.1 Los eventos se siguen construyendo en la aplicación

El maestro §6.15 dice que los eventos «los emiten las entidades, no los casos de uso», y señala que
`LeadProcessedEvent` se fabrica a mano. **Esta fase no lo cambia.**

Mover la emisión a las entidades exige que acumulen eventos y que alguien los drene tras el commit
—`lead.pull_events()`— y eso toca todas las entidades, todos los casos de uso y todos sus tests, sin
cambiar ni un comportamiento observable. Es una refactorización de patrón, no una capacidad, y
mezclarla con la primera fase que **consume** eventos haría imposible saber cuál de los dos cambios
rompió algo.

Lo que sí se respeta es la propiedad que importa: **los eventos se publican después del commit**, y
eso ya se cumple hoy —la publicación vive fuera del bloque de la unidad de trabajo—.

### 4.2 Sólo cuatro eventos, los que tienen consumidor

La tabla de §6.15 lista ocho. Cuatro de ellos tienen la columna «consumidor en el MVP» vacía o con un
guion: `LeadQualified`, `LeadDisqualified`, `LeadDiscarded` e `IntakePromoted`. Un evento que nadie
escucha es una clase, un test y un punto de publicación que hay que mantener para nada.

Los cuatro que entran:

| Evento | Se emite cuando | Quién recibe el aviso |
|---|---|---|
| `LeadAssigned` | Un lead se asigna a un asesor | El **asesor** |
| `LeadReassigned` | Un lead cambia de asesor | El **nuevo asesor** |
| `LeadLeftUnassigned` | Un lead viable no encuentra asesor | El **gestor** |
| `IntakeRejected` | Un registro de ingesta falla la validación | El **gestor** |

Los otros cuatro se añadirán cuando exista quien los escuche —métricas, en la práctica—. Añadir un
evento después es barato: **añade** información y no reinterpreta la guardada.

### 4.3 `webhook_dispatched` se retira, no se corrige

Es el punto que el maestro §15 encarga a esta fase, y la corrección honesta es **quitar el campo**.

Para que dijera la verdad, el caso de uso tendría que saber si una entrega HTTP hecha por un
manejador desacoplado tuvo éxito. Eso significa que el publicador devuelva resultados de sus
manejadores, y con ello el caso de uso vuelve a acoplarse a lo que el pub/sub existe para
desacoplar. El precio de la honestidad sería deshacer el patrón.

**Un campo que no se puede calcular con honestidad no debe estar en la respuesta.** La entrega de
webhooks es asíncrona por diseño; su resultado se consulta donde vive, y F3b —que construye la
configuración de webhooks— es la fase que decide si eso merece su propia bandeja.

### 4.4 El destinatario es siempre un `Agent`

`recipient_id` apunta a un `Agent`, y el gestor es un `Agent` con rol `MANAGER`. No hay otra entidad
de usuario en el sistema.

Avisar «al gestor» significa entonces **a todos los gestores activos de la organización**: una
organización puede tener varios y elegir uno sería arbitrario. El repositorio de agentes gana
`list_by_tenant_and_role(tenant_id, role)` para resolverlo.

El administrador de plataforma **nunca recibe notificaciones**: no pertenece a ninguna organización
y no debe alcanzar datos operativos.

## 5. El modelo

```
Notification
  id             NotificationId
  tenant_id      → Tenant
  recipient_id   → Agent            el asesor o el gestor
  kind           NotificationKind   determina icono y texto en la interfaz
  lead_id        → Lead | None      permite navegar al detalle
  intake_record_id → IntakeRecord | None   para los avisos de validación fallida
  message        str                texto ya compuesto, listo para mostrar
  is_read        bool
  created_at     datetime
```

**Comportamiento:** `mark_as_read()`.

`NotificationKind` toma un valor por evento consumido: `LEAD_ASSIGNED`, `LEAD_REASSIGNED`,
`LEAD_LEFT_UNASSIGNED`, `INTAKE_REJECTED`.

**El mensaje se compone al crear la notificación y se guarda hecho.** Componerlo al leer obligaría a
que la consulta cargara el lead y el registro de ingesta de cada aviso, y a que un lead borrado
dejara notificaciones que no se pueden renderizar. Es la misma decisión que `ScoreBreakdown`: se
guarda lo que hace falta para explicarse, no la referencia con la que reconstruirlo.

El nombre del campo es `intake_record_id`, no `intake_id` como dice §6.11 del maestro: la entidad se
llama `IntakeRecord` desde F2b.

## 6. El flujo

```
IngestLeadUseCase / AssignLeadUseCase / ...
        │  commit
        ▼
  publisher.publish(LeadAssigned)
        │
        ▼
  NotificationHandler.handle_lead_assigned
        │
        ▼
  Notification(recipient=asesor, kind=LEAD_ASSIGNED, ...)  → persistida
```

El manejador **abre su propia unidad de trabajo**. No puede compartir la del caso de uso, porque el
evento se publica cuando ésa ya confirmó, y ése es justo el punto: un fallo al notificar no deshace
un lead ya guardado.

`InMemoryEventPublisher` ya captura las excepciones de sus manejadores, así que una notificación que
reviente **no rompe la ingesta**. Queda registrada en el log y el aviso se pierde. Es aceptable para
un MVP y es la consecuencia directa de no tener cola: se documenta como límite conocido.

## 7. Los endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/v1/notifications?unread_only=&limit=&offset=` | Las del que llama, paginadas, con contador |
| `POST` | `/api/v1/notifications/{id}/read` | Marca una |
| `POST` | `/api/v1/notifications/read-all` | Marca todas las suyas |

Los tres con `require_organization_member`: un asesor y un gestor consultan **las suyas**, y el
destinatario sale del token, nunca de la URL. Es la misma forma que `GET /leads/mine`.

La respuesta de la lista añade `unread_count` a los cinco campos del paginado habitual. Va ahí y no
en un endpoint aparte porque la campana necesita las dos cosas a la vez, y dos peticiones para
pintar un icono es lo que convierte el sondeo en un problema.

**La notificación de otro destinatario se lee como inexistente**: `404`, no `403`.

## 8. Migración 008

- Tabla `notifications`, con índice por `(recipient_id, is_read)` — es la consulta de la campana
- Retirada de nada: `webhook_dispatched` nunca fue una columna

La `007` la ocupa F2c.

## 9. Criterios de aceptación

| # | Criterio |
|---|---|
| 1 | Al asignarse un lead a un asesor, el asesor tiene una notificación no leída con el identificador del lead |
| 2 | Al reasignarse, la recibe el **nuevo** asesor |
| 3 | Un lead viable que no encuentra asesor produce una notificación a **todos** los gestores activos de la organización |
| 4 | Un registro de ingesta rechazado produce una notificación al gestor con el identificador del registro |
| 5 | `GET /notifications` devuelve sólo las del que llama, y su `unread_count` coincide con las no leídas |
| 6 | Marcar una como leída baja el contador; marcarlas todas lo deja en cero |
| 7 | La notificación de otro destinatario da **404** |
| 8 | Un fallo dentro del manejador **no** hace fallar la ingesta: el lead se guarda igual |
| 9 | `webhook_dispatched` no aparece en ninguna respuesta ni en ningún DTO |
| 10 | Suite en verde sin banderas, guardián 4/4, `pytest -m unit` sin variables de entorno |

El 8 es el que justifica que el manejador abra su propia transacción, y se prueba con un doble que
lanza.

## 10. Lo que esta fase deja abierto

- **El aviso se pierde si el manejador falla.** Sin cola no hay reintento. El log lo registra
- **No hay purga**: las notificaciones se acumulan sin caducidad ni archivado
- **Un lead borrado deja notificaciones huérfanas** que siguen mostrando su mensaje. El texto se
  guarda compuesto justo para que eso no rompa la vista, pero el enlace no llevará a ninguna parte
- **La conexión en autocommit del arranque sigue compartida entre hilos sin sincronización.** El
  maestro §11.4 dice que se elimina y no se ha eliminado; esta fase no la toca, pero suscribe un
  segundo manejador al mismo publicador, así que conviene no darla por resuelta
