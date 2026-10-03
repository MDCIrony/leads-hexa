# ADR-0025 · Outbox transaccional

| | |
|---|---|
| **Estado** | Aceptada. **Nota:** `OutboxRelayThread` y el `OutboxRelay` de aplicación los sustituye `chassis.outbox.OutboxRelay` (con `run_relay`), un relay por canal que corre en `backend-worker` y no en la API ([ADR-0033](0033-eventos-internos-en-kafka.md)); `OutboundDispatcherPort` es hoy el protocolo `Dispatcher` de `chassis.outbox`. La decisión no cambia |
| **Fecha** | 2026-08-24 |
| **Ámbito** | Backend · Dominio · Aplicación · Infraestructura |

## Contexto

`IngestLeadUseCase` publica el evento de salida (`LeadProcessedEvent` o `LeadDisqualified`)
**después** del `commit`, a propósito ([ADR-0024](0024-el-contrato-de-salida-se-construye-una-vez.md)):
un aviso que falla no debe deshacer un lead ya guardado. El precio es la ventana inversa — si el
proceso muere entre el commit y la publicación, el lead existe en la base y el cliente no se entera
**nunca**.

Hoy esa ventana son microsegundos y el publicador vive en memoria dentro del mismo proceso: casi
nunca falla entre esas dos líneas. En cuanto el canal de salida hable con un bróker real, la misma
ventana deja de ser un caso de laboratorio: publicar implica una llamada de red, y una llamada de
red que falla o que tarda es justo lo que ocurre con regularidad.

La promesa del producto es que el cliente puede reobtener los leads filtrados que le corresponden.
Perder uno en esa ventana la rompe en silencio — nada en el sistema sabe que faltó.

## Decisión

El outbox resuelve las dos caras del problema a la vez, no una sola: el registro del evento se hace
dentro de la misma transacción que guarda el lead —es un `INSERT` en `outbox_events`, no un efecto
lateral que pueda fallar por su cuenta—, y la entrega ocurre fuera, en un proceso separado que lee
esa tabla. Un rollback se lleva el evento con él; una entrega que falla no toca el lead.

**El outbox es sólo para el canal de salida.** `LeadProcessedEvent` y `LeadDisqualified` —el
catálogo que fijó el [ADR-0023](0023-eventos-del-canal-de-salida.md)— se registran en la tabla
dentro de la transacción del caso de uso, a través de un nuevo `OutboxRepositoryPort`. Los eventos
**internos** —`LeadAssigned`, `LeadReassigned`, `LeadLeftUnassigned`, `IntakeRejected`— se siguen
entregando en proceso y síncronos después del commit, como hasta ahora: su consumidor está aquí
dentro, el usuario espera ver la notificación al recargar el panel, y meterlos en el outbox
retrasaría lo único que hoy es inmediato.

**El relay entrega, el caso de uso no.** Un `OutboxRelay` (capa de aplicación) recorre
periódicamente las filas sin publicar y las reparte entre uno o más `OutboundDispatcherPort`. El
primero es `WebhookOutboundDispatcher`, que usa el `WebhookRepositoryPort` y el
`WebhookDispatcherPort` que ya existían; Kafka llegará como un segundo despachador, sin tocar el
relay ni el punto de registro. El `WebhookEventHandler` **se retira**: el relay es ahora el único
camino a un webhook, y dejar la clase habría sido una segunda copia del mismo bucle de búsqueda y
envío, alcanzable sólo desde su propia prueba. El webhook se vuelve asíncrono —hasta un ciclo del
relay de retraso— y a cambio deja de perderse cuando el proceso muere entre el commit y la entrega.

**Un ciclo del relay son tres pasos, no uno: leer, entregar, registrar.** La entrega ocurre con la
transacción de lectura ya cerrada, y esto es deliberado: entregar dentro de ella mantendría una
conexión del pool ocupada mientras se hacen tantas llamadas de red como entradas tenga el lote, y un
puñado de receptores que agotan su tiempo de espera vaciaría el pool del que vive la API. El precio
es que dos relays en paralelo pueden entregar la misma entrada dos veces; es exactamente lo que
significa *at-least-once*, y para eso el consumidor tiene el `event_id`.

