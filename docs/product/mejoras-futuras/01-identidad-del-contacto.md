# Identidad del contacto

**Estado:** fuera del alcance del MVP. Entrega propia, sin fecha.

**En una frase:** reconocer que dos entradas distintas son la misma persona, y que **cada
organización decida por qué campo se reconocen**.

---

## 1. El problema

Un mismo contacto puede entrar **varias veces**. Rellenó el formulario, nadie le llamó, y dos
semanas después volvió a pedir información. O llegó por una campaña de redes y también por el
formulario de la web.

Hoy la plataforma trata cada entrada como un lead nuevo e independiente. No es un error de
programación: es que nunca se le dijo qué significa «el mismo».

En el sector esto se llama **deduplicación** o **resolución de identidad**, y es funcionalidad
estándar en las plataformas comerciales.

## 2. Por qué da valor, más allá de no duplicar filas

Ésta es la parte que suele malinterpretarse. El objetivo no es tener la tabla limpia; es que
aparezca información que hoy no existe en ninguna parte.

| Lo que se gana | Por qué importa |
|---|---|
| **La repetición es señal de intención** | Alguien que vuelve dos veces quiere algo. Un contacto que insiste vale más que uno idéntico que entró una sola vez, y ninguna regla de puntuación puede verlo hoy |
| **Histórico de intentos de contacto** | El asesor sabe que ya se le llamó y no funcionó, en vez de repetir la misma llamada y quemar al contacto |
| **Rescate de descartados** | Un contacto descalificado por falta de datos que **vuelve con teléfono** deja de estarlo. Sin identidad, esa segunda oportunidad se pierde en silencio |
| **Métrica real por canal** | Si el mismo contacto entra por tres campañas, el recuento por canal miente hasta que se deduplican. Se toman decisiones de inversión sobre cifras infladas |

El tercero es el que conecta con lo que el MVP sí construye: la bandeja de descartados existe
precisamente para que un contacto insuficiente no se destruya. La identidad es lo que convierte esa
bandeja en algo más que un archivo muerto.

## 3. La decisión de diseño: el identificador lo elige la organización

Es el punto que cambia respecto al primer planteamiento, y el que define la funcionalidad.

Al principio se trató «¿qué campo es la identidad?» como una decisión **de diseño pendiente**: había
que elegir entre correo, teléfono o documento antes de poder construir nada. Es la respuesta
equivocada, porque cada opción falla de una forma distinta **según el negocio**:

| Identificador | Dónde funciona | Dónde falla |
|---|---|---|
| Correo | Ventas a empresas con contacto individual | Buzones compartidos (`info@`, `ventas@`) colapsan a media empresa en un solo contacto |
| Teléfono | Ventas a particulares | Los números se reasignan. Y una centralita repite el mismo número para todos |
| Documento de identidad | Sector financiero, seguros, educación reglada | Casi nadie lo pide en un formulario de captación, así que estaría vacío la mayor parte del tiempo |

No hay un ganador universal. **La organización sabe cuál sirve en su negocio y la plataforma no.**

Por eso la identidad se configura, igual que se configuran las reglas de puntuación y de reparto: el
gestor elige qué campo —o qué combinación— significa «es la misma persona», y el sistema hace las
asociaciones con ese criterio. Es coherente con el principio que atraviesa todo el diseño, recogido
en [`03 — Dominio y organización`](../03-dominio-y-organizacion.md): lo que cambia de una
organización a otra no se escribe en el código.

Esto tiene una consecuencia práctica: **la funcionalidad incluye una pantalla de configuración**, no
sólo un proceso de comparación. Es parte de por qué es una entrega propia y no un añadido.

## 4. Lo que hay que decidir antes de construirlo

La elección del identificador deja de ser un bloqueo —pasa a ser configuración—, pero quedan dos, y
ninguna es una pregunta de programación.

**Qué hacer con coincidencias parciales.** Mismo teléfono y correo distinto: ¿es la misma persona,
un familiar, o un compañero de trabajo? Las opciones razonables son fusionar automáticamente,
marcarlo como *posible duplicado* para que alguien lo revise, o tratarlos como distintos. Cada una
tiene un coste comercial distinto cuando se equivoca, y probablemente también deba ser configurable.

**Cuánto tiempo se conserva un contacto rechazado.** Es una decisión de protección de datos, no
técnica. Guardar indefinidamente el historial de alguien que nunca llegó a ser cliente tiene
implicaciones legales que dependen de la jurisdicción y del sector.

## 5. Relación con lo que sí construye el MVP

Hay una decisión ya tomada que condiciona esta funcionalidad, y conviene tenerla presente al
retomarla.

**El correo del contacto puede faltar.** Se decidió a propósito: exigirlo destruía leads con nombre,
empresa y sector cuya única falta era no traer correo. El razonamiento completo está en
[`02 — El modelo de decisión`](../02-el-modelo-de-decision.md).

La consecuencia para esta mejora es directa: **un campo que puede estar vacío no puede ser la
identidad por sí solo**. Cuando se construya, el correo podrá ser *uno* de los identificadores
configurables, pero el sistema tendrá que resolver qué hacer cuando el campo elegido no venga en un
contacto concreto. La respuesta más probable es tratarlo como no emparejable en vez de agrupar por
ausencia — porque agrupar todos los contactos sin correo en uno solo sería el peor resultado posible.
