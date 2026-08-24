# ADR-0024 · El contrato de salida se construye una vez

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-24 |
| **Ámbito** | Backend · Dominio · Aplicación |

Sustituye a [ADR-0020 · Los eventos se construyen en la aplicación](0020-eventos-desde-la-aplicacion.md).

## Contexto

El [ADR-0020](0020-eventos-desde-la-aplicacion.md) fijó que los eventos se fabrican dentro de los
casos de uso y no en las entidades, y se declaró **revisable** con estas palabras: *«se reconsiderará
cuando existan más manejadores consumiendo eventos y el coste de fabricarlos a mano en cada caso de
uso empiece a notarse»*.

Ese momento llegó. `LeadProcessedEvent` dejó de ser un aviso de cuatro campos para convertirse en el
contrato que el cliente recibe: nombre, empresa, sector, presupuesto, atributos propios, desglose de
puntuación, asesor y fechas —diecisiete campos—. Y lo publican dos casos de uso: la ingesta, cuando
el lead termina de procesarse, y la asignación manual, cuando un gestor le pone dueño después.

Dos sitios construyendo diecisiete campos a mano divergen en el primer campo que alguien añada en
uno solo. El consumidor recibiría entonces el mismo evento con dos formas distintas según qué lo
provocó, que es la clase de error que no falla en ninguna prueba y aparece en producción.

## Decisión

`LeadProcessedEvent.of(lead)` construye el contrato desde la entidad que describe, y es el único
constructor que la producción usa. El caso de uso decide **cuándo** publicar; el evento sabe **qué**
lleva dentro.

Los eventos **internos** —`LeadAssigned`, `LeadReassigned`, `LeadLeftUnassigned`, `IntakeRejected`—
se siguen construyendo en el caso de uso. Son de tres campos, su forma no es un contrato público y
nadie fuera del proceso los ve: no pagan el coste que justifica el cambio.

Lo que el 0020 protegía sigue en pie: los eventos se publican **después** del `commit` de la
transacción, nunca antes. Esta decisión cambia de dónde nace el objeto, no cuándo sale.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Que cada caso de uso construya el contrato completo | Es el defecto que motiva el cambio: diecisiete campos en dos sitios que deben coincidir sin nada que lo verifique |
| Una función auxiliar en la capa de aplicación | La aplicación pasaría a conocer la forma del contrato de salida, que es justo lo que se quiere encapsular; y el dominio ya tiene ambas piezas —la entidad y el evento— sin cruzar ninguna capa |
| Mover **todos** los eventos a las entidades, por coherencia con el modelo teórico | Coherencia sin beneficio: los internos son baratos de fabricar y su forma no la ve nadie fuera. Se paga complejidad donde no hay problema que resolver |

## Consecuencias

**Fácil:** un campo nuevo en el contrato se añade en un sitio y los dos publicadores lo obtienen. La
regla de qué se copia y qué se referencia —los atributos propios se copian, no se comparten— vive
junto al contrato en vez de repetirse en cada llamador.

**Difícil:** `LeadProcessedEvent` conoce la entidad `Lead`. Ambos viven en el dominio, así que no
cruza ninguna capa ni rompe el guardián, pero el evento deja de ser una estructura de datos inerte y
pasa a depender de la forma de la entidad: renombrar un campo de `Lead` obliga a tocarlo. Es el
precio de tener un solo sitio donde el contrato se define.

## Ver también

- [ADR-0020 · Los eventos se construyen en la aplicación](0020-eventos-desde-la-aplicacion.md)
- [ADR-0023 · Los eventos del canal de salida](0023-eventos-del-canal-de-salida.md)
