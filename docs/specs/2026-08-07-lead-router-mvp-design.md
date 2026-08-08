# Lead Router — Diseño del MVP

**Fecha:** 2026-08-07
**Estado:** propuesto, pendiente de revisión
**Ámbito:** backend (refactor arquitectónico + funcionalidad nueva) y frontend (arquitectura + vistas)

---

## 1. Objetivo

Plataforma multi-tenant de **captación, calificación y asignación automática de leads** a asesores comerciales, construida como MVP demostrable para un curso de arquitectura de software.

El sistema debe:

1. Recibir leads por formulario individual, carga masiva CSV/XLSX y —en una iteración posterior— webhooks de plataformas externas.
2. Puntuarlos con reglas configurables por la organización.
3. Asignarlos automáticamente a un asesor según reglas por grupo o por asesor concreto.
4. No perder nunca un lead: lo que no valida o no se puede asignar queda visible para intervención manual del gestor.
5. Avisar dentro de la aplicación a quien corresponda: al asesor cuando recibe un lead, al gestor cuando algo requiere su intervención.

Los criterios de calidad son los propios de la asignatura: **arquitectura hexagonal estricta, desacoplamiento real, inversión de dependencias efectiva y patrones de diseño justificados**. El sistema debe arrancar completo con un único `docker compose up`.

---

## 2. Estado de partida

Diagnóstico realizado sobre el código, no sobre la documentación. Evidencia ejecutada:

| Comprobación | Resultado |
|---|---|
| `uv run pytest` | 12 fallan / 59 pasan — todos por `KeyError: 'DATABASE_URL'` |
| `tsc && vite build` | Pasa limpio |
| `docker compose config` | Válido |
| `docker compose build` | Ambas imágenes construyen |
| Llamadas HTTP reales del frontend | Cero |

### 2.1 Lo que se conserva

- `domain/` no importa ningún framework. La regla de dependencias se respeta en esa capa.
- Puertos ABC razonablemente completos y mocks in-memory funcionando.
- 12 endpoints operativos con RBAC (JWT + bcrypt) y regla de bootstrap del primer administrador.
- Raw SQL sobre PostgreSQL con sentencias parametrizadas.
- `docker-compose.yml` correcto: tres servicios, healthchecks, volumen persistente.
- 58 tests unitarios genuinamente offline.
- Los 11 componentes React existentes (el trabajo de Tailwind es sólido y se aprovecha).

### 2.2 Violaciones de la regla de dependencias

| Ubicación | Violación |
|---|---|
| `application/use_cases/auth_use_cases.py:4-5` | La aplicación importa `infrastructure.security` (`verify_password`, `create_access_token`) |
| `application/use_cases/agent_use_cases.py:10` | La aplicación importa `infrastructure.security.password_hasher.hash_password` |
| `application/dtos/commands.py:46`, `queries.py:2` | Pydantic dentro de la capa de aplicación |
| `adapters/input/api/agent_router.py:36-63` | El router accede directamente al repositorio (`uow.agents.count()`) e implementa reglas de negocio |
| `domain/exceptions.py:3` | Códigos HTTP dentro del dominio (`status_code = 400`) |
| `application/ports/input/*` | Los puertos de entrada devuelven entidades de dominio; el hash de contraseña llega hasta el DTO de respuesta |

### 2.3 Defectos funcionales

| Defecto | Causa |
|---|---|
| `ROUND_ROBIN` siempre elige el mismo agente | `RouterEngine` se instancia por request; el cursor vive en memoria de instancia |
| `DIRECT_AGENT` no dirige a nadie | Devuelve `eligible_agents[0]`, idéntico al caso por defecto |
| El operador `IN` nunca se cumple | `CreateScoringRuleCommand.value: str` fuerza cadena; el motor exige lista |
| Ingesta individual y carga masiva sin autenticación | Cualquiera puede inyectar leads en cualquier tenant |
| Fuga cross-tenant en la asignación | `get_available_agents()` no filtra por tenant |
| Fuga cross-tenant en listados | `GET /agents` devuelve agentes de todas las organizaciones |
| Paginación no determinista | `list_by_tenant` sin `ORDER BY` |
| `active_leads_count` nunca decrece, con *lost update* | Read-modify-write sin atomicidad, y no hay cierre de leads |
| Un lead con email inválido se pierde | Devuelve `FAILED` sin persistir nada |
| `applied_rules_count` miente | Cuenta reglas consultadas, no aplicadas |
| `webhook_dispatched` miente | Es `True` con sólo existir el publicador |

### 2.4 Deuda de infraestructura

Sin índices, sin claves foráneas, sin `UNIQUE` en `agents.email`, sin migraciones versionadas, sin pool de conexiones, sin logging, sin `.dockerignore`, sin `conftest.py`, sin marcadores de pytest. Los tipos de columna son `TEXT` donde deberían ser `UUID`, `TIMESTAMPTZ`, `NUMERIC` y `JSONB`.

### 2.5 Frontend

Es una maqueta. Las capas `application/` e `infrastructure/` existen y compilan, pero **ningún componente las importa**: el grafo de dependencias está partido en dos mitades desconectadas. Todo el estado vive en `App.tsx` con datos inventados, la navegación es un `useState` (no hay router), y `handleUploadBatch` lleva el comentario literal `// Simulación de carga batch para UI` y fabrica un lead falso en lugar de subir el fichero.

No hay login, ni almacenamiento de token, ni interceptor de autorización, ni noción de rol en el modelo. Además hay cuatro desajustes de contrato con el backend; el más grave: `getLeads()` espera un array y el backend devuelve un objeto paginado, así que `.map` reventaría en cuanto se conectara.

---

## 3. Modelo de negocio objetivo

### 3.1 Actores

| Actor | Rol técnico | Qué hace |
|---|---|---|
| Administrador de plataforma | `ADMIN` | Da de alta organizaciones y a su primer gestor. No pertenece a ninguna organización |
| Gestor comercial | `MANAGER` | Administra su organización: asesores, grupos, reglas de asignación, fuentes. Ve todos los leads, resuelve los que fallan, asigna manualmente y descarta |
| Asesor de ventas | `AGENT` | Ve únicamente los leads asignados a él y su detalle. Recibe notificaciones |

### 3.2 Recorrido principal

1. El gestor entra, crea sus **grupos de venta** ("Ventas Norte", "Enterprise") y da de alta a sus **asesores**, asignando cada uno a un grupo.
2. Define **reglas de puntuación**: qué características de un lead suman o restan puntos.
3. Define **reglas de asignación**: a partir de qué puntuación, a qué grupo o a qué asesores concretos, y con qué estrategia de reparto.
4. Entran leads —por formulario, por carga masiva de fichero, o (más adelante) por webhook de una plataforma externa.
5. Cada lead se puntúa, se califica y se asigna automáticamente. El asesor recibe una notificación.
6. Si un lead no valida o no encuentra asesor, queda visible para el gestor, que lo corrige, lo asigna a mano o lo descarta. También recibe notificación.
7. El asesor entra a su panel y ve su lista de leads asignados con el detalle de cada uno.

---

## 4. Decisiones de arquitectura

Decisiones tomadas en la sesión de diseño, con su justificación.

