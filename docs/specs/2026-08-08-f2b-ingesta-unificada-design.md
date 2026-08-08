# F2b — Ingesta unificada: diseño

**Estado:** implementado. Sucede a F2a, cerrada y verificada.

**Objetivo en una frase:** que nada de lo que entra se pierda, y que nadie ingeste sin credencial.

**Documento maestro:** [spec del MVP](2026-08-07-lead-router-mvp-design.md). Este desarrolla §6.6,
§6.7, §6.8 y §8. La justificación de negocio está en
[`docs/product/02`](../product/02-el-modelo-de-decision.md).

---

## 1. El problema

Hoy la ingesta tiene tres defectos que se refuerzan entre sí:

| Defecto | Consecuencia |
|---|---|
| **No exige autenticación** | `POST /intake/{tenant_id}/leads/ingest` responde `201` sin token, y la organización sale de la URL. Cualquiera inyecta leads en cualquier organización |
| **Lo que no valida, se pierde** | Un payload con correo mal formado devuelve `FAILED` y **no persiste nada**. No hay traza, no hay bandeja, no hay recuento |
| **Hay dos caminos distintos** | El formulario individual y la carga masiva tienen recorridos separados, con validación y reglas propias que ya divergen |

El segundo es el más caro, y no por los datos: el gestor **no puede saber cuántos leads está
perdiendo**. Un mapeo de columnas mal configurado en un CSV descarta en silencio la mitad de una
campaña, y el síntoma aparece semanas después como "vinieron menos leads de los que pagué".

## 2. Alcance

**Entra:**

1. `LeadSource` — el origen deja de ser implícito y pasa a ser una entidad del gestor
2. `IntakeRecord` + `IntakeError` — todo payload que llega se persiste, valide o no
3. Pipeline unificado — un solo recorrido para formulario, carga masiva y futuras fuentes
4. **Correo opcional en el lead** — la contactabilidad deja de ser invariante
5. Cierre de la ingesta sin autenticar
6. Retirada de `LeadStatus.FAILED`
7. Migración `005`

**No entra:** las reglas de descalificación que aprovechan el correo opcional (F2c), la
deduplicación por identidad ([fuera del alcance del MVP](../product/mejoras-futuras/01-identidad-del-contacto.md)),
y el adaptador de webhook entrante (F3b).

## 3. Por qué el correo opcional cae en esta fase

Es el punto donde F2b cambió de alcance respecto al plan original, y conviene dejar el razonamiento
escrito.

*«Sin correo no vale la pena»* es una **regla de la organización**, no un invariante: hay quien
contacta por teléfono, por mensajería o por redes profesionales. Escrita como invariante produce el
peor resultado posible — el lead **se destruye** en vez de quedar marcado.

Tres razones para hacerlo aquí y no en F2c:

1. **F2b ya reescribe el pipeline de ingesta**, que es exactamente el código que hoy captura el
   correo inválido y devuelve `FAILED`. Hacerlo aparte significa tocar los mismos ficheros dos veces.
2. **F2c no puede funcionar sin ello.** Su regla de referencia —«sin teléfono y sin correo,
   descartar»— no puede dispararse mientras un lead sin correo no llegue a existir.
3. **La decisión de qué se conserva de lo que entra es el tema de esta fase.** El correo obligatorio
   es un caso particular de lo mismo.

### Lo que cambia y lo que no

| Afirmación | Antes | Después |
|---|---|---|
| Si viene un correo, tiene forma de correo | Invariante | **Invariante** — sin cambios |
| Un lead debe traer correo | Invariante | **Regla de la organización** (se escribe en F2c) |

**Y no se añade ninguna exigencia en su lugar.** Nada de «al menos una vía de contacto»: eso
reproduciría el problema con otro nombre —el lead sin ninguna vía seguiría sin poder crearse— y
dejaría la bandeja de descalificados vacía justo en el caso que la justifica.

### Alcance del cambio

| Capa | Qué toca |
|---|---|
| Dominio | `Lead.email: Optional[EmailAddress]`; la factoría deja de exigirlo |
| Persistencia | `leads.email` es `NOT NULL` → migración; serialización y reconstitución del nulo |
| API | Esquema de ingesta y su validador de formato |
| Carga masiva | Lector de ficheros y su caso de uso |
| Eventos | `LeadProcessedEvent.email` pasa a admitir nulo |

El correo del **asesor** no se toca: ahí sí es obligatorio de verdad, porque es la credencial de
acceso.

### Consecuencia para el futuro

