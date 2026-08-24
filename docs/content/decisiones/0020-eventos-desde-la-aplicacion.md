# ADR-0020 · Los eventos se construyen en la aplicación

| | |
|---|---|
| **Estado** | Sustituida por [ADR-0024](0024-el-contrato-de-salida-se-construye-una-vez.md) |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · Aplicación |

## Contexto

El modelo teórico de eventos de dominio dice que es la **entidad** la que emite un evento cuando le
ocurre algo, no el caso de uso que la manipula. Hasta ahora el único evento existente se fabricaba a
mano dentro de un caso de uso. Al añadir los primeros manejadores que **consumen** eventos de
verdad, se planteó si aprovechar el cambio para mover también la emisión a las entidades.

## Decisión

Los eventos se siguen construyendo dentro de los casos de uso, no en las entidades. Se respeta la
propiedad que sí importa para quien consume —los eventos se publican después del `commit` de la
transacción, nunca antes—, pero de dónde nace el objeto evento no cambia.

Es una decisión **revisable**, no una convicción de diseño: se reconsiderará cuando existan más
manejadores consumiendo eventos y el coste de fabricarlos a mano en cada caso de uso empiece a
notarse frente al de mover la emisión a las entidades.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Mover la emisión de eventos a las entidades ahora, junto con los primeros manejadores que los consumen | Mezclar una refactorización de patrón —que no cambia ningún comportamiento observable— con la primera vez que algo consume eventos de verdad haría imposible saber cuál de los dos cambios rompió algo si algo fallara |
| Mantener la fabricación en el caso de uso indefinidamente, sin plantear revisarlo | Cierra la puerta a una refactorización con argumento real —la entidad es quien mejor conoce cuándo ocurrió el suceso que el evento describe—; se prefiere dejarlo escrito como decisión abierta en vez de como asunto cerrado |

## Consecuencias

**Fácil:** separar los dos cambios —consumir eventos por primera vez, y de dónde nacen— permite
atribuir sin ambigüedad cualquier fallo a uno de los dos. Un evento nuevo hoy sigue el patrón ya
conocido: se construye y se publica desde el caso de uso, después del `commit`.

**Difícil:** el caso de uso conoce detalles de qué evento fabricar y cuándo, una responsabilidad
que en el modelo teórico pertenecería a la entidad. Cuantos más eventos y manejadores se añadan sin
revisar esto, más se acumula esa responsabilidad fuera de donde el modelo dice que debería estar.

## Ver también

- [ADR-0024 · El contrato de salida se construye una vez](0024-el-contrato-de-salida-se-construye-una-vez.md)
- [ADR-0016 · Sólo eventos con consumidor](0016-solo-eventos-con-consumidor.md)
- [Notificaciones](../modulos/notificaciones.md)