| # | Decisión | Alternativa descartada | Motivo |
|---|---|---|---|
| D1 | `SalesGroup` es una entidad de primera clase con clave foránea real | Mantener `team: String` libre | Con una cadena suelta no hay CRUD de grupos, no se pueden definir políticas por grupo, y un error tipográfico deja la regla muerta en silencio |
| D2 | Multi-tenancy se conserva, pero el tenant **se deriva del token**, no de la URL | Conservar `/tenants/{tenant_id}/…` | Cierra de raíz las fugas cross-tenant: el cliente deja de poder elegir a qué organización accede. Simplifica el frontend |
| D3 | Tres roles: `ADMIN` (plataforma), `MANAGER` (organización), `AGENT` | Dos roles | Refleja un SaaS real y aprovecha el RBAC ya implementado |
| D4 | Los leads inválidos se capturan en un agregado separado, `IntakeRecord` | Relajar los value objects del `Lead` | La invariante "un `EmailAddress` siempre es válido" es el mejor argumento arquitectónico del proyecto; relajarla lo destruiría. Con un agregado de ingesta, el `Lead` nunca existe en estado inválido |
| D5 | Notificaciones internas por *polling* del cliente | SSE / WebSocket | Cero infraestructura adicional, funciona tras el proxy nginx sin tocar nada, y con la concurrencia de un MVP es indistinguible del tiempo real. SSE exigiría convertir a asíncrono todo el acceso a datos, que hoy es síncrono y bloqueante |
| D6 | Las fuentes de leads llevan un **mapeo de campos configurable** | Contrato canónico fijo, o un adaptador por proveedor | Un único adaptador genérico sirve para cualquier plataforma sin desplegar código nuevo. Además es el mismo mecanismo que necesita el mapeo de columnas del CSV, así que se amortiza desde el día uno |
| D7 | La carga de trabajo de un asesor se **deriva por consulta**, no se mantiene denormalizada | Conservar `active_leads_count` como columna | Elimina de un golpe el *lost update* por concurrencia y el contador que nunca decrece. Con un índice, el coste es despreciable en un MVP |
| D8 | Se conserva raw SQL; migraciones con un runner propio | Introducir un ORM, o Alembic | La prohibición de ORM es una restricción autoimpuesta del proyecto y didácticamente valiosa: obliga a que el puerto oculte de verdad el detalle de persistencia. Alembic arrastra SQLAlchemy |
| D9 | Estrategia de testing: unitarios amplios + integración por repositorio + un *smoke* e2e | Eliminar todo lo que toque base de datos | Sin ORM no hay compilador que valide el SQL escrito a mano. Como el esquema se va a reescribir por completo, los tests de integración son la única red de seguridad |

---

## 5. Arquitectura del backend

### 5.1 Estructura de capas

```
backend/src/
├── domain/                     Núcleo puro. Cero dependencias externas
│   ├── entities/               Agregados con comportamiento
│   ├── value_objects/          Invariantes en el constructor
│   ├── services/               ScoringEngine, AssignmentEngine
│   ├── policies/               QualificationPolicy, AuthorizationPolicy
│   ├── events/                 Eventos emitidos por las entidades
│   └── exceptions.py           Sin códigos HTTP
│
├── application/                Orquestación. Depende sólo de domain
│   ├── ports/input/            Contratos de casos de uso (ABC)
│   ├── ports/output/           Contratos de infraestructura (ABC)
│   ├── dtos/                   dataclasses frozen. Cero Pydantic
│   ├── use_cases/              Implementaciones de los puertos de entrada
│   └── handlers/               Reaccionan a eventos de dominio
│
└── infrastructure/             Adaptadores. Depende de todo lo anterior
    ├── adapters/input/api/     Routers finos, schemas Pydantic, mappers
    ├── adapters/output/        persistence · security · parsers · events
    ├── config/                 Settings centralizado
    └── di/                     Composition root
```

### 5.2 Cambios estructurales

**C1 — Puertos de seguridad.** Se crean `PasswordHasherPort` y `TokenServicePort` en `application/ports/output/`. Las implementaciones bcrypt y PyJWT pasan a ser adaptadores en `infrastructure/adapters/output/security/`. Cierra las tres violaciones duras de la sección 2.2.

**C2 — DTOs sin framework.** Todos los comandos y consultas de `application/dtos/` pasan a `@dataclass(frozen=True)`. Pydantic queda confinado a `infrastructure/adapters/input/api/schemas.py`, con mappers explícitos en ambos sentidos.

**C3 — Autorización como política de dominio.** Se crea `AuthorizationPolicy` en `domain/policies/`. Los routers dejan de decidir quién puede hacer qué; se limitan a invocar la política. Las reglas pasan a ser testeables sin FastAPI y reutilizables desde un worker o una CLI.

**C4 — Excepciones sin transporte.** Se elimina `status_code` de las excepciones de dominio. El mapeo excepción → código HTTP vive en una tabla dentro de `exception_handlers.py`.

**C5 — Composition root explícito.** Se crea `infrastructure/di/container.py`, que construye el grafo de objetos y fija el ciclo de vida de cada uno. FastAPI se limita a consultarlo vía `Depends`. Aquí se resuelve el bug del round-robin: los componentes con estado dejan de recrearse por petición.

**C6 — Contexto de petición.** Una única dependencia construye un `RequestContext` (actor autenticado + organización) a partir del token. Los casos de uso reciben ese contexto dentro del comando. Desaparece `{tenant_id}` de todas las URLs.

**C7 — Puertos de entorno.** `ClockPort` e `IdGeneratorPort`. Hoy las entidades llaman a `datetime.now()` y `uuid4()` internamente, lo que es un efecto de lado no controlable y hace los tests no deterministas.

**C8 — Guardián automático.** Un test de arquitectura que recorre los imports de `domain/` y `application/` y falla si aparece `infrastructure`. Sin él, la regla de dependencias se erosiona en cuanto haya prisa.

### 5.3 Patrones de diseño aplicados

| Patrón | Dónde | Para qué |
|---|---|---|
| Ports & Adapters | Toda la arquitectura | Aislar el núcleo de negocio de frameworks y drivers |
| Strategy | `AssignmentStrategy` en el motor de asignación | Intercambiar el algoritmo de reparto sin tocar el motor |
| Repository | Puertos de persistencia | Ocultar el SQL tras un contrato de colección |
| Unit of Work | `UnitOfWorkPort` | Garantizar atomicidad transaccional entre repositorios |
| Observer / Pub-Sub | Bus de eventos de dominio | Desacoplar los efectos secundarios (notificar, avisar) del caso de uso |
| Specification (ligera) | `ScoringRule.matches()` | Expresar el criterio de una regla como objeto evaluable |
| Factory Method | `Lead.create()`, `Agent.create()` | Concentrar la construcción válida de un agregado |
| Policy | `QualificationPolicy`, `AuthorizationPolicy` | Sacar decisiones de negocio del código de orquestación |
| Dependency Injection | Composition root | Invertir dependencias sin acoplar a un contenedor mágico |
| Data Mapper | Mappers DTO ↔ Pydantic ↔ entidad | Impedir que un modelo de una capa se filtre a otra |

---

## 6. Modelo de dominio

Detalle campo a campo de cada agregado. La columna **Obl.** indica si el campo es obligatorio en la construcción.

### 6.1 `Tenant` — organización cliente

Representa a la empresa que usa la plataforma. Hoy el tenant es un UUID que circula libremente sin respaldo en base de datos: cualquiera puede inventarse uno. Al existir el rol `ADMIN` como administrador de plataforma, la organización necesita ser una entidad real que él pueda dar de alta.

| Campo | Tipo | Obl. | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | `TenantId` | sí | generado | Identidad de la organización |
| `name` | `str` | sí | — | Nombre comercial. Es lo que ve el administrador de plataforma en su listado |
| `is_active` | `bool` | no | `True` | Una organización inactiva no permite autenticación ni ingesta, pero conserva todos sus datos. Permite suspender sin destruir |
| `created_at` | `datetime` | sí | ahora | Auditoría |

**Invariantes:** `name` no puede estar vacío.

---

### 6.2 `SalesGroup` — grupo de asesores

Agrupación de asesores que comparten política de asignación. Es el concepto central que hoy falta: sustituye al campo `team: String` suelto por un agregado con identidad, políticas propias y clave foránea real.

| Campo | Tipo | Obl. | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | `GroupId` | sí | generado | Identidad del grupo |
| `tenant_id` | `TenantId` | sí | — | Organización propietaria. Un grupo nunca cruza organizaciones |
| `name` | `str` | sí | — | Nombre visible: "Ventas Norte", "Equipo Enterprise". Único dentro de la organización |
| `description` | `str \| None` | no | `None` | Texto libre para que el gestor documente el propósito del grupo |
| `default_strategy` | `AssignmentStrategy` | no | `LOWEST_LOAD` | Estrategia de reparto que se aplica cuando la regla de asignación no especifica una propia. Evita repetir la misma decisión en cada regla que apunte a este grupo |
| `capacity_per_agent` | `int \| None` | no | `None` | Máximo de leads activos que puede tener a la vez cada asesor del grupo. `None` significa sin límite. Un asesor que llegue al tope queda excluido de los candidatos hasta que se libere |
| `is_active` | `bool` | no | `True` | Un grupo inactivo deja de recibir asignaciones automáticas pero conserva su histórico y sus asesores |
| `created_at` | `datetime` | sí | ahora | Auditoría |