Si el correo puede faltar, **no puede ser la identidad del contacto**. La resolución de identidad
—cuando llegue— necesitará una clave compuesta o un campo distinto, elegido por cada organización.
Queda fuera del alcance de este MVP y está desarrollado en
[`docs/product/mejoras-futuras/01`](../product/mejoras-futuras/01-identidad-del-contacto.md).

## 4. `LeadSource` — el origen como entidad

Ver §6.8 del documento maestro para el modelo completo. Lo que esta fase entrega:

- Al crear una organización se generan **dos fuentes automáticas**: `MANUAL_FORM` y `FILE_UPLOAD`.
  El `field_mapping` de la segunda es el mapeo de columnas del fichero, así que la maquinaria se
  amortiza desde el primer día en vez de ser andamiaje para un futuro que quizá no llega.
- CRUD para el gestor.
- El lead pasa a llevar `source_id` obligatorio.

**Por qué importa para el negocio:** sin origen, la pregunta «¿de dónde vienen mis leads?» no tiene
respuesta, y el eje de reparto por canal que F2c habilita no tendría sobre qué condicionar.

## 5. `IntakeRecord` — nada se pierde

Todo payload que llega se persiste **antes** de intentar interpretarlo.

| Estado | Significado |
|---|---|
| `PENDING` | Recibido, sin procesar |
| `PROMOTED` | Se interpretó y generó un lead |
| `REJECTED` | No se pudo interpretar. Visible para el gestor con el detalle del fallo |
| `DISCARDED` | El gestor decidió no recuperarlo |

`IntakeError` guarda el detalle por campo: qué campo, qué se recibió, qué falló.

**La frontera entre `IntakeRecord` y `Lead`** es la distinción de la §6.5 del maestro:

- **No se puede interpretar** (falta el nombre, el presupuesto no es un número) → se queda en
  `IntakeRecord` como `REJECTED`
- **Se interpreta pero es comercialmente inútil** (sin ninguna vía de contacto) → **se convierte en
  `Lead`**, y en F2c una regla lo descalifica

Esa segunda categoría es la que hoy se pierde, y la que da valor a la bandeja: un lead sin teléfono
pero con nombre, empresa y sector **es información**, no basura.

## 6. Pipeline unificado

Un solo recorrido, tres entradas:

```
formulario ─┐
    CSV ────┼──→ IntakeRecord (persistido) ──→ interpretar ─┬─ falla ──→ REJECTED
 webhook ───┘                                               │
   (F3b)                                                    └─ ok ──→ Lead ──→ scoring ──→ reparto
```

Elimina la divergencia actual entre el camino individual y el masivo, y deja el punto de extensión
donde F3b engancha el webhook sin tocar el núcleo.

## 7. Cierre de la ingesta sin autenticar

La organización deja de salir de la URL y pasa a derivarse de la credencial, como en todos los demás
endpoints del sistema desde F0.5.

Dos modos, porque el caso de uso es distinto:

| Entrada | Credencial |
|---|---|
| Formulario del gestor y carga masiva | Token del gestor autenticado |
| Fuente externa (F3b) | Secreto de la fuente, verificado por firma. El `source_id` identifica la organización |

El segundo modo se **diseña** aquí y se **implementa** en F3b: definir ahora el contrato evita que
el cierre de autenticación haya que rehacerlo cuando lleguen los webhooks.

## 8. Retirada de `FAILED`

`LeadStatus.FAILED` desaparece. Hoy no se persiste nunca —es un código de respuesta HTTP disfrazado
de estado de dominio, devuelto en un retorno temprano antes de que exista ninguna entidad—, así que
su retirada no requiere migración de datos: no hay ninguna fila con ese valor.

Su papel lo asume `IntakeRecord.REJECTED`, que sí se persiste y sí se puede revisar.

## 9. Migración 005

- `leads.email` deja de ser `NOT NULL`
- `leads.source_id` con clave foránea a `lead_sources`
- Tablas `lead_sources`, `intake_records`, `intake_errors`
- Índices por organización y estado para la bandeja

No hay datos que preservar: las migraciones se aplican sobre base vacía.

## 10. Criterio de aceptación

1. Un payload sin correo genera un lead que **existe** y es visible
2. Un payload ininterpretable queda en la bandeja con el detalle del fallo, y el gestor lo corrige y
   lo promueve
3. Una petición de ingesta sin credencial es rechazada
4. Formulario y carga masiva recorren el mismo pipeline y producen el mismo resultado para el mismo
   dato
5. El gestor responde «¿de dónde vienen mis leads?» desde la interfaz
6. La suite completa en verde sin banderas, guardián de arquitectura 4/4, `pytest -m unit` sin
   variables de entorno
