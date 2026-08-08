# F2d — Recepción y procesamiento separados

**Estado:** propuesto
**Documento maestro:** [spec del MVP](2026-08-07-lead-router-mvp-design.md)
**Fundamento conceptual:** [Dónde se valida lo que entra](../conceptos/01-donde-se-valida-lo-que-entra.md)
**Orden:** va **antes** de [F2c](2026-08-08-f2c-reglas-componibles-design.md). F2c reescribe el motor de
reglas dentro del mismo caso de uso que esta fase parte en dos; hacerlo al revés obliga a rehacerlo.

**Objetivo en una frase:** que recibir un lead y procesarlo dejen de compartir transacción, para que
ningún fallo al procesar pueda destruir la constancia de haber recibido.

---

## 1. El problema, medido

F2b prometía que *«todo payload que llega se persiste antes de intentar interpretarlo»*. Se colocó ese
guardado dentro del servicio de ingesta, y eso lo deja fuera de alcance en dos casos:

| Petición con credencial válida | Respuesta | Registros creados |
|---|---|---|
| `email: "sin-arroba"` | `422` | **0** |
| `budget: "abc"` | `422` | **0** |
| Falta un campo obligatorio | `422` | **0** |

El framework valida el cuerpo antes de llamar al endpoint, así que el servicio —que es quien tenía la
instrucción de guardar— no llega a ejecutarse.

Y hay un tercer caso que ninguna prueba cubre: el `UnitOfWork` hace **rollback ante cualquier
excepción**, y el guardado del registro vive dentro de ese bloque. Un fallo imprevisto después del
guardado lo deshace.

## 2. La decisión

Separar el recorrido en dos fases con transacciones distintas:

```
FASE 1 · recepción        petición → Job + Record persistidos → 202 Accepted
FASE 2 · procesamiento    leer los Record → producir los Lead → marcar los Record
```

La fase 2 corre **en segundo plano**, después de responder. La consecuencia buscada:

> El servicio de ingesta deja de **crear** el registro y pasa a **recibirlo** y marcarlo.

No es un cambio de rendimiento. Es que dos transacciones distintas hacen **imposible por
construcción** que un fallo al procesar borre la constancia de haber recibido.

## 3. El modelo

```
IntakeJob (nuevo)                          IntakeRecord (existente)
  id           ← es el correlation_id        job_id      → IntakeJob   [NUEVO]
  tenant_id    → Tenant                      tenant_id   → Tenant
  source_id    → LeadSource         1:N      source_id   → LeadSource
  kind         SINGLE | BATCH       ◄──────   payload     JSONB crudo
  status       PENDING|PROCESSING|            status      PENDING|PROMOTED|
               COMPLETED|FAILED                           REJECTED|DISCARDED
  total_items / succeeded / failed            errors      [IntakeError]
  created_at / completed_at                   lead_id     → Lead
```

**Un ingreso individual es un job con un item.** No hay dos caminos: hay uno con `total_items = 1` y
otro con `total_items = N`. La homogeneidad se paga ahora, no después.

**El `correlation_id` es el `job_id`.** Dos identificadores para la misma cosa serían ceremonia que
mantener sincronizada; cuando entren colas y haga falta correlacionar entre sistemas, ahí tendrá
sentido separarlos.

### Estados de `IntakeJob`

| Estado | Significa | Transiciona a |
|---|---|---|
| `PENDING` | Recibido, sin empezar | `PROCESSING` |
| `PROCESSING` | En curso | `COMPLETED`, `FAILED` |
| `COMPLETED` | Todos los items alcanzaron estado terminal | — |
| `FAILED` | El job no pudo siquiera empezar (fichero ilegible, fuente inexistente) | — |

`COMPLETED` **no significa que todo saliera bien**: significa que ya no queda trabajo. Un job con diez
items rechazados está `COMPLETED` con `failed = 10`. La distinción entre «terminó» y «salió bien» vive
en los contadores, no en el estado.

`total_items` es nulo hasta que el fichero se parsea, porque el parseo ocurre en la fase 2.

## 4. Los dos flujos

### Ingesta individual

```
POST /api/v1/intake/leads/ingest
  ① Job(SINGLE, PENDING, total_items=1) + Record(PENDING)   ← transacción propia, commit
  ② background: procesar
  ③ 202 { job_id, record_ids: [...], status: "PENDING" }
```

El cuerpo se acepta **sin validación de formato de correo**: esa comprobación duplicaba la del dominio
y es la que producía el `422`. Lo que Pydantic no pueda interpretar por tipo o por campo ausente sigue
dando `422`, y ese caso queda fuera de alcance (§7).

### Carga masiva

```
POST /api/v1/intake/leads/batch-upload
  ① Job(BATCH, PENDING, total_items=NULL)                   ← commit
  ② background: parsear → N Record(PENDING) → procesar cada uno → contadores
  ③ 202 { job_id, status: "PENDING" }
```

El parseo va en segundo plano a propósito: un fichero de diez mil filas no puede bloquear la
respuesta. Ése es el motivo de que `total_items` nazca nulo.