**Invariantes:** `name` no vacío y único por organización; `capacity_per_agent`, si se indica, debe ser mayor que cero.

---

### 6.3 `Agent` — usuario del sistema

Es a la vez credencial de acceso y receptor de leads.

| Campo | Tipo | Obl. | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | `AgentId` | sí | generado | Identidad del usuario |
| `tenant_id` | `TenantId \| None` | condicional | — | Organización a la que pertenece. Es `None` **únicamente** para el rol `ADMIN`, que opera por encima de las organizaciones |
| `name` | `str` | sí | — | Nombre visible en la interfaz |
| `email` | `EmailAddress` | sí | — | Identificador de acceso. Único por organización |
| `role` | `AgentRole` | no | `AGENT` | Determina qué puede hacer. Ver 6.12 |
| `group_id` | `GroupId \| None` | no | `None` | Grupo al que pertenece. Sin grupo, el asesor no recibe asignaciones por reglas de grupo, pero sí puede ser destinatario de una regla que lo nombre explícitamente |
| `is_active` | `bool` | no | `True` | Un asesor inactivo no puede autenticarse y queda fuera de la asignación automática. Su token vigente deja de funcionar en la siguiente petición, porque la identidad se revalida contra base de datos |
| `created_at` | `datetime` | sí | ahora | Auditoría |

**Comportamiento:** `activate()`, `deactivate()`, `assign_to_group(group_id)`, `belongs_to(tenant_id)`, `can_manage_organization()`.

**Cambios respecto al modelo actual:**

- **Sale `hashed_password`** a un agregado separado (6.4). Hoy el hash forma parte de la entidad y, como los puertos de entrada devuelven la entidad directamente, acaba viajando hasta el adaptador HTTP. Separarlo hace esa fuga imposible por construcción.
- **Sale `active_leads_count`.** Pasa a derivarse por consulta (decisión D7).
- **Entra `group_id`.** Sustituye a `team: str`.

**Invariantes:** `tenant_id` es obligatorio salvo para `ADMIN`; un `AGENT` o `MANAGER` sin organización sería un usuario huérfano incapaz de operar.

---

### 6.4 `AgentCredentials` — secreto de acceso

Agregado separado, relación uno a uno con `Agent`. Existe para que el secreto no forme parte del modelo comercial.

| Campo | Tipo | Obl. | Por defecto | Descripción |
|---|---|---|---|---|
| `agent_id` | `AgentId` | sí | — | Usuario al que pertenecen |
| `password_hash` | `str` | sí | — | Hash bcrypt. Nunca abandona el backend |
| `updated_at` | `datetime` | sí | ahora | Fecha del último cambio. Habilita políticas de caducidad más adelante |

---

### 6.5 `Lead` — prospecto comercial validado

Un `Lead` sólo existe si todos sus datos son válidos. Lo que no valida se queda en `IntakeRecord` (6.6).

| Campo | Tipo | Obl. | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | `LeadId` | sí | generado | Identidad del lead |
| `tenant_id` | `TenantId` | sí | — | Organización propietaria |
| `source_id` | `SourceId` | sí | — | Fuente por la que entró. Permite responder "¿de dónde vienen mis leads?" y segmentar métricas por canal |
| `first_name` | `str` | sí | — | Nombre |
| `last_name` | `str` | sí | — | Apellidos |
| `email` | `EmailAddress` | sí | — | Correo. El value object garantiza el formato |
| `phone` | `str \| None` | no | `None` | Teléfono de contacto |
| `company` | `str` | sí | — | Empresa del prospecto |
| `industry` | `str` | sí | — | Sector. Es uno de los campos típicos sobre los que se definen reglas de puntuación |
| `budget` | `Money` | sí | — | Presupuesto estimado. `Decimal` no negativo |
| `custom_attributes` | `dict[str, Any]` | no | `{}` | Atributos libres que aporta la fuente (número de empleados, urgencia, campaña…). Accesibles desde las reglas con notación de punto: `custom_attributes.employee_count` |
| `score` | `Score` | no | `0` | Puntuación resultante del motor de scoring |
| `status` | `LeadStatus` | no | `NEW` | Estado del ciclo de vida. Ver 6.12 |
| `assigned_agent_id` | `AgentId \| None` | no | `None` | Asesor responsable |
| `assigned_at` | `datetime \| None` | no | `None` | Momento de la asignación. Necesario para ordenar el panel del asesor y para métricas de tiempo de respuesta |
| `discard_reason` | `str \| None` | no | `None` | Motivo del descarte. Sólo presente si `status` es `DISCARDED` |
| `created_at` | `datetime` | sí | ahora | Momento de entrada al sistema |
| `updated_at` | `datetime` | sí | ahora | Última modificación. Hoy no existe, así que no hay traza de reasignaciones |

**Máquina de estados:**

```
                    ┌── score < umbral inferior ──→ DISQUALIFIED
                    │
   NEW ── scoring ──┤
                    │                        ┌── hay asesor ──→ ASSIGNED
                    └── score ≥ umbral ──→ QUALIFIED
                                             └── sin asesor ──→ UNASSIGNED

   UNASSIGNED ── asignación manual ──→ ASSIGNED
   ASSIGNED   ── reasignación       ──→ ASSIGNED (otro asesor)
   ASSIGNED   ── liberación         ──→ UNASSIGNED
   cualquiera ── descarte           ──→ DISCARDED
```

**Comportamiento:** `apply_score(delta)`, `qualify(policy)`, `assign_to(agent, at)`, `reassign_to(agent, at)`, `unassign()`, `discard(reason)`.

**Invariantes de transición** (hoy inexistentes: `assign_to_agent` acepta cualquier estado y sobrescribe en silencio una asignación previa):

- `assign_to` sólo desde `QUALIFIED` o `UNASSIGNED`.
- `reassign_to` sólo desde `ASSIGNED`.
- `discard` desde cualquier estado salvo `DISCARDED`.
- El asesor destino debe pertenecer a la misma organización que el lead.
- Un lead `DISQUALIFIED` no entra al motor de asignación.

---

### 6.6 `IntakeRecord` — bandeja de entrada

Captura **todo** lo que llega al sistema antes de validarlo. Es la pieza que garantiza que ningún lead se pierda.

Hoy, un lead con el correo mal formado devuelve `FAILED` y no se persiste en ninguna parte: desaparece. Con este agregado, el payload original queda guardado y el gestor puede corregirlo y reintentarlo.

| Campo | Tipo | Obl. | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | `IntakeId` | sí | generado | Identidad del registro de ingesta |
| `tenant_id` | `TenantId` | sí | — | Organización destinataria |
| `source_id` | `SourceId` | sí | — | Fuente por la que llegó |
| `raw_payload` | `dict[str, Any]` | sí | — | El dato **tal cual llegó**, sin transformar. Es lo que permite corregir y reintentar sin pedir el reenvío al origen |
| `status` | `IntakeStatus` | no | `PENDING` | Estado del procesamiento. Ver 6.12 |
| `errors` | `list[IntakeError]` | no | `[]` | Errores de validación encontrados. Vacío si validó |
| `lead_id` | `LeadId \| None` | no | `None` | Lead resultante, si se promovió correctamente |
| `batch_id` | `BatchId \| None` | no | `None` | Agrupa todos los registros de una misma carga de fichero. Permite mostrar el resultado consolidado de una subida |
| `row_number` | `int \| None` | no | `None` | Número de fila dentro del fichero, para que el gestor localice exactamente qué línea falló |
| `created_at` | `datetime` | sí | ahora | Momento de recepción |
| `processed_at` | `datetime \| None` | no | `None` | Momento en que se resolvió (promoción o rechazo) |

**Comportamiento:** `promote(lead_id, at)`, `reject(errors, at)`, `correct(payload)`, `discard()`.

**Invariantes:** `lead_id` sólo puede estar presente si `status` es `PROMOTED`; `errors` no puede estar vacío si `status` es `REJECTED`.

