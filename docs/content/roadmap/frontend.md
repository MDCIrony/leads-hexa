# Frontend

Qué tiene que construir la interfaz web, la pieza más grande que le falta al proyecto para ser un
producto usable.

## Punto de partida

El backend cubre el recorrido completo de un lead: ingesta, viabilidad, puntuación, asignación,
bandeja de revisión y notificaciones. Cada operación de la
[referencia de la API](../desarrollo/api-referencia.md) tiene ya su caso de uso probado. Lo que
falta es la interfaz que lo consuma.

La interfaz actual es una maqueta desconectada de ese backend, no un punto de partida a medias:

- Las capas de dominio e infraestructura del frontend existen y compilan, pero ningún componente
  de presentación las importa. El grafo de dependencias está partido en dos mitades que no se
  tocan.
- Todo el estado vive en el componente raíz con datos escritos a mano; no hay llamada real al
  backend en ningún punto de la navegación.
- La navegación es una variable de estado local, no un enrutador: no hay URLs propias por
  pantalla, ni enlaces directos, ni botón atrás.
- La carga masiva no sube ningún fichero: fabrica un lead de ejemplo y lo añade a la lista en
  memoria.
- No existe manejo de sesión: ni login, ni almacenamiento del token, ni interceptor que lo añada a
  las peticiones, ni noción de rol.
- El cliente HTTP fija `Content-Type: application/json` de forma fija, lo que rompería el login en
  cuanto se conectara: ese endpoint espera `form-urlencoded`.

## Arquitectura a construir

Se conserva la separación en capas ya presente —está bien planteada— pero hay que conectarla de
verdad:

```
src/
├── domain/           modelos y tipos de negocio
├── application/      mappers, servicios y hooks de caso de uso
├── infrastructure/   cliente HTTP, DTOs generados, almacenamiento de sesión
└── presentation/     páginas, componentes, rutas y guards
```

| Elemento | Qué debe resolver |
|---|---|
| Enrutado | Rutas declarativas con URLs propias, enlaces directos y navegación con botón atrás |
| Sesión | Token en memoria con rehidratación al recargar, interceptor que añade la cabecera de autorización, manejo centralizado de sesión expirada y de acceso denegado |
| Datos | Una capa de datos con caché, reintentos y estados de carga y error explícitos, que hoy no existen en ninguna vista |
| Tipos del API | Generados desde el contrato del backend en vez de escritos a mano, para que un cambio de contrato rompa la compilación del frontend en lugar de fallar en producción |
| Guards | Por rol: el gestor accede a la gestión completa, el asesor sólo a su propio panel |
| Estilos | Se mantienen Tailwind y los componentes ya escritos |

```mermaid
flowchart LR
    P[presentation] --> A[application]
    A --> D[domain]
    A --> I[infrastructure]
    I --> B[(API del backend)]
```

## La API, mapeada en servicios

La superficie del backend son **48 operaciones**, y se agrupa en **diez servicios**. Cada uno cubre
un recurso completo y es la única puerta de la interfaz hacia él: ninguna página llama a la API por
su cuenta.

Esta tabla es el alcance de la primera pieza a construir. Los contratos exactos —campos, tipos,
obligatoriedad— no se copian aquí: se generan desde `/openapi.json`, que es la única fuente que no
puede desincronizarse. Lo que fija esta tabla es **qué servicio existe, qué operaciones expone y qué
contrato devuelve cada una**.

