# API · Errores

El formato de error unificado, de dónde sale cada código HTTP y qué significa cada código de
dominio. La tabla de códigos es la autoridad real del sistema:
`backend/src/infrastructure/adapters/input/api/exception_handlers.py`.

## El dominio no conoce HTTP

Una excepción de dominio (`DomainException`, en
`backend/src/domain/exceptions.py`) lleva un `message` y un
`error_code` estable, nunca un `status_code`: qué número HTTP le corresponde es una decisión del
adaptador de entrada, no del dominio. El guardián de arquitectura falla si el dominio llega a
importar algo que lo delate — ver [Convenciones](convenciones.md).

Un manejador global intercepta cualquier `DomainException` no controlada y la traduce a JSON:

```json
{
  "error": true,
  "error_code": "INVALID_EMAIL",
  "message": "Formato de correo electrónico inválido"
}
```

El código de estado sale de una única tabla, `STATUS_BY_ERROR_CODE`, indexada por `error_code`.
Lo que no figura en ella responde **400 Bad Request** por defecto — no porque cada caso se haya
decidido así uno por uno, sino porque un error de dominio que el cliente puede corregir es, salvo
que se diga lo contrario, un problema de la petición.

## Por qué 404 y no 403 entre organizaciones

Cuando un identificador válido pertenece a otra organización, la API responde **404 Not Found**,
igual que si no existiera — nunca **403 Forbidden**. Confirmar con un 403 que el recurso existe en
algún sitio, sólo que no aquí, ya es una fuga: permite mapear qué identificadores son válidos en
organizaciones ajenas por descarte. Cada caso de uso resuelve el recurso acotado por
`tenant_id` desde el principio (`get_by_id_and_tenant` o equivalente), así que uno ajeno nunca llega
a comprobarse: directamente no aparece. El razonamiento completo está en
[ADR-0005](../decisiones/0005-404-en-vez-de-403.md). De dónde sale ese `tenant_id` —siempre del
token, nunca de la URL ni del cuerpo— está en
[ADR-0004](../decisiones/0004-organizacion-desde-el-token.md).

## Autenticación y autorización

| `error_code` | HTTP | Significa |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | El correo o la contraseña no coinciden, o la organización del agente está desactivada |
| `UNAUTHORIZED` | 401 | Token ausente, caducado, inválido, o el agente ya no existe o está desactivado |
| `FORBIDDEN` | 403 | La identidad es válida, pero el rol o el plano (plataforma/organización) no alcanza para la acción |

## Recurso inexistente o ajeno

Todos responden **404**, con el mismo significado doble: no existe, o pertenece a otra
organización.

| `error_code` | Recurso |
|---|---|
| `AGENT_NOT_FOUND` | Agente |
| `LEAD_NOT_FOUND` | Lead — incluye el caso de un `AGENT` pidiendo el lead de un compañero |
| `GROUP_NOT_FOUND` | Grupo de ventas |
| `ASSIGNMENT_RULE_NOT_FOUND` | Regla de asignación |
| `DISQUALIFICATION_RULE_NOT_FOUND` | Regla de descalificación |
| `SCORING_RULE_NOT_FOUND` | Regla de puntuación |
| `SOURCE_NOT_FOUND` | Origen de leads — también cuando la organización no tiene uno activo para el canal que se está usando |
| `INTAKE_RECORD_NOT_FOUND` | Registro de la bandeja de ingesta |
| `INTAKE_JOB_NOT_FOUND` | Trabajo de ingesta |
| `NOTIFICATION_NOT_FOUND` | Notificación — incluye la de otro destinatario |
| `TENANT_NOT_FOUND` | Organización, en el plano de plataforma |

!!! warning "El nombre no decide el estado; esta tabla sí"
    Un código que termine en `_NOT_FOUND` **no** responde 404 por el nombre, sino por estar dado de
    alta en `STATUS_BY_ERROR_CODE`. Lo que no aparece ahí cae en el 400 por defecto, y ese fallo es
    silencioso: la petición responde, el cuerpo trae el código correcto, y sólo el número está mal.

    Al añadir un código de «no encontrado» nuevo, darlo de alta en esa tabla es parte de la tarea.