---

### 6.7 `IntakeError` — detalle de un fallo de validación

Value object inmutable.

| Campo | Tipo | Descripción |
|---|---|---|
| `field` | `str` | Campo que falló: `"email"`, `"budget"` |
| `code` | `str` | Código estable: `"INVALID_EMAIL"`, `"NEGATIVE_BUDGET"`, `"MISSING_FIELD"`. La interfaz decide el mensaje a partir de él, sin depender del texto |
| `message` | `str` | Descripción legible para el gestor |

---

### 6.8 `LeadSource` — origen de los leads

Define por qué canal entran los leads y cómo se traduce su formato. Es una entidad que el gestor da de alta desde la interfaz, no un enumerado cerrado en el código: por eso el sistema es extensible a nuevas plataformas sin desplegar código nuevo.

| Campo | Tipo | Obl. | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | `SourceId` | sí | generado | Identidad de la fuente |
| `tenant_id` | `TenantId` | sí | — | Organización propietaria |
| `name` | `str` | sí | — | Nombre que escribe el gestor: "Facebook Lead Ads — Campaña Verano", "Formulario web" |
| `kind` | `SourceKind` | sí | — | Mecanismo de entrada. Ver 6.12 |
| `field_mapping` | `dict[str, str]` | no | `{}` | Traducción `campo de origen → campo del lead`. Vacío significa que el payload ya llega en formato canónico. Ejemplo: `{"full_name": "first_name", "presupuesto": "budget"}` |
| `secret` | `str \| None` | no | `None` | Secreto compartido para verificar la firma HMAC de las peticiones entrantes. Sólo aplica a `kind = WEBHOOK` |
| `is_active` | `bool` | no | `True` | Una fuente inactiva rechaza las entradas nuevas sin perder su histórico |
| `created_at` | `datetime` | sí | ahora | Auditoría |

**Comportamiento previsto en el MVP:** al crear una organización se generan automáticamente dos fuentes, `MANUAL_FORM` y `FILE_UPLOAD`, que son las que usan el formulario individual y la carga de ficheros. El `field_mapping` de `FILE_UPLOAD` es exactamente el mapeo de columnas del CSV, así que la maquinaria se amortiza desde el primer día.

**Extensión posterior (F3b):** el gestor registra una fuente de tipo `WEBHOOK`; el sistema genera un `secret` y expone `POST /api/v1/intake/{source_id}`; el gestor configura el `field_mapping` para traducir el JSON de esa plataforma. Sólo haría falta escribir código nuevo si un proveedor exige un protocolo de verificación particular (Facebook, por ejemplo, requiere responder a una petición GET de comprobación del hook).

**Invariantes:** `secret` es obligatorio si `kind` es `WEBHOOK`, y debe ser nulo en el resto de casos.

---

### 6.9 `ScoringRule` — regla de puntuación

Criterio que suma o resta puntos a un lead según sus atributos.

| Campo | Tipo | Obl. | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | `RuleId` | sí | generado | Identidad de la regla |
| `tenant_id` | `TenantId` | sí | — | Organización propietaria. Hoy la regla no sabe a qué organización pertenece: el tenant viaja como parámetro suelto del repositorio |
| `name` | `str` | sí | — | Nombre descriptivo: "Presupuesto alto", "Sector tecnológico" |
| `field` | `str` | sí | — | Campo del lead a evaluar. Admite notación de punto para atributos personalizados: `custom_attributes.employee_count` |
| `operator` | `Operator` | sí | — | Comparador a aplicar. Ver 6.12 |
| `value` | `RuleValue` | sí | — | Valor de referencia, **conservando su tipo**. Hoy se fuerza a cadena en el router, lo que rompe el operador `IN` y hace que las comparaciones numéricas funcionen por casualidad |
| `score_delta` | `int` | sí | — | Puntos a sumar si la regla se cumple. Negativo para penalizar |
| `priority` | `int` | no | `0` | Orden de evaluación. La suma es conmutativa, así que sólo afecta a la trazabilidad del desglose |
| `is_active` | `bool` | no | `True` | Permite desactivar una regla sin borrarla ni perder su histórico |

**Comportamiento:** `matches(lead) -> bool`. Hoy esta lógica vive fuera, en el motor; llevarla a la regla la convierte en una especificación evaluable y elimina la anemia del modelo.

**Invariantes:** `field` no vacío; `value` compatible con el operador (`IN` exige una lista, `GREATER_THAN` un número).

---

### 6.10 `AssignmentRule` — regla de asignación

Renombra a la actual `RoutingRule`. Decide a quién se asigna un lead en función de su puntuación.

| Campo | Tipo | Obl. | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | `RuleId` | sí | generado | Identidad de la regla |
| `tenant_id` | `TenantId` | sí | — | Organización propietaria |
| `name` | `str` | sí | — | Nombre descriptivo. Hoy la regla no tiene nombre, lo que la hace imposible de identificar en una interfaz |
| `min_score` | `int` | no | `0` | Puntuación mínima (inclusive) para que la regla aplique |
| `max_score` | `int \| None` | no | `None` | Puntuación máxima (inclusive). Permite definir bandas: "de 30 a 60 puntos, al equipo junior". `None` significa sin límite superior |
| `target_group_id` | `GroupId \| None` | no | `None` | Grupo destinatario. Clave foránea real, no una cadena |
| `target_agent_ids` | `list[AgentId]` | no | `[]` | Asesores nombrados explícitamente |
| `agent_match_mode` | `AgentMatchMode` | no | `ANY` | Cómo se combinan grupo y asesores nombrados. Ver 6.12. Resuelve el defecto actual, que los intersecta siempre y deja fuera a un asesor nombrado que esté en otro grupo |
| `strategy` | `AssignmentStrategy \| None` | no | `None` | Estrategia de reparto. `None` significa heredar la del grupo destino |
| `priority` | `int` | no | `0` | Orden de evaluación: mayor primero. Resuelve el desempate no determinista actual, que depende del orden en que la base de datos devuelva las filas |
| `is_active` | `bool` | no | `True` | Permite desactivar sin borrar |
| `rr_cursor` | `int` | no | `0` | Cursor del reparto rotatorio, **persistido**. Hoy vive en memoria de una instancia que se recrea en cada petición, y por eso el round-robin siempre elige al mismo asesor |

**Comportamiento:** `matches_score(score) -> bool`, `resolve_strategy(group) -> AssignmentStrategy`, `advance_cursor(size) -> int`.

**Invariantes:** debe indicarse al menos uno de `target_group_id` o `target_agent_ids`, o la regla no puede producir ningún candidato; `max_score`, si se indica, debe ser mayor o igual que `min_score`.

---

### 6.11 `Notification` — aviso interno

| Campo | Tipo | Obl. | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | `NotificationId` | sí | generado | Identidad del aviso |
| `tenant_id` | `TenantId` | sí | — | Organización |
| `recipient_id` | `AgentId` | sí | — | Destinatario del aviso |
| `kind` | `NotificationKind` | sí | — | Tipo de suceso. Determina el icono y el texto en la interfaz |
| `lead_id` | `LeadId \| None` | no | `None` | Lead relacionado. Permite que al pulsar la notificación se navegue directamente a su detalle |
| `intake_id` | `IntakeId \| None` | no | `None` | Registro de ingesta relacionado, para los avisos de validación fallida |
| `message` | `str` | sí | — | Texto ya compuesto y listo para mostrar |
| `is_read` | `bool` | no | `False` | Marca de lectura. Alimenta el contador de la campana |
| `created_at` | `datetime` | sí | ahora | Momento del aviso |

**Comportamiento:** `mark_as_read()`.

---

### 6.12 Enumerados

**`AgentRole`** — qué puede hacer un usuario.

| Valor | Ámbito | Permisos |
|---|---|---|
| `ADMIN` | Plataforma | Crea organizaciones y su primer gestor. No pertenece a ninguna organización (`tenant_id` nulo) |
| `MANAGER` | Su organización | Administra asesores, grupos, reglas y fuentes. Ve todos los leads de su organización, asigna manualmente, descarta y resuelve la bandeja de entrada |
| `AGENT` | Sus propios leads | Consulta únicamente los leads asignados a él y su detalle. Recibe notificaciones |