| Servicio | Operaciones | Contrato de salida |
|---|---|---|
| `auth` | `POST /auth/login` · `GET /auth/me` | `LoginResponse` · `CurrentUserResponse` |
| `tenants` | `GET` lista · `POST` · `PATCH /{id}` | `PaginatedTenantsResponse` · `TenantResponse` |
| `agents` | `GET` lista · `POST` · `GET /{id}` · `PATCH /{id}` · `DELETE /{id}` | `PaginatedAgentsResponse` · `AgentResponse` |
| `groups` | `GET` lista · `POST` · `PATCH /{id}` · `DELETE /{id}` | `PaginatedGroupsResponse` · `SalesGroupResponse` · `204` |
| `sources` | `GET` lista · `POST` · `PATCH /{id}` · `DELETE /{id}` | `PaginatedSourcesResponse` · `LeadSourceResponse` · `204` |
| `leads` | `GET` lista · `GET /mine` · `GET /{id}` · `POST /{id}/assign` · `POST /{id}/discard` | `PaginatedLeadsResponse` · `LeadDetailResponse` |
| `leadStats` | `GET /leads/stats` | `LeadStatsResponse` |
| `intake` | `POST /leads/ingest` · `POST /leads/batch-upload` · `GET /records` · `POST /records/{id}/promote` · `POST /records/{id}/discard` | `IntakeAcceptedResponse` · `IntakeRecordsPageResponse` · `LeadProcessedResponse` · `204` |
| `intakeJobs` | `GET /jobs` · `GET /jobs/{id}` · `POST /jobs/{id}/reprocess` | `IntakeJobsPageResponse` · `IntakeJobResponse` |
| `rules` | Tres familias —puntuación, asignación, descalificación— cada una con `GET` lista, `POST`, `PATCH /{id}`, `DELETE /{id}` | `Paginated*RulesResponse` · `*RuleResponse` · `204` |
| `notifications` | `GET` lista · `POST /read-all` · `POST /{id}/read` | `NotificationsPageResponse` · `204` |

### Cinco reglas del contrato que la capa de servicios tiene que absorber

Son las que, si no se resuelven una sola vez en la capa de servicios, se repiten mal en cada página.

**Todos los listados devuelven el mismo sobre.** `{items, total, limit, offset, has_more}`, sin
excepción en los dieciséis. Un solo tipo genérico y un solo hook de paginación los cubren todos.

**Todo lo temporal viene de lo más nuevo a lo más antiguo.** Leads, notificaciones, organizaciones,
registros y trabajos de entrada. Ninguna vista tiene que reordenar en cliente.

**El login no es JSON.** `POST /auth/login` espera `form-urlencoded` y el correo viaja en el campo
`username`. Es la única operación que se sale del JSON, y es la primera que se implementa.

**La organización sale del token, nunca de la URL ni del cuerpo.** No hay `tenant_id` que enviar en
ninguna petición: un `tenant_id` en el cuerpo se ignora en silencio.

**La ingesta responde `202`, no `200`.** El lead no existe todavía cuando la petición vuelve: hay que
sondear `GET /intake/jobs/{id}` hasta estado terminal. Es el único flujo asíncrono de la interfaz y
merece un hook propio.

### Dos cosas que la API deliberadamente no da

**El listado de leads no trae el nombre del asesor**, sólo `assigned_agent_id`. La tabla resuelve el
nombre pidiendo `GET /agents` una vez y mapeando en cliente; el listado no infla cada fila con datos
de otra entidad. (`GET /leads/stats` sí trae nombres, porque su barra de carga por asesor los
necesita y evitar una segunda petición era justamente su motivo.)

**No existe `GET /groups/{id}`.** El detalle de un grupo sale de la lista, y sus miembros de
`GET /agents?group_id=`.

## Los tres roles

Cada rol ve una aplicación distinta, no la misma con botones ocultos. El rol viaja en el token y se
lee con `GET /auth/me`.

| Rol | Alcance | Qué recibe fuera de él |
|---|---|---|
| `ADMIN` | Sólo el plano de plataforma: organizaciones | `403` en todo lo operativo |
| `MANAGER` | Su organización entera | `404` al leer algo de otra organización |
| `AGENT` | Lo suyo: sus leads y sus avisos | `404` al pedir el lead de un compañero, no `403` |

Que un lead ajeno responda `404` y no `403` **no es un detalle de implementación**: la interfaz tiene
que tratarlo como «no existe», sin insinuar que existe en otro sitio. Ver
[ADR-0005](../decisiones/0005-404-en-vez-de-403.md).

## Vistas y funcionalidad mínima

Lo que sigue acota **qué tiene que hacer cada vista para considerarse terminada**. No dice cómo.

### Panel del administrador de plataforma

Es el rol que hoy no tiene ninguna pantalla, y sin él no hay forma de dar de alta una organización
sin `curl`.

| Vista | Funcionalidad mínima |
|---|---|
| Organizaciones | Listar paginado; dar de alta una organización con su gestor en un solo formulario; renombrar; activar y desactivar |

### Panel del gestor

