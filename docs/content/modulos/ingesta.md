# Ingesta

Recibe los leads por las vías de entrada habilitadas para la organización, garantiza que ningún
payload se pierde —se pueda interpretar o no— y lo convierte en un `Lead` en una fase de
procesamiento independiente de la petición HTTP que lo trajo.

## Cómo funciona

La ingesta ocurre en dos fases, en transacciones y procesos distintos. La primera responde rápido y
sin interpretar nada: guarda el payload tal cual llegó y deja constancia de que hay trabajo. La
segunda, en el `intake-worker`, es la que intenta construir un `Lead` a partir de ese payload.

- **Recepción** (`ReceiveIntakeUseCase`): en **una transacción** crea un `IntakeJob`; si la vía es el
  formulario individual, también el `IntakeRecord` con el payload sin tocar; si es una carga de
  fichero, guarda el fichero crudo en `intake_files`; y registra la orden de procesarlo en el outbox
  (canal `job`). Responde `202 Accepted` con el identificador del trabajo antes de interpretar una
  sola línea.
- **Procesamiento** (`ProcessIntakeJobUseCase`): recorre los `IntakeRecord` en estado `PENDING` de
  un trabajo y entrega cada uno a `IngestLeadUseCase`, que construye el `Lead`, lo hace atravesar
  viabilidad, puntuación y asignación, y marca el registro como `PROMOTED` o `REJECTED`.

El camino entre las dos es [el outbox y RabbitMQ](../eventos/rabbitmq.md): `backend-worker` publica la
orden en `intake.jobs` con *publisher confirms* y el worker la consume. Si RabbitMQ está caído, el
trabajo espera `PENDING` en el outbox; no hay otra ruta que lo procese dentro de la API.

```mermaid
flowchart TD
    A[Formulario individual] -->|POST /leads/ingest| R[ReceiveIntakeUseCase]
    B[Carga de fichero CSV/XLSX] -->|POST /leads/batch-upload| R
    RP[Reproceso] -->|POST /jobs/id/reprocess| OB

    R --> J1[(IntakeJob)]
    R --> REC1[(IntakeRecord PENDING<br/>sólo en el formulario)]
    R --> FI[(intake_files<br/>sólo en la carga)]
    R --> OB[(outbox canal job)]

    J1 --> RESP[202 Accepted]
    OB -. relay y RabbitMQ .-> W[intake-worker]

    W -->|carga de fichero| PBU[ProcessBatchUseCase]
    FI --> PBU
    PBU -->|una fila, un registro| REC2[(IntakeRecord PENDING)]
    PBU --> PJ[ProcessIntakeJobUseCase]
    W -->|formulario| PJ
    REC1 --> PJ
    REC2 --> PJ

    PJ --> IL[IngestLeadUseCase]
    IL -->|payload inválido| REJ[(IntakeRecord REJECTED)]
    IL -->|payload válido| LEAD[Viabilidad, puntuación y asignación]

    REJ --> INBOX[Bandeja de revisión]
    INBOX -->|corrige y promueve| IL
    INBOX -->|descarta| DESC[(IntakeRecord DISCARDED)]
```

### Las tres vías de entrada