**`LeadStatus`** — ciclo de vida del lead.

| Valor | Significado |
|---|---|
| `NEW` | Creado, aún sin evaluar |
| `QUALIFIED` | Superó el umbral de calificación; pendiente de asignar |
| `DISQUALIFIED` | Por debajo del umbral inferior. No entra al motor de asignación |
| `UNASSIGNED` | **Nuevo.** Calificado, pero ninguna regla produjo un asesor. Requiere intervención del gestor |
| `ASSIGNED` | Asignado a un asesor |
| `DISCARDED` | **Nuevo.** Descartado manualmente por el gestor, con motivo |

Se elimina `FAILED`: un lead que no valida ya no llega a ser `Lead`; se queda en `IntakeRecord` con estado `REJECTED`.

**`IntakeStatus`** — procesamiento de un registro de ingesta.

| Valor | Significado |
|---|---|
| `PENDING` | Recibido, pendiente de procesar |
| `PROMOTED` | Validó correctamente y generó un lead |
| `REJECTED` | Falló la validación. Visible para el gestor, que puede corregirlo o descartarlo |
| `DISCARDED` | El gestor decidió no recuperarlo |

**`SourceKind`** — mecanismo de entrada.

| Valor | Significado | Disponible |
|---|---|---|
| `MANUAL_FORM` | Alta individual desde la interfaz del gestor | MVP |
| `FILE_UPLOAD` | Carga masiva de fichero CSV o XLSX | MVP |
| `WEBHOOK` | Empuje desde una plataforma externa, con firma HMAC | F3b |

**`Operator`** — comparadores de las reglas de puntuación. Sin cambios respecto al modelo actual: `EQUALS`, `NOT_EQUALS`, `GREATER_THAN`, `LESS_THAN`, `CONTAINS`, `IN`.

**`AssignmentStrategy`** — algoritmo de reparto.

| Valor | Comportamiento |
|---|---|
| `LOWEST_LOAD` | Elige al candidato con menos leads activos. Reparte equilibrando carga |
| `ROUND_ROBIN` | Rota entre los candidatos en orden estable, usando el cursor persistido de la regla |
| `DIRECT_AGENT` | Recorre `target_agent_ids` **en el orden definido** y toma el primero disponible. Permite prioridad explícita entre asesores concretos |

**`AgentMatchMode`** — cómo combinar grupo y asesores nombrados.

| Valor | Comportamiento |
|---|---|
| `ANY` | Candidatos = miembros del grupo **unidos** a los asesores nombrados. Es lo que se espera intuitivamente: "el equipo Norte, y además María aunque sea de otro equipo" |
| `ONLY` | Candidatos = intersección de ambos conjuntos. Restringe dentro del grupo: "sólo Juan y Pedro, del equipo Norte" |

**`NotificationKind`** — tipos de aviso.

| Valor | Destinatario | Cuándo |
|---|---|---|
| `LEAD_ASSIGNED` | Asesor | Se le ha asignado un lead nuevo |
| `LEAD_UNASSIGNED` | Gestor | Un lead calificado no encontró asesor |
| `INTAKE_REJECTED` | Gestor | Un registro de ingesta falló la validación |

---

### 6.13 Value objects

| Value object | Invariante que garantiza |
|---|---|
| `EntityId` (base genérica) | UUID válido. Se especializa en `TenantId`, `AgentId`, `LeadId`, `GroupId`, `SourceId`, `IntakeId`, `RuleId`, `NotificationId`, `BatchId`. Elimina la triplicación byte a byte actual de `LeadId`/`AgentId`/`TenantId` |
| `EmailAddress` | Formato de correo válido |
| `Money` | `Decimal` no negativo, con precisión monetaria preservada |
| `Score` | Entero dentro de un rango razonable. Hoy no valida nada: `Score(-999999)` es aceptado |
| `RuleValue` | **Nuevo.** Preserva el tipo del valor de una regla (número, texto, booleano o lista) a través de la serialización. Es lo que hace que el operador `IN` funcione |

### 6.14 Políticas de dominio

**`QualificationPolicy(threshold_qualified, threshold_disqualified)`** — decide si un lead queda calificado o descalificado según su puntuación. Hoy los umbrales `30` y `0` están escritos como valores por defecto del constructor de un caso de uso, que nadie sobrescribe: la política de negocio ni existe como concepto ni es configurable. Pasa a ser un objeto de dominio, configurable por organización.

**`AuthorizationPolicy`** — concentra las decisiones de quién puede hacer qué: `can_manage_agents(actor)`, `can_manage_groups(actor)`, `can_manage_rules(actor)`, `can_view_lead(actor, lead)`, `can_create_agent_with_role(actor, role)`, `can_access_tenant(actor, tenant_id)`. Hoy estas reglas están repartidas entre `dependencies.py` y `agent_router.py`, acopladas a FastAPI y no reutilizables.

### 6.15 Eventos de dominio

Los emiten **las entidades**, no los casos de uso. Hoy existe un único evento (`LeadProcessedEvent`) que se fabrica a mano en el caso de uso, lo que lo convierte en una notificación de aplicación y no en un evento de dominio.

| Evento | Se emite cuando | Consumidor en el MVP |
|---|---|---|
| `LeadQualified` | Un lead supera el umbral | — (reservado para métricas) |
| `LeadDisqualified` | Un lead queda por debajo del umbral | — |
| `LeadAssigned` | Un lead se asigna a un asesor | `NotificationHandler` → avisa al asesor |
| `LeadLeftUnassigned` | Un lead calificado no encuentra asesor | `NotificationHandler` → avisa al gestor |
| `LeadReassigned` | Un lead cambia de asesor | `NotificationHandler` → avisa al nuevo asesor |
| `LeadDiscarded` | El gestor descarta un lead | — |
| `IntakeRejected` | Un registro de ingesta falla la validación | `NotificationHandler` → avisa al gestor |
| `IntakePromoted` | Un registro de ingesta genera un lead | — |

En F3b se añade un segundo consumidor, `OutboundWebhookHandler`, sin tocar ni las entidades ni los casos de uso. Ése es precisamente el valor del patrón.

---

## 7. Motor de puntuación y asignación

### 7.1 Motor de puntuación

```
score = 0
para cada ScoringRule activa de la organización, ordenada por priority:
    si regla.matches(lead):
        score += regla.score_delta
        registrar (regla.id, regla.name, regla.score_delta) en el desglose
```

Devuelve la puntuación **y el desglose de reglas aplicadas**. Hoy sólo se devuelve `applied_rules_count`, que además cuenta las reglas consultadas y no las que efectivamente aplicaron; el desglose es lo que permite que la interfaz explique al gestor por qué un lead puntuó lo que puntuó.

Correcciones respecto al motor actual:

- `NOT_EQUALS` aplica la misma coerción de tipos que `EQUALS`. Hoy no la hace, así que para el mismo par campo/valor ambos operadores pueden devolver verdadero a la vez.
- Un campo ausente devuelve falso para los operadores positivos, pero **verdadero** para `NOT_EQUALS`. Hoy devuelve falso siempre, lo que es semánticamente incorrecto.
- Las comparaciones numéricas conservan `Decimal` en lugar de convertir a `float`.
- El campo a evaluar se valida contra una lista de campos permitidos. Hoy es reflexión libre sobre el nombre: una regla con `field = "tenant_id"` funciona.

### 7.2 Motor de asignación

```
1. Filtrar las AssignmentRule activas de la organización cuyo rango
   [min_score, max_score] contenga la puntuación del lead.
   Ordenar por priority descendente, y por id como desempate estable.

2. Para cada regla candidata, en ese orden:

   a. Construir el conjunto de candidatos según agent_match_mode:
        ANY  → miembros del grupo  ∪  asesores nombrados
        ONLY → miembros del grupo  ∩  asesores nombrados

   b. Filtrar candidatos:
        - de la misma organización que el lead    ← cierra la fuga cross-tenant
        - activos
        - de un grupo activo
        - por debajo de capacity_per_agent, si el grupo lo define

   c. Si no queda ningún candidato → probar la siguiente regla (cascada)

   d. Aplicar la estrategia (la de la regla, o la del grupo si no la define):
        LOWEST_LOAD  → menor carga derivada; desempate por id
        ROUND_ROBIN  → candidatos[rr_cursor % n], y avanzar el cursor
                       en la misma transacción
        DIRECT_AGENT → primer disponible en el orden de target_agent_ids

   e. Devolver el asesor seleccionado

3. Si ninguna regla produce asesor:
   → el lead queda UNASSIGNED
   → se emite LeadLeftUnassigned
   → se notifica al gestor
```