## Ya existe o está en uso

| `error_code` | HTTP | Significa |
|---|---|---|
| `TENANT_ALREADY_EXISTS` | 400 | Ya existe una organización con ese nombre |
| `EMAIL_ALREADY_EXISTS` | 400 | Ya existe un agente con ese correo, al crear una organización junto a su gestor |
| `SOURCE_ALREADY_EXISTS` | 400 | Ya existe un origen con ese nombre en la organización — el mismo nombre sí se acepta en otra |
| `GROUP_ALREADY_EXISTS` | 400 | Ya existe un grupo con ese nombre en la organización |
| `SOURCE_IN_USE` | 400 | El origen tiene leads asociados; borrarlo perdería su trazabilidad |

## Red de seguridad genérica en la persistencia

`PostgresUnitOfWork.__exit__` traduce estos dos si una violación de índice único o de clave foránea
llega desde psycopg sin que ningún caso de uso la haya comprobado antes de escribir. El mensaje es
deliberadamente genérico — a diferencia de `EMAIL_ALREADY_EXISTS` o `GROUP_NOT_FOUND`, no puede
señalar un campo concreto. Cuando existe una comprobación previa en el caso de uso, su código
específico responde primero y esta red nunca llega a activarse.

| `error_code` | HTTP | Significa |
|---|---|---|
| `ALREADY_EXISTS` | 400 | `UniqueViolation` sin comprobación previa en el caso de uso |
| `RELATED_ENTITY_NOT_FOUND` | 400 | `ForeignKeyViolation` sin comprobación previa en el caso de uso |

## Validación de campos

| `error_code` | HTTP | Significa |
|---|---|---|
| `INVALID_EMAIL` | 400 | Formato de correo inválido. Lo evalúa el dominio, no el esquema de entrada — ver la nota sobre `IngestLeadRequest` en [API · Referencia](api-referencia.md) |
| `INVALID_BUDGET` | 400 | Presupuesto negativo |
| `INVALID_UUID` | 400 | Un identificador no tiene forma de UUID válido |
| `INVALID_TENANT_NAME` | 400 | El nombre de la organización llega vacío, o no queda ningún carácter alfanumérico con el que construir su identificador (`slug`) |
| `INVALID_GROUP_NAME` | 400 | El nombre del grupo llega vacío |
| `INVALID_GROUP_CAPACITY` | 400 | `capacity_per_agent` es menor o igual que cero |
| `SOURCE_WITHOUT_NAME` | 400 | El nombre del origen llega vacío |
| `INVALID_FIELD_MAPPING` | 400 | `field_mapping` trae una clave o un valor vacíos |
| `INVALID_RULE_NAME` | 400 | El nombre de una regla de descalificación o de asignación llega vacío — es el motivo que verá el gestor, así que no es opcional |
| `INVALID_RULE_CONDITIONS` | 400 | Una regla de descalificación se crea o actualiza con `conditions` vacía: se cumpliría siempre y descalificaría a toda la organización |
| `INVALID_SCORE_BAND` | 400 | En una regla de asignación, `max_score` es menor que `min_score` |
| `RULE_WITHOUT_TARGET` | 400 | Una regla de asignación no apunta ni a un grupo (`target_group_id`) ni a asesores concretos (`target_agent_ids`) |

Las tres siguientes son de `Criterion`, la gramática de condiciones compartida por las reglas de
puntuación, asignación y descalificación — ver
[ADR-0011](../decisiones/0011-gramatica-de-condiciones.md):

| `error_code` | HTTP | Significa |
|---|---|---|
| `INVALID_RULE_FIELD` | 400 | El `field` de una condición llega vacío |
| `FIELD_NOT_SCORABLE` | 400 | El `field` no está en la lista blanca de campos evaluables ni empieza por `custom_attributes.` |
| `INVALID_RULE_VALUE` | 400 | El operador `IN` de una condición no recibe una lista |

## Transiciones de estado inválidas