Cada organización recibe dos fuentes (`LeadSource`) al darse de alta: una `MANUAL_FORM` para el
formulario individual y otra `FILE_UPLOAD` para la carga de fichero. Desde F3 llegan unos segundos
después del alta, cuando el consumidor `intake.tenants` recibe el estado de la organización nueva
que publica identity ([Organizaciones](organizaciones.md#el-alta-una-transaccion-y-un-evento)). `ReceiveIntakeUseCase`
resuelve la fuente activa según el tipo de trabajo, así que ninguna de las dos exige configuración
previa. Una tercera vía, `WEBHOOK`, está declarada en `LeadSourceKind` pero todavía no tiene un
endpoint que la sirva.

La carga de fichero tiene una asimetría respecto al formulario: en la recepción no se crean
registros, sólo el `IntakeJob` y el fichero crudo en `intake_files` (`bytea`, con un límite de 10 MB:
un cuerpo mayor se rechaza con `413 PAYLOAD_TOO_LARGE`, en el gateway y en el propio endpoint).
`ProcessBatchUseCase` lo parsea **en el worker, una sola vez** —lo lee con `FOR UPDATE` y marca
`parsed_at` en la misma transacción que los registros— y sólo entonces materializa un `IntakeRecord`
por fila, antes de entregarlos al mismo `ProcessIntakeJobUseCase` que procesa la vía individual. El
fichero se conserva: lo que sobrevive es el fichero y una fila por registro.

### Reproceso de un trabajo interrumpido

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> PROCESSING: start()
    PENDING --> FAILED: fichero ilegible
    PROCESSING --> COMPLETED: todos los registros se resolvieron
    PROCESSING --> PROCESSING: un registro falla, nack y reentrega
    PROCESSING --> PENDING: POST /jobs/{job_id}/reprocess
    COMPLETED --> [*]
    FAILED --> [*]
```

Un trabajo que falla a mitad de proceso —una excepción no prevista al interpretar un registro— no se
marca `FAILED`: se queda en `PROCESSING`, porque los registros que sí se resolvieron ya tienen su
resultado y sólo faltan los que quedaron `PENDING`. El worker hace entonces `nack` con reencolado, y
RabbitMQ lo entrega de nuevo, hasta tres veces; a la tercera el mensaje pasa a `intake.jobs.dlq`.
Cada entrega vuelve a leer únicamente los registros todavía `PENDING`. Sólo un fichero ilegible marca
el trabajo `FAILED` de forma directa, porque en ese caso no llegó a generar ni una fila.

`POST /jobs/{job_id}/reprocess` es el camino manual, para un trabajo que llegó a la DLQ o quedó
detenido. **No procesa en la petición**: reinicia los contadores, deja el trabajo `PENDING`, registra
una orden nueva en el outbox y responde `202`. El resultado se consulta después con
`GET /jobs/{job_id}`.

!!! note
    Cada ejecución procesa como máximo 10 000 registros pendientes. Un trabajo más grande que eso
    necesita más de un reproceso para vaciarse: el resto se queda `PENDING` a la espera.

### La bandeja de revisión

`GET /records` lista los `IntakeRecord` de la organización, filtrables por estado. Un registro
`REJECTED` puede corregirse y reintentarse (`POST /records/{record_id}/promote`, que ejecuta el
mismo `IngestLeadUseCase` con un payload corregido) o descartarse
(`POST /records/{record_id}/discard`). Ninguna de las dos operaciones borra el registro: la bandeja
es el historial completo de lo que entró, se haya podido trabajar o no. El contrato de cada endpoint
está en la [referencia de la API](../desarrollo/api-referencia.md).

## Piezas

| Pieza | Responsabilidad |
|---|---|
| `IntakeJob` | Agrega una operación de ingesta —una unidad o un fichero— y su progreso |
| `IntakeRecord` | Guarda el payload tal cual llegó, y si se promovió, rechazó o descartó |
| `ReceiveIntakeUseCase` | Persiste el trabajo (y el fichero, si lo hay), registra la orden en el outbox y responde antes de interpretar el payload |
| `ProcessIntakeJobUseCase` | Recorre los registros `PENDING` de un trabajo y los interpreta |
| `IngestLeadUseCase` | Interpreta el payload: viabilidad, puntuación y asignación |
| `ProcessBatchUseCase` | Parsea el fichero guardado, una sola vez, y materializa un `IntakeRecord` por fila |
| `intake_worker/` (`consumer.py`, `messages.py`, `main.py`) | Consumen `intake.jobs` y ejecutan el trabajo; `ack`, `nack` o dead-letter según el resultado |
| `intake_router.py` | Endpoints de ingesta, bandeja de revisión y reproceso |

## Decisiones que lo explican

- [ADR-0009](../decisiones/0009-registrar-antes-de-interpretar.md): por qué se guarda antes de leer.
- [ADR-0010](../decisiones/0010-recepcion-y-procesamiento-separados.md): por qué hay dos fases.
- [ADR-0027](../decisiones/0027-cola-para-el-trabajo-de-fondo.md) y [ADR-0034](../decisiones/0034-encolado-por-outbox-y-fichero-durable.md): la cola, el outbox y el fichero guardado.
- [ADR-0008](../decisiones/0008-correo-opcional.md): por qué un lead puede no traer correo.

## Dónde vive

- `backend/src/domain/entities/intake_job.py`
- `backend/src/domain/entities/intake_record.py`
- `backend/src/application/use_cases/receive_intake_use_case.py`
- `backend/src/application/use_cases/process_intake_job_use_case.py`
- `backend/src/application/use_cases/ingest_lead_use_case.py`
- `backend/src/application/use_cases/process_batch_use_case.py`
- `backend/src/application/use_cases/intake_job_use_cases.py`
- `backend/src/application/use_cases/intake_record_use_cases.py`
- `backend/src/infrastructure/intake_worker/`
- `backend/src/infrastructure/adapters/input/api/intake_router.py`