Diferencias clave con el motor actual:

| Aspecto | Hoy | Objetivo |
|---|---|---|
| Selección de regla | Primera que supera el umbral tras ordenar por `min_score`; si no da asesor, se rinde | Cascada por `priority` explícita, probando reglas sucesivas |
| Filtro de organización | No existe | Obligatorio |
| Grupo y asesores nombrados | Siempre se intersectan | Configurable con `agent_match_mode` |
| Capacidad | No se contempla | `capacity_per_agent` del grupo |
| Round-robin | Cursor en memoria por petición → siempre el mismo | Cursor persistido en la regla |
| `DIRECT_AGENT` | `candidatos[0]`, idéntico al caso por defecto | Recorre `target_agent_ids` en orden |
| Sin asesor | `None` silencioso | Estado `UNASSIGNED`, evento y notificación |
| Efecto de lado | `select_agent()` muta el lead | El motor sólo selecciona; el caso de uso decide |

### 7.3 Carga de trabajo derivada

`active_leads_count` desaparece como columna. La carga de un asesor se calcula con:

```sql
SELECT assigned_agent_id, COUNT(*) AS load
FROM leads
WHERE tenant_id = %s AND status = 'ASSIGNED' AND assigned_agent_id = ANY(%s)
GROUP BY assigned_agent_id
```

Una sola consulta para todos los candidatos de una asignación, con índice sobre `(tenant_id, assigned_agent_id, status)`. Esto elimina simultáneamente el *lost update* por concurrencia y el problema de que el contador nunca decrezca.

---

## 8. Flujo de ingesta unificado

Los tres canales de entrada convergen en el mismo recorrido:

```
payload crudo (formulario · fichero · webhook)
   │
   ├─ crear IntakeRecord(PENDING) con el payload sin tocar
   │
   ├─ aplicar field_mapping de la fuente
   │
   ├─ intentar construir Lead (value objects validan)
   │
   ├── VÁLIDO ──→ ScoringEngine
   │               └→ QualificationPolicy
   │                   ├─ DISQUALIFIED → fin
   │                   └─ QUALIFIED → AssignmentEngine
   │                       ├─ asesor encontrado
   │                       │   → Lead(ASSIGNED), evento LeadAssigned
   │                       │   → notificación al ASESOR
   │                       └─ sin asesor
   │                           → Lead(UNASSIGNED), evento LeadLeftUnassigned
   │                           → notificación al GESTOR
   │               IntakeRecord(PROMOTED, lead_id)
   │
   └── INVÁLIDO ─→ IntakeRecord(REJECTED, errors[])
                    → evento IntakeRejected
                    → notificación al GESTOR
                    ├─ el gestor corrige el payload → reintenta la promoción
                    └─ el gestor descarta → DISCARDED
```

**Transaccionalidad.** El `IntakeRecord` y el `Lead` se persisten en la misma transacción. Los eventos se publican **después** del commit, de modo que un fallo al notificar no deshaga un lead ya guardado — el problema inverso al actual, donde el publicador se invoca dentro del flujo y una excepción en un manejador hace fallar una ingesta ya confirmada.

**Carga masiva.** Cada fila genera su propio `IntakeRecord`, todos compartiendo `batch_id`. La respuesta resume el lote y la bandeja de entrada permite revisar fila a fila lo que falló. Hoy el `job_id` que devuelve el endpoint no se persiste en ninguna parte, así que el resultado de una carga es irrecuperable en cuanto se cierra la pantalla.

---

## 9. Autorización y multi-tenancy

### 9.1 Contexto de petición

```
Authorization: Bearer <jwt>
   │
   └─→ decodificar → validar → cargar Agent → construir RequestContext
                                                 ├─ actor: Agent
                                                 └─ tenant_id: TenantId | None
```

El `RequestContext` se construye **una vez** por petición y se pasa a los casos de uso dentro del comando. Ningún caso de uso recibe un `tenant_id` que venga del cliente.

**Consecuencia directa:** desaparecen los segmentos `/tenants/{tenant_id}/` de todas las URLs. Un cliente ya no puede elegir a qué organización accede, y las tres fugas cross-tenant detectadas dejan de ser posibles por construcción, no por comprobación.

### 9.2 Matriz de permisos

| Operación | `ADMIN` | `MANAGER` | `AGENT` |
|---|---|---|---|
| Crear organización | ✅ | ❌ | ❌ |
| Crear gestor de una organización | ✅ | ❌ | ❌ |
| Crear / editar / desactivar asesores | ✅ | ✅ su organización | ❌ |
| Gestionar grupos | ✅ | ✅ su organización | ❌ |
| Gestionar reglas | ✅ | ✅ su organización | ❌ |
| Gestionar fuentes | ✅ | ✅ su organización | ❌ |
| Ver todos los leads | ✅ | ✅ su organización | ❌ |
| Ver sus leads asignados | — | ✅ | ✅ |
| Asignar manualmente / descartar | ✅ | ✅ su organización | ❌ |
| Resolver la bandeja de entrada | ✅ | ✅ su organización | ❌ |

Estas reglas viven en `AuthorizationPolicy`, en el dominio. Las dependencias de FastAPI se limitan a construir el contexto e invocar la política.

> **Hueco de diseño detectado al implementar F0 — pendiente de resolver en F1.**
>
> Un `ADMIN` de plataforma tiene `tenant_id = None`. Al derivar la organización del token (decisión D2), ese administrador **no tiene forma de expresar sobre qué organización quiere operar**, así que las filas de la matriz que le conceden ver leads o gestionar reglas no son alcanzables.
>
> Las dos salidas posibles:
>
> 1. **Impersonación explícita:** los endpoints de gestión aceptan un `?tenant_id=` que **sólo** el `ADMIN` puede usar. Conserva la matriz tal cual, a cambio de reintroducir un identificador de organización controlado por el cliente —justo lo que D2 eliminó—, aunque ahora restringido a un único rol.
> 2. **Separación de planos:** el `ADMIN` gestiona organizaciones y sus gestores, pero no accede a datos operativos. Más seguro y más simple, y obliga a corregir la matriz de permisos.
>
> La segunda es la recomendada: un superadministrador que no puede leer los leads de sus clientes es una propiedad deseable, no una carencia.

### 9.3 Arranque del sistema

Se conserva la regla de bootstrap, corregida: si no existe ningún usuario, la primera llamada a `POST /api/v1/agents` crea un `ADMIN` sin exigir autenticación. Se corrige la condición de carrera actual, en la que la comprobación y la creación ocurren en transacciones distintas y varias peticiones simultáneas producirían varios administradores. Se resuelve con un índice único parcial sobre el rol `ADMIN`.

---

## 10. Contrato de API

Sin `tenant_id` en las rutas: se deriva del token.

### Autenticación
```
POST   /api/v1/auth/login          form-urlencoded (username, password) → token
GET    /api/v1/auth/me             🆕 identidad, rol, organización y grupo del usuario actual
```
`/auth/me` es imprescindible para el frontend: el token lleva el rol como claim, pero hoy `get_current_agent` lo ignora y siempre relee de base de datos, así que el cliente no tiene forma de conocer su propio rol.

### Plataforma — sólo `ADMIN`
```
POST   /api/v1/tenants             🆕 crear organización
GET    /api/v1/tenants             🆕 listar organizaciones
PATCH  /api/v1/tenants/{id}        🆕 activar / desactivar
```

### Asesores
```
GET    /api/v1/agents              listar (filtros: group_id, role, is_active, q)
POST   /api/v1/agents              crear
GET    /api/v1/agents/{id}         detalle
PATCH  /api/v1/agents/{id}         🆕 editar (nombre, grupo, rol)
DELETE /api/v1/agents/{id}         🆕 desactivar (borrado lógico)
```

