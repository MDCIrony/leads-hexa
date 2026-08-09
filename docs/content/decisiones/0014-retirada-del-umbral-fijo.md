# ADR-0014 · Retirada del umbral fijo

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · Dominio |

## Contexto

Dos cortes de puntuación fijados como valores por defecto en el código decidían, en la práctica, si
un lead entraba al reparto. Nadie los veía ni podía moverlos. El síntoma: una regla de asignación
para leads mediocres no se disparaba nunca, sin ningún mensaje de error, porque estaba detrás de un
umbral que su autor no sabía que existía.

El diseño original planteaba resolverlo con una política de calificación configurable por
organización, como objeto de dominio con sus propios umbrales editables. Al examinarlo de cerca, esa
salida no resolvía el defecto de fondo: seguiría habiendo **dos** cortes independientes para la
misma decisión —el umbral de calificación y la banda más baja de las reglas de asignación—, que
nadie sincroniza y de los que uno seguiría siendo invisible para el gestor.

## Decisión

El umbral desaparece del código sin sustituirse por una política configurable. **La banda más baja
de las reglas de asignación que el propio gestor escribe pasa a ser el único corte de puntuación**
del sistema. La calificación del lead deja de recibir umbrales: se limita a la transición de
«nuevo» a «calificado», y la descalificación pasa por completo a las reglas de la etapa de
viabilidad, que son las que tienen el motivo.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Mantener los umbrales fijos en el código | Es la causa medida del defecto: una regla de reparto puede quedar detrás de una puerta que nadie ve ni puede mover |
| Una política de calificación configurable por organización | No resuelve el defecto de fondo: seguiría habiendo dos cortes de puntuación independientes que nadie sincroniza, sólo que ambos configurables en vez de uno fijo. Añade un concepto nuevo para el gestor sin eliminar la duplicidad |

## Consecuencias

**Fácil:** existe un único lugar donde se decide a partir de qué puntuación un lead entra al
reparto, y lo controla el gestor desde la misma interfaz donde ya define sus reglas de asignación.
Desaparece la franja de puntuación sin veredicto: antes, un lead entre los dos umbrales se quedaba
sin procesar para siempre, indistinguible de uno recién llegado.

**Difícil:** si el gestor no define ninguna regla de asignación, no hay ningún corte —todo lead
calificado queda sin asignar en vez de descalificado—, así que la calidad del reparto depende por
completo de que las reglas estén bien escritas; el sistema ya no tiene un valor por defecto de
respaldo.

## Ver también

- [ADR-0011 · Una gramática de condiciones](0011-gramatica-de-condiciones.md)
- [ADR-0012 · Y dentro, O entre](0012-y-dentro-o-entre.md)
- [Reglas](../modulos/reglas.md)
- [Asignación](../modulos/asignacion.md)
