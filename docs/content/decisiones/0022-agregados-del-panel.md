# ADR-0022 · Agregados del panel

| | |
|---|---|
| **Estado** | Aceptada — `pending_intake` pasó a `GET /intake/stats` en F4 ([ADR-0036](0036-cambios-de-contrato-publico.md)); el resto sigue vigente |
| **Fecha** | 2026-08-10 |
| **Ámbito** | Backend · Aplicación |

## Contexto

La vista «Panel» del roadmap pinta cinco indicadores a la vez: leads del periodo, distribución por
estado, sin asignar, bandeja pendiente y carga por asesor. No existe hoy ningún endpoint que los
calcule. La única forma de obtenerlos es traerse la organización entera con `GET /leads` y contar en
el navegador, lo que además choca con el techo `le=1000` de paginación: una organización con más
leads que ese límite no puede pintar una cifra correcta sin paginar y sumar en el cliente.

`GET /leads` ya acepta `status`, `assigned_agent_id`, `group_id`, `source_id` y `q`, y todos los
listados devuelven el mismo sobre `{items, total, limit, offset, has_more}`. Ese filtro resuelve
«dame los leads que cumplen una condición»; no resuelve «dame cinco cifras distintas a la vez», que
exigiría cinco peticiones filtradas — una por indicador — para pintar una sola pantalla. Contar no es
listar.

Es también la primera vez que la API expone una lectura cuya respuesta no son entidades sino cifras
derivadas. El guardián 4/4 no hace excepciones para este tipo de lectura: pasa por el mismo camino
que cualquier otra — puerto de repositorio, caso de uso en la aplicación, sobre de respuesta en el
borde HTTP — sin atajo que salte capas.

## Decisión

Se añade un único endpoint, `GET /leads/stats`, bajo el mismo prefijo que `GET /leads` y declarado
antes de `GET /leads/{lead_id}` — como ya hace `GET /leads/mine` — para que FastAPI no intente
interpretar `stats` como un UUID de ruta paramétrica.

Sólo lo puede pedir un `MANAGER`, con `require_organization_manager` y sin rama por rol: es la foto
de la organización entera, igual que `GET /leads`. El asesor no tiene panel de organización; su vista
es «Mis leads».

Acepta `from` y `to` opcionales, ambos fechas, para acotar «leads del periodo». Sin ellos, la cifra
es «desde siempre» — lo que un MVP necesita el primer día que se enciende, antes de que exista
histórico que recortar. Con ellos, el cliente puede pedir «últimos 30 días» sin que la API tenga que
saber qué es un periodo de negocio. Si `from` es posterior a `to`, la API responde `400`: un rango
imposible es un error del cliente, no una respuesta vacía que lo disimula.

La cifra de carga por asesor reutiliza `LeadRepositoryPort.active_load_by_agent`
(`raw_sql_lead_repository.py:259-276`), que ya devuelve `{agent_id: nº de leads ASSIGNED}` y es la
misma consulta que usa el motor de asignación. No se escribe una segunda consulta que cuente lo
mismo de otra manera: dos consultas que dicen lo mismo acaban discrepando.

Nada se cachea ni se materializa. Sin tabla de contadores, sin columna incrementada: todo se deriva
en el momento de la lectura, por la misma razón que ya vale para `active_load_by_agent` — un contador
que sólo se incrementa se desincroniza de la realidad en cuanto un lead se descarta o se reasigna.

### Forma de la respuesta

```json
{
  "total": 1240,
  "by_status": {
    "NEW": 12,
    "QUALIFIED": 300,
    "DISQUALIFIED": 88,
    "UNASSIGNED": 40,
    "ASSIGNED": 700,
    "DISCARDED": 100
  },
  "unassigned": 40,
  "pending_intake": 17,
  "load_by_agent": [
    { "agent_id": "5c8a...", "name": "Ana Ruiz", "active_leads": 23 }
  ]
}
```