### Grupos — todo nuevo
```
GET    /api/v1/groups              🆕
POST   /api/v1/groups              🆕
GET    /api/v1/groups/{id}         🆕 incluye sus asesores y la carga de cada uno
PATCH  /api/v1/groups/{id}         🆕
DELETE /api/v1/groups/{id}         🆕 desactivar
```

### Reglas
```
GET    /api/v1/rules/scoring       listar
POST   /api/v1/rules/scoring       crear
PATCH  /api/v1/rules/scoring/{id}  🆕 editar / activar / desactivar
DELETE /api/v1/rules/scoring/{id}  🆕
POST   /api/v1/rules/scoring/test  🆕 evaluar reglas contra un lead simulado

GET    /api/v1/rules/assignment    (renombra rules/routing)
POST   /api/v1/rules/assignment
PATCH  /api/v1/rules/assignment/{id}   🆕
DELETE /api/v1/rules/assignment/{id}   🆕
```

### Leads
```
POST   /api/v1/leads                   alta individual
POST   /api/v1/leads/batch             carga CSV / XLSX
GET    /api/v1/leads                   gestor: todos (filtros: status, assigned_agent_id,
                                       group_id, source_id, q, rango de fechas)
GET    /api/v1/leads/mine              🆕 asesor: sólo los suyos
GET    /api/v1/leads/{id}              detalle con desglose de reglas aplicadas
POST   /api/v1/leads/{id}/assign       🆕 asignación manual
POST   /api/v1/leads/{id}/discard      🆕 descarte con motivo
```

### Bandeja de entrada — todo nuevo
```
GET    /api/v1/intake                  🆕 filtros: status, batch_id, source_id
GET    /api/v1/intake/{id}             🆕 payload crudo y errores
PATCH  /api/v1/intake/{id}             🆕 corregir el payload
POST   /api/v1/intake/{id}/promote     🆕 reintentar tras corregir
POST   /api/v1/intake/{id}/discard     🆕
```

### Fuentes
```
GET    /api/v1/sources                 🆕
POST   /api/v1/sources                 🆕
PATCH  /api/v1/sources/{id}            🆕 incluye el field_mapping
```

### Notificaciones — todo nuevo
```
GET    /api/v1/notifications           🆕 ?unread_only=true, con contador
POST   /api/v1/notifications/{id}/read 🆕
POST   /api/v1/notifications/read-all  🆕
```

### Salud
```
GET    /health
```

### Formato de error

Se unifica en un único envoltorio. Hoy conviven tres formatos distintos: el del manejador de dominio, el de `HTTPException` de FastAPI y el de los errores de validación de Pydantic.

```json
{
  "error": true,
  "error_code": "INVALID_EMAIL",
  "message": "El formato del correo electrónico no es válido",
  "details": [{"field": "email", "code": "INVALID_EMAIL"}]
}
```

Se añade un manejador para excepciones no controladas, de modo que un fallo de base de datos devuelva el mismo envoltorio en lugar del `{"detail": "Internal Server Error"}` por defecto de Starlette.

---

## 11. Persistencia

### 11.1 Migraciones

Ficheros SQL numerados en `backend/migrations/`, aplicados al arrancar por un runner de unas treinta líneas que registra lo ya ejecutado en una tabla `schema_migrations`. Sin Alembic, que arrastraría SQLAlchemy y contradiría la restricción de diseño del proyecto.

```
migrations/
  001_initial_schema.sql
  002_tenants_and_groups.sql
  003_intake_and_sources.sql
  004_notifications.sql
  005_indexes_and_constraints.sql
```

Sustituye al esquema actual, que se recrea en cada arranque desde una constante de Python y ha ido acumulando `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` de forma irreversible.

### 11.2 Corrección de tipos

| Concepto | Hoy | Objetivo |
|---|---|---|
| Identificadores | `TEXT` | `UUID` |
| Fechas | `TEXT` con ISO | `TIMESTAMPTZ` |
| Importes | `DOUBLE PRECISION` | `NUMERIC(14,2)` — el dominio usa `Decimal`; hoy se pierde precisión en el viaje de ida y vuelta |
| Booleanos | `INTEGER` con `1`/`0` | `BOOLEAN` |
| Atributos y payloads | `TEXT` con JSON serializado | `JSONB` — permite además consultar por atributo |

### 11.3 Integridad e índices

- Claves foráneas entre todas las relaciones. Hoy no hay ninguna.
- `UNIQUE (tenant_id, email)` en asesores. Hoy no existe, así que pueden coexistir dos usuarios con el mismo correo y el login autenticaría contra una fila arbitraria.
- `UNIQUE (tenant_id, name)` en grupos.
- Índices sobre `leads(tenant_id, status)`, `leads(tenant_id, assigned_agent_id, status)`, `leads(tenant_id, created_at DESC)`, `intake_records(tenant_id, status)`, `notifications(recipient_id, is_read)`.
- `ORDER BY` explícito en toda consulta paginada. Sin él, la paginación puede repetir u omitir filas entre páginas.

### 11.4 Conexiones

Pool con `psycopg_pool`, creado en el arranque de la aplicación. Hoy cada bloque transaccional abre y cierra una conexión TCP nueva: una carga de 200 filas produce 200 conexiones secuenciales.

Se elimina también la conexión única en autocommit que hoy se crea en el arranque para el repositorio de webhooks y se comparte entre todos los hilos del threadpool de FastAPI sin sincronización, sin reconexión y sin cierre.

### 11.5 Eficiencia de la carga masiva

Las reglas de la organización se cargan **una vez por lote**, no una vez por fila. Hoy cada fila dispara tres consultas idénticas (reglas de puntuación, reglas de asignación, asesores disponibles), lo que produce del orden de 3N consultas para N filas.

---

## 12. Frontend

### 12.1 Arquitectura

Se conserva la separación en capas ya presente —está bien planteada— pero se conecta de verdad: hoy `presentation/` no importa nada de `application/` ni de `infrastructure/`.

```
src/
├── domain/           modelos y tipos de negocio
├── application/      mappers · servicios · hooks de caso de uso
├── infrastructure/   cliente HTTP · DTOs generados · almacenamiento de sesión
└── presentation/     páginas · componentes · rutas · guards
```

| Elemento | Decisión |
|---|---|
| Enrutado | `react-router` con rutas declarativas. Sustituye al `useState` que hoy hace de navegación: no hay URLs, ni enlaces directos, ni botón atrás |
| Sesión | Token en memoria con rehidratación al recargar; interceptor que añade `Authorization`; manejo centralizado de 401 y 403 |
| Datos | TanStack Query sobre los servicios de aplicación. Aporta caché, reintentos y estados de carga y error, que hoy no existen en ninguna vista |
| Tipos del API | Generados desde el OpenAPI del backend con `openapi-typescript`. Los cuatro desajustes de contrato detectados nacieron de escribir los DTOs a mano; generarlos los elimina de raíz y evita su reaparición |
| Guards | Por rol: `MANAGER` accede a la gestión, `AGENT` sólo a su panel |
| Estilos | Se mantiene Tailwind 4 y los 11 componentes actuales |

### 12.2 Vistas

**Gestor**

| Vista | Contenido |
|---|---|
| Panel | Indicadores: leads del periodo, distribución por estado, sin asignar, bandeja pendiente, carga por asesor |
| Leads | Tabla con filtros por estado, asesor, grupo, fuente y búsqueda. **Columna de asesor asignado** (hoy no se muestra en ninguna parte). Detalle con desglose de reglas aplicadas, asignación manual y descarte |
| Bandeja de entrada | Registros rechazados con su payload y sus errores. Corregir, reintentar o descartar |
| Alta de lead | Formulario individual |
| Carga masiva | Subida real de CSV/XLSX con previsualización, mapeo de columnas y resumen de resultado por fila |
| Asesores | Alta, edición, asignación a grupo, activación y desactivación. Carga actual de cada uno |
| Grupos | CRUD, estrategia por defecto, capacidad, miembros |
| Reglas de puntuación | Constructor tipo "Si [campo] [operador] [valor] entonces [puntos]", con activación y probador |
| Reglas de asignación | Constructor por rango de puntuación, grupo o asesores, modo de coincidencia, estrategia y prioridad |
| Notificaciones | Campana con contador y desplegable, con navegación al elemento relacionado |

