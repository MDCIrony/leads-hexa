# Modelo de datos

El modelo entidad-relación completo, tal como lo dejan las ocho migraciones de
`backend/migrations/`, y las tres máquinas de estados que gobiernan el ciclo de vida de un lead
mientras lo atraviesa.

## Diagrama entidad-relación

```mermaid
erDiagram
    TENANT {
        uuid id PK
        text name
        text slug UK
        boolean is_active
        timestamptz created_at
    }
    AGENT {
        uuid id PK
        uuid tenant_id FK "nulo sólo para ADMIN"
        uuid group_id FK "nulo sin grupo"
        text name
        text email "único por organización"
        text role
        text hashed_password
        boolean is_active
    }
    SALES_GROUP {
        uuid id PK
        uuid tenant_id FK
        text name "único por organización"
        text description
        text default_strategy
        integer capacity_per_agent
        boolean is_active
        timestamptz created_at
    }
    LEAD_SOURCE {
        uuid id PK
        uuid tenant_id FK
        text name "único por organización"
        text kind
        jsonb field_mapping
        text secret_hash "reservado, sin uso"
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }
    LEAD {
        uuid id PK
        uuid tenant_id FK
        uuid source_id FK
        text first_name
        text last_name
        text email "opcional"
        text phone
        text company
        numeric budget
        text industry
        jsonb custom_attributes
        integer score
        jsonb score_breakdown
        text status
        uuid assigned_agent_id "sin clave foránea física"
        timestamptz assigned_at
        text discard_reason
        text disqualification_reason
        timestamptz created_at
        timestamptz updated_at
    }
    SCORING_RULE {
        uuid id PK
        uuid tenant_id "sin clave foránea física"
        text name
        jsonb conditions
        integer score_delta
        integer priority
        boolean is_active
    }
    ASSIGNMENT_RULE {
        uuid id PK
        uuid tenant_id FK
        text name
        integer min_score
        integer max_score
        uuid target_group_id FK
        jsonb target_agent_ids
        text agent_match_mode
        text strategy
        integer priority
        boolean is_active
        integer rr_cursor
        jsonb conditions
    }
    DISQUALIFICATION_RULE {
        uuid id PK
        uuid tenant_id FK
        text name
        jsonb conditions
        integer priority
        boolean is_active
    }
    INTAKE_JOB {
        uuid id PK
        uuid tenant_id FK
        uuid source_id FK
        text kind
        text status
        integer total_items
        integer succeeded
        integer failed
        timestamptz created_at
        timestamptz completed_at
    }
    INTAKE_RECORD {
        uuid id PK
        uuid tenant_id FK
        uuid source_id FK
        uuid job_id FK
        jsonb payload
        text status
        uuid lead_id FK
        timestamptz received_at
        timestamptz processed_at
    }
    INTAKE_ERROR {
        uuid id PK
        uuid intake_record_id FK
        text field
        text received_value
        text message
        text error_code
    }
    NOTIFICATION {
        uuid id PK
        uuid tenant_id FK
        uuid recipient_id FK
        text kind
        uuid lead_id "puntero sin clave foránea"
        uuid intake_record_id "puntero sin clave foránea"
        text message
        boolean is_read
        timestamptz created_at
    }
    WEBHOOK_CONFIG {
        uuid id PK
        uuid tenant_id "sin clave foránea física"
        text event_type
        text target_url
        text secret_token
    }

    TENANT |o--o{ AGENT : tiene
    TENANT ||--o{ SALES_GROUP : tiene
    TENANT ||--o{ LEAD_SOURCE : tiene
    TENANT ||--o{ LEAD : tiene
    TENANT ||--o{ SCORING_RULE : tiene
    TENANT ||--o{ ASSIGNMENT_RULE : tiene
    TENANT ||--o{ DISQUALIFICATION_RULE : tiene
    TENANT ||--o{ INTAKE_JOB : tiene
    TENANT ||--o{ INTAKE_RECORD : tiene
    TENANT ||--o{ NOTIFICATION : tiene
    TENANT ||--o{ WEBHOOK_CONFIG : tiene
    SALES_GROUP |o--o{ AGENT : agrupa
    SALES_GROUP |o--o{ ASSIGNMENT_RULE : "destino de"
    LEAD_SOURCE ||--o{ LEAD : origina
    LEAD_SOURCE ||--o{ INTAKE_RECORD : origina
    LEAD_SOURCE ||--o{ INTAKE_JOB : origina
    INTAKE_JOB |o--o{ INTAKE_RECORD : agrupa
    INTAKE_RECORD ||--o{ INTAKE_ERROR : detalla
    INTAKE_RECORD ||--o| LEAD : promueve
    AGENT |o--o{ LEAD : "asignado a"
    AGENT ||--o{ NOTIFICATION : recibe
```