**`by_status` lleva siempre los seis valores de `LeadStatus`**, con `0` donde no haya leads. Un panel
que recibe un mapa con huecos tiene que conocer la lista completa de estados para pintar la barra
completa, y entonces esa lista vive en dos sitios — el backend y el frontend — con el riesgo de que
diverjan. Que la respuesta sea completa desde el origen hace al cliente tonto, que es donde conviene
que esté la tontería.

**`unassigned` es redundante con `by_status["UNASSIGNED"]`, y se queda así.** Es el indicador propio
que pide el roadmap, y sacarlo del mapa obligaría al cliente a saber que «sin asignar» se llama
`UNASSIGNED` dentro de `LeadStatus`. La redundancia cuesta una línea en la respuesta; el acoplamiento
a un nombre de estado interno cuesta una release cuando ese nombre cambie.

**`pending_intake` cuenta los registros de entrada en `PENDING` y `REJECTED`.** Son los dos estados
de `intake_record` sobre los que un gestor tiene algo pendiente que hacer — corregir, reintentar o
descartar. `PROMOTED` y `DISCARDED` ya están cerrados y no pertenecen a una bandeja de pendientes.

**`load_by_agent` incluye el nombre del asesor, no sólo su identificador.** Un panel que recibe UUIDs
tendría que pedir `GET /agents` para pintar una barra con nombre, y entonces son dos peticiones para
una sola pantalla — exactamente lo que este endpoint existe para evitar. Implica que la consulta cruza
`leads` con `agents`; no cambia el dominio, sólo la consulta SQL que arma el DTO de respuesta.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Cinco endpoints, uno por indicador | El panel pinta las cinco cifras a la vez; cinco peticiones para una pantalla es el mismo error que [ADR-0015](0015-notificaciones-por-sondeo.md) evitó al meter `unread_count` dentro de la página de notificaciones en vez de darle endpoint propio |
| Contar en el cliente sobre `GET /leads` paginado | Exige traerse la organización entera al navegador, choca con el techo `le=1000` de paginación en cualquier organización grande, y mueve el trabajo de agregación al sitio donde cuesta más — serializar y transferir filas en vez de un `GROUP BY` en base de datos |
| Contador materializado (columna o tabla de agregados) | Introduce el mismo problema que `active_load_by_agent` ya resolvió al no materializarse: un contador que sólo se incrementa se desincroniza de la realidad en el primer lead que se descarta o reasigna, y este MVP no tiene el volumen que justificaría pagar esa complejidad |
| `by_status` sólo con los estados presentes | Obliga al cliente a conocer la lista completa de `LeadStatus` para rellenar los huecos al pintar, duplicando esa lista entre backend y frontend |
| `load_by_agent` sólo con `agent_id` | Obliga al cliente a una segunda petición a `GET /agents` para resolver el nombre antes de pintar, contradiciendo el motivo de existir de este endpoint |

## Consecuencias

**Fácil:** el panel se pinta con una sola petición y sin traerse ninguna entidad completa al
navegador; la cifra de carga por asesor no puede discrepar de la que usa el motor de asignación,
porque es la misma consulta. Un rango `from`/`to` inválido se detecta en el borde, antes de tocar
base de datos.

**Difícil:** cada indicador nuevo que el panel quiera en el futuro crece esta misma respuesta en vez
de tener endpoint propio, así que el DTO de agregados necesita revisión cada vez que el roadmap añada
una cifra — el mismo trueque que ya aceptó ADR-0015 para las notificaciones. `by_status` fijo a los
seis valores de `LeadStatus` significa que añadir un estado nuevo al dominio obliga a tocar también
esta respuesta.

## Ver también

- [ADR-0015 · Notificaciones por sondeo](0015-notificaciones-por-sondeo.md)
- [ADR-0005 · 404 en vez de 403](0005-404-en-vez-de-403.md)