**Asesor**

| Vista | Contenido |
|---|---|
| Mis leads | Lista de leads asignados, ordenada por fecha de asignación, con búsqueda y filtro |
| Detalle | Ficha completa del lead: datos de contacto, empresa, presupuesto, sector, atributos personalizados, puntuación y desglose |
| Notificaciones | Campana |

### 12.3 Correcciones necesarias

- `getLeads()` debe leer la respuesta paginada. Hoy declara un array y hace `.map` sobre lo que en realidad es `{items, total, limit, offset, has_more}`.
- El DTO de respuesta de ingesta no corresponde al del backend en tres campos.
- La carga masiva debe subir el fichero de verdad. Hoy fabrica un lead falso.
- El bloque `catch` de la carga escribe el mensaje de error en la variable de éxito, y se renderiza en verde con icono de acierto: un fallo se muestra como un acierto.
- El cliente HTTP fija `Content-Type: application/json`, lo que rompería el login, que es `form-urlencoded`.
- Falta el proxy de desarrollo en `vite.config.ts`: con la configuración actual, `npm run dev` no puede hablar con el backend.

---

## 13. Docker y arranque

Objetivo: `docker compose up` levanta el sistema completo y utilizable.

| Cambio | Motivo |
|---|---|
| `.dockerignore` en backend y frontend | El contexto de build arrastra hoy `node_modules` y el entorno virtual del host |
| `CORS_ORIGINS` explícito en el compose, incluyendo `http://localhost` sin puerto | El valor por defecto es `http://localhost:80`, pero el navegador envía el origen sin el puerto por defecto: la comprobación falla |
| `condition: service_healthy` en la dependencia del frontend | Hoy nginx puede arrancar antes que el backend y abortar por upstream no resuelto |
| Usuario no privilegiado en la imagen del backend | Hoy corre como root |
| Migraciones al arrancar, antes de servir | Sustituye a la creación de esquema desde código |
| Semilla opcional de demostración | Una organización, un gestor, dos grupos, cuatro asesores y un juego de reglas, para que la aplicación sea navegable desde el primer arranque en clase |
| Perfil `test` con base de datos efímera | Permite ejecutar la suite completa con un comando |
| Perfil `dev` con bind mounts y recarga | Evita reconstruir la imagen en cada cambio |
| `.env.example` documentado | Hoy no existe, y `VITE_API_BASE_URL` no está documentada en ninguna parte |

---

## 14. Estrategia de pruebas

| Nivel | Alcance | Base de datos | Cuándo se ejecuta |
|---|---|---|---|
| Unitario | Dominio completo, casos de uso con dobles, políticas, motores | No | Siempre. `pytest -m unit` debe estar verde sin ninguna infraestructura |
| Integración | Un test por repositorio: ciclo de guardado, recuperación, listado y paginación. Runner de migraciones | Sí | Con el compose levantado |
| Extremo a extremo | Un único recorrido: bootstrap → login → grupo → asesor → reglas → ingesta → lead asignado → el asesor lo ve | Sí | Con el compose levantado |
| Arquitectura | Falla si `domain/` o `application/` importan `infrastructure/` | No | Siempre |

**Aislamiento.** Base de datos `leads_test` independiente en el mismo contenedor, y una fixture `autouse` que ejecuta `TRUNCATE ... RESTART IDENTITY CASCADE` antes de cada test. No se usa la técnica de transacción envolvente con rollback porque el Unit of Work abre su propia conexión y confirma por su cuenta, de modo que un rollback externo no vería esos datos.

Esto elimina también la fragilidad actual: los tests extremo a extremo comparten hoy la base de datos de desarrollo, y por eso contienen ramas defensivas como `if bootstrap_resp.status_code == 401: ... elif`. El último commit del repositorio es literalmente un parche para hacerlos idempotentes.

**Infraestructura del frontend.** Se añaden `jsdom` y `@testing-library/react`, hoy ausentes: con `environment: 'node'` es imposible escribir un solo test de componente.

**Reducción deliberada.** Los doce tests extremo a extremo actuales se colapsan en uno solo. El valor de esa capa es verificar que el cableado funciona, no cubrir casos de negocio: eso corresponde a los unitarios, que son órdenes de magnitud más rápidos.

---

## 15. Fases

| Fase | Contenido | Criterio de aceptación |
|---|---|---|
| **F0** — Fundación | Puertos de seguridad, DTOs sin framework, políticas de dominio, composition root, contexto de petición, excepciones sin HTTP, migraciones, pool, logging, `conftest.py`, marcadores, test de arquitectura | El test de arquitectura pasa; `pytest -m unit` verde sin base de datos; la suite completa verde con el compose levantado |
| **F1** — Grupos y asignación | `Tenant`, `SalesGroup`, `AssignmentRule` renovada, motor de asignación corregido, carga derivada, CRUD completo de asesores, grupos y reglas | Un gestor crea grupos, asesores y reglas, y un lead ingestado se asigna al asesor correcto según cada estrategia |
| **F2** — Ingesta y ciclo de vida | `LeadSource`, `IntakeRecord`, pipeline unificado, máquina de estados del lead, asignación manual, descarte, `/leads/mine` | Un lead mal formado queda en la bandeja con su error; el gestor lo corrige y se promueve; un lead sin asesor queda `UNASSIGNED` y se puede asignar a mano |
| **F3a** — Notificaciones | `Notification`, manejadores de eventos, endpoints, contador de no leídas | El asesor recibe aviso al asignársele un lead; el gestor lo recibe ante un rechazo o un lead sin asignar |
| **F4** — Frontend | Arquitectura (router, sesión, capa de datos, guards, tipos generados) y después las vistas de ambos paneles | Un gestor y un asesor completan sus recorridos contra el backend real, sin ningún dato simulado |

Cada fase es entregable y demostrable por separado. La ordenación no es negociable: F0 establece las fronteras que el resto respeta, y hacerla al final significaría reescribir todo lo construido encima.

---

## 16. Fuera de alcance

Modelado en el dominio, sin adaptador implementado. El diseño deja los puntos de extensión preparados para que añadirlos no requiera tocar el núcleo.

| Elemento | Estado | Qué faltaría |
|---|---|---|
| Webhooks de entrada | `SourceKind.WEBHOOK` y el campo `secret` existen en el modelo | Adaptador de entrada con verificación HMAC, endpoint público por fuente, y la interfaz de alta de fuentes externas |
| Webhooks de salida | El despachador HMAC ya existe en el código actual y se conserva | Entidad de configuración con CRUD, suscripción del manejador al bus de eventos, reintentos y cola de fallidos |
| Ciclo comercial del lead | — | Estados `CONTACTED`, `WON`, `LOST` y las acciones del asesor sobre sus leads |
| Métricas e informes | — | Agregados de conversión, tiempo de respuesta y rendimiento por asesor |
| Refresh token y cierre de sesión | — | El token actual dura sesenta minutos sin renovación ni revocación |
| Carga masiva asíncrona | — | Hoy el procesamiento es síncrono dentro de la petición HTTP |

Los diagramas de `docs/diagrams/` quedarán desactualizados con este diseño y deben regenerarse en formato draw.io al cerrar F1.

---

## 17. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| F0 toca prácticamente todos los ficheros del backend | Alto | Se hace primero, con la suite unitaria como red. Los tests de dominio deben seguir verdes sin modificarlos; los de casos de uso se adaptarán a los puertos nuevos, y esa adaptación es en sí la prueba de que la inversión de dependencias funciona |
| La migración de esquema no es compatible hacia atrás | Medio | Los datos actuales son de desarrollo. Migración destructiva documentada, con semilla de demostración para repoblar |
| El alcance crece por encima del tiempo disponible | Alto | Las fases son entregables independientes. F0 a F2 ya constituyen una demostración defendible; F3a y F4 se pueden recortar |
| El frontend depende de que el contrato del backend esté cerrado | Medio | Los tipos se generan desde el OpenAPI: cuando el backend cambia, el frontend deja de compilar en vez de fallar en ejecución |