**Nada se descarta por haberse reintentado demasiadas veces, y el lote se ordena por número de
intentos.** Ordenar sólo por antigüedad dejaba que un destino roto de forma permanente saliera
siempre primero y dejase sin sitio a todo lo de detrás. Un tope de reintentos habría sido peor: un
bróker caído unos segundos lo agotaría, y se perderían exactamente los leads que esta tabla existe
para no perder. Con `ORDER BY attempts, occurred_on`, una entrada que falla se hunde en el orden
—las nuevas la adelantan— y se sigue reintentando el tiempo que haga falta, con su `last_error` a
la vista de quien opere el sistema.

Un `OutboxRelayThread` —hilo daemon, arrancado en el `lifespan` de la API y detenido antes de cerrar
la base— llama a `OutboxRelay.drain()` cada segundo (configurable vía `OUTBOX_RELAY_INTERVAL_SECONDS`).
No es `BackgroundTasks` de FastAPI: esas tareas son por petición, y este trabajo es periódico e
independiente de cualquier request. El [ADR-0019](0019-trabajo-de-fondo-en-proceso.md) sigue
respetado en lo que importa —mismo proceso, sin bróker ni trabajador externo—; sólo cambia el
mecanismo concreto para este trabajo de fondo en particular, que un hilo con temporizador cubre y
las tareas por petición no.

El evento se serializa una sola vez, en el propio evento (`DomainEvent.as_payload()`), para que el
outbox hoy y Kafka mañana no acaben con dos conversiones que mantener sincronizadas.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Publicar tras el commit y aceptar la pérdida (el comportamiento actual) | Es el defecto que motiva este ADR: una ventana pequeña hoy que se vuelve frecuente en cuanto el canal de salida hable con un bróker real |
| Two-phase commit entre Postgres y el bróker de salida | Ningún cliente de Kafka —ni de la mayoría de bróker— ofrece 2PC contra Postgres; exigiría coordinar dos sistemas transaccionales distintos con garantías que ninguno de los dos expone |
| Meter también los eventos internos en el outbox, para tener un solo mecanismo de publicación | Retrasaría lo único que hoy es inmediato: la notificación en el panel que el usuario espera ver al recargar. Dos catálogos con dos criterios ya es la frontera que trazaron el ADR-0023 y el ADR-0024 |

## Consecuencias

**Fácil:** ningún lead se guarda sin que su publicación quede registrada, y al revés — el rollback se
lleva el evento con el lead. Añadir Kafka en 2.2 es un segundo `OutboundDispatcherPort`, no un cambio
al relay ni al punto de registro dentro de los casos de uso.

**Difícil:** la entrega es *at-least-once*, no exactly-once — un despachador que falla a mitad de un
`drain()` deja la fila sin publicar, y el siguiente ciclo la reintenta entera, incluidos los
despachadores que ya habían tenido éxito. El `id` de la fila es el `event_id` del propio evento,
precisamente para que el consumidor pueda deduplicar por él. El webhook, que hoy es síncrono, pasa a
tener hasta un ciclo del relay de retraso. Y la tabla crece sin que nada la pode: las filas
publicadas se quedan ahí. Es a propósito mientras sean el único registro de lo que salió, pero un
despliegue con volumen real necesitará archivarlas, y ese trabajo todavía no existe.

## Ver también

- [ADR-0019 · Trabajo de fondo en el mismo proceso](0019-trabajo-de-fondo-en-proceso.md)
- [ADR-0023 · Los eventos del canal de salida](0023-eventos-del-canal-de-salida.md)
- [ADR-0024 · El contrato de salida se construye una vez](0024-el-contrato-de-salida-se-construye-una-vez.md)