## 5. Consulta y reproceso

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/v1/intake/jobs?status=&limit=&offset=` | Lista paginada de jobs |
| `GET` | `/api/v1/intake/jobs/{job_id}` | Estado y contadores de uno |
| `GET` | `/api/v1/intake/records?job_id=` | Los items de un job (filtro nuevo sobre el endpoint existente) |
| `POST` | `/api/v1/intake/jobs/{job_id}/reprocess` | Relanza los items no terminales |

**El reproceso existe por una limitación conocida:** el trabajo de fondo corre en el mismo proceso que
la API. Si el contenedor cae entre la respuesta y el final del trabajo, el job queda en `PROCESSING`
para siempre. Se decidió **hacerlo visible y reprocesable a mano** en vez de detectarlo por
antigüedad, que exigiría un umbral arbitrario, o ignorarlo.

Reprocesar toma los `Record` que siguen en `PENDING` y los vuelve a pasar por la fase 2 con el payload
guardado intacto. **Es la misma operación que ejecutará la cola** cuando exista: construirla ahora no
es trabajo perdido, es la interfaz que la cola consumirá.

## 6. Reparto de responsabilidades

| Quién | Qué hace | Qué deja de hacer |
|---|---|---|
| Router de ingesta | Crea `Job` y `Record`, encola el trabajo, responde `202` | Resolver la fuente antes del caso de uso |
| `ReceiveIntakeUseCase` (nuevo) | Fase 1: persiste job y registros en transacción propia | — |
| `ProcessIntakeJobUseCase` (nuevo) | Fase 2: recorre los registros, invoca la ingesta, actualiza contadores | — |
| `IngestLeadUseCase` | **Recibe** un registro, produce el lead, lo marca `PROMOTED`/`REJECTED` | **Crear** el registro |

El parámetro `existing_record` que F2b añadió a `IngestLeadUseCase` pasa de opcional a **obligatorio**,
y con eso el servicio de ingesta ya no conoce la creación del registro. Es la inversión completa: crea
la fase 1, marca la fase 2.

## 7. Lo que esta fase NO hace

- **Colas ni trabajadores externos.** El trabajo de fondo es el del propio framework, en proceso. La
  limitación se documenta y se mitiga con el reproceso manual.
- **Reintento automático.** Un job atascado se relanza a mano.
- **Registrar peticiones que no superan la validación de esquema.** Un `422` por tipo incorrecto o
  campo ausente sigue sin dejar rastro: no hay `tenant_id` resuelto ni `source_id` con el que escribir
  antes de que el framework corte. Se documenta como límite conocido y **no se resuelve aquí**.

  La razón de fondo es que no tiene arreglo dentro de este modelo: el esquema de entrada se declara
  estáticamente y se congela al importar, así que no puede ser sensible a la organización que llama.
  El día que cada organización defina sus campos, ese `422` no se quita — **deja de existir**, porque
  no queda esquema fijo que violar. Ver
  [la definición del lead por organización](../product/mejoras-futuras/02-la-definicion-del-lead-por-organizacion.md).
- **Notificar al emisor cuando el trabajo termina.** El cliente consulta; nadie le avisa.
- **Reprocesar por cambio de configuración** («relanza todo lo de esta fuente con el mapeo nuevo»).
  El modelo queda preparado —el payload se guarda intacto y `job_id` agrupa— pero la operación masiva
  por fuente no se construye aquí.

## 8. Constraints que vinculan a todas las tareas

Los tres protegen la misma propiedad: que una decisión de hoy no destruya información que mañana
sería interpretable.

| # | Constraint |
|---|---|
| **V1** | **No se añade ninguna validación nueva al esquema HTTP de ingesta.** Cada regla ahí habrá que arrancarla cuando la definición del lead sea por organización, y mientras tanto descarta datos en silencio. La del formato de correo se retira en esta fase por ese motivo |
| **V2** | **El payload se guarda tal como llega, sin normalizar.** Los campos que hoy no significan nada son los que una organización futura declarará suyos |
| **V3** | **El rechazo no es terminal.** Un registro rechazado debe poder reinterpretarse cuando cambie la configuración, sin reenviar nada. El modelo ya lo cumple desde F2b: la promoción acepta registros rechazados |

V1 es de la misma familia que el constraint C8 de F2b —*«no añadir ninguna exigencia de
contactabilidad»*—, que ya evitó una vez que se sustituyera una restricción por otra equivalente.

## 9. Criterios de aceptación

| # | Criterio |
|---|---|
| 1 | La ingesta individual responde `202` con un `job_id`, y consultando ese job se llega al lead |
| 2 | Una carga masiva responde `202` antes de parsear, y al terminar el job tiene `total_items` y contadores correctos |
| 3 | Un payload que el dominio no puede interpretar deja su registro `REJECTED` con el detalle por campo, y el job `COMPLETED` con `failed ≥ 1` |
| 4 | Un job interrumpido queda visible en `PROCESSING` y `reprocess` lo lleva a término sin duplicar leads |
| 5 | Ningún fallo durante el procesamiento borra el registro creado en la recepción |
| 6 | Suite en verde sin banderas, guardián 4/4, `pytest -m unit` sin variables de entorno |

## 10. Coste asumido

Cambiar `201` por `202` rompe el contrato de la ingesta. Afecta a **7 ficheros de pruebas de extremo a
extremo** y al harness de negocio; `test_lead_lifecycle_api.py` concentra 21 aserciones que dependen
del lead ya procesado.

Se comprobó que `TestClient` **ejecuta el trabajo de fondo antes de devolver el control**, así que las
pruebas necesitan una petición más, no sondeo ni esperas. Sólo `verify-e2e.sh`, que habla HTTP real
contra el contenedor, necesita sondear.

Se acepta el coste: mantener `201` obligaría a que la respuesta afirme algo que todavía no es cierto,
que es exactamente el defecto que la fase corrige.