## Los agregados

### Tenant

`domain/entities/tenant.py`, tabla `tenants`. Representa a la organización cliente. `name` no
puede quedar vacío; `slug` se deriva del nombre plegando tildes y símbolos (`slugify()`) y es
único en toda la plataforma, no sólo dentro de una organización — evita que "Solución" y
"Solucion" produzcan dos organizaciones indistinguibles en el listado del administrador. Crear una
organización crea, en la misma transacción, sus dos fuentes por defecto (`Formulario manual`,
`Carga de fichero`) y su primer gestor.

### Agent

`domain/entities/agent.py`, tabla `agents`. Es a la vez credencial de acceso y receptor de leads.
`tenant_id` es nulo únicamente para `ADMIN`. `email` es único por organización, o único en toda la
plataforma si `tenant_id` es nulo — lo garantizan los dos índices únicos parciales de
`002_tenants.sql`, no una comprobación de aplicación. El hash de la contraseña vive en la misma
fila (`hashed_password`); no hay un agregado de credenciales separado, y es el mapeador de
respuesta del router quien evita que ese campo llegue al cliente, omitiéndolo explícitamente. El
formato del correo no lo valida el dominio —`email` es un `str` llano— sino el esquema Pydantic de
entrada.

### SalesGroup

`domain/entities/sales_group.py`, tabla `sales_groups`. Agrupa asesores que comparten política de
asignación. `name` no vacío y único por organización; `capacity_per_agent`, si se define, debe ser
mayor que cero. Borrar un grupo no arrastra sus asesores ni las reglas que lo señalan: `group_id`
en `agents` y `target_group_id` en `assignment_rules` quedan en `NULL`, así que el gestor ve el
hueco en vez de perder datos en cascada.

### LeadSource

`domain/entities/lead_source.py`, tabla `lead_sources`. El canal por el que entra un lead. `name`
no vacío y único por organización; `field_mapping`, si se define, exige claves y valores no
vacíos. Toda organización nace con dos fuentes activas, `MANUAL_FORM` y `FILE_UPLOAD`. La columna
`secret_hash` está reservada para el webhook entrante — la entidad de dominio no tiene hoy ningún
atributo que la use.

### Lead

`domain/entities/lead.py`, tabla `leads`. El prospecto comercial: existe si sus datos son
coherentes, no si son comercialmente útiles. `budget` es un `Money` (`Decimal` no negativo);
`email`, si viene, debe tener formato válido, pero su ausencia ya no impide crear el lead. Cada
transición de estado está guardada en su propio método — ver la máquina de estados más abajo.
`assigned_agent_id` no lleva clave foránea física: es `Lead._bind_agent()` quien impide asignar el
lead a un asesor de otra organización, comparando `tenant_id` en memoria antes de guardar.

### ScoringRule y AssignmentRule

`domain/entities/rule.py`, tablas `scoring_rules` y `assignment_rules`. Comparten `conditions`,
una lista de `Criterion` serializada en JSONB. `ScoringRule` no exige un nombre no vacío — a
diferencia de `AssignmentRule` y `DisqualificationRule`, que sí lo hacen. `AssignmentRule` exige
al menos un `target_group_id` o un `target_agent_id` (si no, no podría producir ningún candidato),
y si define `max_score` éste debe ser mayor o igual que `min_score`. `rr_cursor` es el cursor del
reparto rotatorio, persistido en la fila para que sobreviva entre peticiones.

### DisqualificationRule

`domain/entities/disqualification_rule.py`, tabla `disqualification_rules`. Exige nombre no vacío
y al menos una condición: una regla sin condiciones se cumpliría para cualquier lead y
descalificaría a la organización entera.

### IntakeJob, IntakeRecord e IntakeError

`domain/entities/intake_job.py` y `domain/entities/intake_record.py`; tablas `intake_jobs`,
`intake_records` e `intake_errors`. Un `IntakeJob` agrupa una operación de ingesta completa, sea de
un único lead o de un fichero entero. Cada payload recibido genera su propio `IntakeRecord`, con el
dato **tal cual llegó** en `payload`. Los errores de validación viven en su propia tabla,
`intake_errors`, no embebidos en JSONB: un registro puede fallar por varios campos a la vez, y el
gestor necesita saber cuáles. `promote()` y `reject()` sólo aceptan un registro en `PENDING` o
`REJECTED`; `reject()` exige además al menos un error.

