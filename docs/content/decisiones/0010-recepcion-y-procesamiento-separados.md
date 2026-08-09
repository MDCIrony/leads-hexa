# ADR-0010 · Recepción y procesamiento separados

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · Aplicación |

## Contexto

Recibir un payload de ingesta y procesarlo —puntuarlo, calificarlo, repartirlo— compartían la misma
transacción. Eso dejaba dos formas de que un fallo posterior deshiciera el registro de entrada que
ya se había escrito:

1. La validación de esquema HTTP corta antes de que el servicio se ejecute — el caso que
   [ADR-0009](0009-registrar-antes-de-interpretar.md) cierra.
2. La unidad de trabajo hace *rollback* ante **cualquier** excepción, y el guardado del registro de
   entrada vivía dentro de ese mismo bloque. Un fallo imprevisto después de guardar —en el motor de
   puntuación, en el de reparto— deshacía también el registro, aunque el guardado fuera la primera
   línea del servicio.

El problema de fondo no era de rendimiento: era que **dos responsabilidades distintas compartían una
transacción**, y compartir transacción significa que el *rollback* de una se lleva a la otra.

## Decisión

El recorrido de ingesta se separa en dos fases, cada una con su propia transacción. La **fase de
recepción** crea un trabajo de ingesta y su registro o registros, confirma, y responde
`202 Accepted` con el identificador del trabajo. La **fase de procesamiento** corre en segundo
plano, después de responder: lee los registros que la recepción dejó pendientes, intenta
interpretarlos y los marca como promovidos a lead o rechazados. El servicio de ingesta deja de
**crear** el registro y pasa a **recibirlo** y marcarlo: es la inversión completa de
responsabilidades.

Un ingreso individual es un trabajo con un único elemento, no un camino aparte del de la carga
masiva: hay un solo modelo con uno o con muchos elementos. Los eventos de dominio se publican
**después** del `commit` de cada fase, de modo que un fallo al notificar no deshaga un lead ya
guardado.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Mantener una sola transacción y responder `201` al terminar | Es la causa medida del defecto: cualquier fallo después de guardar el registro lo deshace junto con todo lo demás |
| Introducir una cola externa y un proceso trabajador aparte | El trabajo de fondo del propio framework basta para separar las dos transacciones, que es la propiedad que se necesita; una cola añade infraestructura que este MVP no paga todavía. El modelo de dos fases es compatible con una cola futura sin rediseñarse |
| Guardar sólo al final, cuando se conoce el resultado completo | Es fail-fast con otro nombre: si el procesamiento falla a mitad, no queda ni rastro de que la petición llegó |

## Consecuencias

**Fácil:** ningún fallo durante el procesamiento puede ya borrar la constancia de haber recibido,
porque son dos transacciones distintas por construcción, no por disciplina. Un trabajo interrumpido
queda visible en curso en vez de desaparecer.

**Difícil:** cambiar `201` por `202` rompe el contrato previo de la ingesta —la respuesta ya no
afirma que el lead quedó procesado, sólo que se recibió—, y se acepta el coste porque mantener `201`
obligaría a la respuesta a afirmar algo que todavía no es cierto, que es exactamente el defecto que
esta decisión corrige. El trabajo de fondo corre en el mismo proceso que la API: si el contenedor
cae entre la respuesta y el final del trabajo, el trabajo queda en curso para siempre. No hay
reintento automático; se mitiga haciéndolo **visible y reprocesable a mano** en vez de detectarlo
por antigüedad o ignorarlo. Reprocesar es, deliberadamente, la misma operación que ejecutaría una
cola futura: construirla ahora no es trabajo perdido.

## Ver también

- [ADR-0009 · Registrar antes de interpretar](0009-registrar-antes-de-interpretar.md)
- [Ingesta](../modulos/ingesta.md)
- [Recorrido de un lead](../arquitectura/recorrido-de-un-lead.md)