| `error_code` | HTTP | Significa |
|---|---|---|
| `INVALID_LEAD_TRANSITION` | 400 | Asignar, reasignar o descartar un lead en un estado que no lo admite — por ejemplo, asignar uno ya `DISCARDED` |
| `DISCARD_WITHOUT_REASON` | 400 | El motivo del descarte llega vacío o en blanco |
| `INVALID_INTAKE_TRANSITION` | 400 | Promover, rechazar o descartar un registro de ingesta que ya está en un estado terminal (`PROMOTED` o `DISCARDED`) |
| `INVALID_JOB_TRANSITION` | 400 | Reprocesar un trabajo de ingesta que ya terminó (`COMPLETED` o `FAILED`) |
| `INVALID_INTAKE_STATUS` | 400 | El filtro `status` de la bandeja de ingesta no es un valor conocido |
| `INVALID_JOB_STATUS` | 400 | El filtro `status` de la lista de trabajos no es un valor conocido |
| `INVALID_LEAD_STATUS` | 400 | El filtro `status` de `GET /leads` o `GET /leads/mine` no es un valor conocido |

## Definidos, no alcanzables desde la API hoy

Estos códigos existen en el dominio como invariantes de defensa, pero cada camino que podría
dispararlos ya está cortado por una comprobación anterior en el caso de uso. Se documentan porque
aparecen en el código y alguien puede toparse con ellos leyendo, no porque un cliente vaya a
recibirlos:

| `error_code` | Dónde vive | Por qué no se alcanza hoy |
|---|---|---|
| `CROSS_TENANT_ASSIGNMENT` | `Lead._bind_agent()` | `AssignLeadUseCase` resuelve al asesor acotado por organización antes de llamar aquí; uno ajeno ya responde `AGENT_NOT_FOUND` |
| `EMPTY_CANDIDATE_POOL` | `AssignmentRule.advance_cursor()` | El motor de asignación filtra la lista de candidatos antes de rotar sobre ella |
| `REJECTION_WITHOUT_ERRORS` | `IntakeRecord.reject()` | El único llamador siempre adjunta al menos un error de campo |
| `INVALID_NOTIFICATION_MESSAGE` | `Notification` | Las notificaciones las crea el propio sistema; ningún endpoint recibe su mensaje como entrada |
| `DOMAIN_ERROR` | `DomainException` (valor por defecto) | Ningún caso de uso deja el `error_code` sin especificar |
| `INVALID_RULE` | `InvalidRuleException` | Definida en `domain/exceptions.py`; ningún caso de uso la levanta hoy |
| `ROUTING_FAILED` | `LeadRoutingException` | Definida en `domain/exceptions.py`; ningún caso de uso la levanta hoy |

## Fuera de la tabla de dominio

No son `DomainException`: los genera FastAPI o Starlette directamente, con el mismo sobre JSON.

| `error_code` | HTTP | Significa |
|---|---|---|
| `VALIDATION_ERROR` | 422 | El cuerpo, la query o el path no cumplen el esquema Pydantic del endpoint. La respuesta añade `details`: una lista con `field`, `code` y `message` por cada campo que falló |
| `INTERNAL_ERROR` | 500 | Fallo no controlado. El mensaje es siempre genérico a propósito — no expone detalle interno ni de base de datos; el detalle real queda en el log del contenedor |
| `NOT_FOUND` | 404 | Ninguna ruta coincide con la petición. No confundir con los `*_NOT_FOUND` de dominio, que sí identifican qué tipo de recurso falta |
| `METHOD_NOT_ALLOWED` | 405 | La ruta existe pero no admite ese verbo HTTP |

Ejemplo de `VALIDATION_ERROR`:

```json
{
  "error": true,
  "error_code": "VALIDATION_ERROR",
  "message": "La petición no supera la validación de esquema",
  "details": [
    {"field": "budget", "code": "float_parsing", "message": "Input should be a valid number"}
  ]
}
```

## Ver también

- [API · Referencia](api-referencia.md) — qué código de error puede devolver cada endpoint.
- [ADR-0005](../decisiones/0005-404-en-vez-de-403.md) — 404 en vez de 403.
- [ADR-0004](../decisiones/0004-organizacion-desde-el-token.md) — la organización sale del token.