### Notification

`domain/entities/notification.py`, tabla `notifications`. El aviso interno; exige un `message` no
vacío. `lead_id` e `intake_record_id` son punteros informativos sin clave foránea: sólo permiten
que la interfaz navegue al elemento relacionado, y la notificación sobrevive aunque ese elemento
se borre.

### WebhookConfig

`domain/entities/webhook.py`, tabla `webhook_configs`. Configura un destino externo para el
webhook saliente firmado. No declara invariantes propias más allá del tipado de sus
identificadores, y hoy no existe ningún endpoint que lo dé de alta: sólo el despachador que lo
consume está escrito. Ver [ADR-0017](../decisiones/0017-retirada-de-webhook-dispatched.md).

## Máquinas de estados

### Lead

Seis estados. Cada transición vive en un método de `Lead` que comprueba el estado de partida,
salvo `qualify()` y `disqualify()`: ninguno de los dos exige un estado previo concreto en el propio
método — el pipeline de ingesta es quien garantiza que sólo se invocan sobre un lead recién creado.

```mermaid
stateDiagram-v2
    [*] --> NEW
    NEW --> DISQUALIFIED: disqualify(), el motor de viabilidad encuentra una regla que se cumple
    NEW --> QUALIFIED: qualify(), tras puntuar sin descalificación
    QUALIFIED --> ASSIGNED: assign_to(), el motor de asignación encuentra asesor
    QUALIFIED --> UNASSIGNED: leave_unassigned(), ninguna regla produce asesor
    UNASSIGNED --> ASSIGNED: assign_to(), asignación manual del gestor
    ASSIGNED --> ASSIGNED: reassign_to(), reasignación a otro asesor
    ASSIGNED --> UNASSIGNED: unassign(), liberación
    NEW --> DISCARDED: discard(reason)
    QUALIFIED --> DISCARDED: discard(reason)
    UNASSIGNED --> DISCARDED: discard(reason)
    ASSIGNED --> DISCARDED: discard(reason)
    DISQUALIFIED --> [*]
    DISCARDED --> [*]
```

`DISQUALIFIED` y `DISCARDED` son terminales: ningún método transiciona fuera de ellos. `discard()`
los excluye a propósito de sus estados de partida — ya salieron del flujo por su cuenta, y
descartarlos otra vez no aporta información.

### IntakeRecord

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> PROMOTED: promote(), el lead resultante es válido
    PENDING --> REJECTED: reject(), el payload no valida
    REJECTED --> PROMOTED: promote(), tras corregir el payload
    REJECTED --> REJECTED: reject(), la corrección vuelve a fallar
    PENDING --> DISCARDED: discard()
    REJECTED --> DISCARDED: discard()
    PROMOTED --> [*]
    DISCARDED --> [*]
```

`PROMOTED` y `DISCARDED` son terminales. `PENDING` y `REJECTED` son los únicos estados
reabribles: son los dos desde los que `promote()` y `reject()` aceptan actuar, lo que deja al
gestor corregir un registro rechazado y reintentarlo tantas veces como haga falta.

### IntakeJob

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> PROCESSING: start()
    PENDING --> FAILED: fail(), fichero ilegible antes de arrancar
    PROCESSING --> COMPLETED: complete(), terminó sin interrupciones
    PROCESSING --> PENDING: reset_counters(), se relanza tras una interrupción
    COMPLETED --> [*]
    FAILED --> [*]
```

Un trabajo interrumpido por un fallo inesperado a mitad de proceso se queda en `PROCESSING` —
ninguna transición lo mueve por sí sola— hasta que el gestor lo reprocesa. `COMPLETED` no es una
afirmación de éxito: un trabajo con diez registros rechazados también termina en `COMPLETED`,
con `failed = 10`. Terminado y salió bien son preguntas distintas, y sólo la primera decide el
estado.

## Ver también

- [El recorrido de un lead](recorrido-de-un-lead.md) muestra cuándo se dispara cada transición.
- [Organizaciones](../modulos/organizaciones.md) explica `Tenant`, `SalesGroup` y `LeadSource` desde
  el negocio.
- [ADR-0007 · Tipos nativos de SQL](../decisiones/0007-tipos-nativos-de-sql.md)
- [ADR-0013 · Condiciones en JSONB](../decisiones/0013-condiciones-en-jsonb.md)