| Vista | Funcionalidad mínima |
|---|---|
| Panel | Pintar las cinco cifras de `GET /leads/stats` en una sola petición: total, distribución por estado, sin asignar, bandeja pendiente y carga por asesor. Acotar por periodo con `from`/`to` |
| Leads | Tabla paginada con los cinco filtros del backend —estado, asesor, grupo, fuente y búsqueda— combinables entre sí, y columna de asesor asignado |
| Detalle del lead | Ficha completa, desglose de las reglas que produjeron la puntuación, motivo de descalificación o descarte cuando lo haya, asignación manual a un asesor y descarte con motivo |
| Bandeja de entrada | Registros de entrada con su estado; para uno rechazado, ver el payload tal como llegó y el error por campo; corregir y reintentar, o descartar |
| Alta de lead | Formulario individual que **valida en cliente lo que el esquema exige**, y espera al procesamiento antes de dar el alta por buena |
| Carga masiva | Subida real de fichero, seguimiento del trabajo hasta estado terminal, y resumen del resultado fila a fila |
| Trabajos de entrada | Listado de cargas con su estado y contadores; reprocesar una que quedó a medias |
| Asesores | Alta, edición, asignación a grupo, **desactivar y reactivar**, y ver los desactivados con `?is_active=false` |
| Grupos | Alta, edición y borrado; estrategia por defecto, capacidad por asesor; ver sus miembros |
| Orígenes | Alta, edición y borrado; mapeo de columnas del fichero a los campos de la plataforma |
| Reglas de puntuación | Alta, edición, activación y borrado; constructor de condiciones con campo, operador y valor; puntos y prioridad |
| Reglas de asignación | Alta, edición, activación y borrado; rango de puntuación, destino por grupo o por asesores, modo de coincidencia, estrategia y prioridad |
| Reglas de descalificación | Alta, edición, activación y borrado; constructor de condiciones |
| Notificaciones | Campana con contador de no leídas, desplegable paginado, marcar una y marcar todas, y navegar al elemento relacionado |

### Panel del asesor

| Vista | Funcionalidad mínima |
|---|---|
| Mis leads | Lista paginada de los leads asignados, ordenada por fecha de asignación, con filtro por estado y búsqueda |
| Detalle del lead | Ficha completa con contacto, empresa, presupuesto, sector, atributos personalizados, puntuación y su desglose |
| Notificaciones | Campana con contador, marcar leídas y navegar al lead |

### Transversal a los tres

| Vista | Funcionalidad mínima |
|---|---|
| Login | Entrada única; guardar el token, rehidratarlo al recargar, y llevar a cada rol a su panel |
| Errores y sesión | Un `401` cierra la sesión y vuelve al login; un `403` explica que el rol no alcanza; un `404` dice que no existe; un `422` señala el campo; un `500` ofrece reintentar |

## Qué ya existe y se puede aprovechar

Los componentes React ya escritos —cabecera, barra lateral, tabla de panel, formulario de reglas,
cargador de ficheros, ajustes de asesor— están construidos sobre Tailwind y no necesitan
rehacerse. El trabajo es conectarlos a datos reales, no reemplazarlos.

## Correcciones puntuales

Aparte de la arquitectura, hay defectos concretos que arrastrar aunque se reescriban las vistas:

- La lectura de la lista de leads debe interpretar la respuesta paginada del backend
  (`items`, `total`, `limit`, `offset`, `has_more`), no un array suelto.
- El proxy de desarrollo del servidor local debe apuntar al backend; sin él, el modo de desarrollo
  no puede hablar con la API.
- El cliente HTTP fija `Content-Type: application/json` para todas las peticiones. El login lo
  necesita `form-urlencoded` y la carga masiva, `multipart/form-data`: la cabecera tiene que
  decidirse por petición, no una vez para todas.

## El `422` que no deja rastro

Un formulario de alta de lead **tiene que validar en cliente lo que el esquema de entrada exige**
—campos obligatorios y tipos—, y no por cortesía con el usuario.

La plataforma promete que nada de lo que entra se pierde, y lo cumple para lo que falla en el
dominio: un correo mal escrito responde `202` y queda en la bandeja con su motivo, listo para
corregir. Pero lo que falla en el **esquema** —falta un campo, el presupuesto llega como texto— se
rechaza con un `422` antes de que la ingesta llegue a ejecutarse, y **ese payload no se guarda en
ninguna parte**. El usuario no puede recuperarlo desde la bandeja porque nunca llegó a ella.

Mientras el esquema de entrada siga siendo fijo, la única red es el formulario. La solución de fondo
—que la recepción acepte cualquier cuerpo y sea la definición de cada organización la que decida si
encaja— está descrita en [La definición del lead](definicion-del-lead.md).
