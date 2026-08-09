# Identidad del contacto

Reconocer que dos entradas distintas son la misma persona, dejando que cada organización decida
por qué campo se reconocen. Fuera de alcance por ahora.

## El problema

Un mismo contacto puede entrar varias veces: rellenó el formulario, nadie le llamó, y dos semanas
después volvió a pedir información. O llegó por una campaña en redes y también por el formulario
de la web.

Hoy la plataforma trata cada entrada como un lead nuevo e independiente. No es un error de
programación: es que nunca se le dijo qué significa "el mismo". En el sector esto se llama
deduplicación o resolución de identidad, y es funcionalidad estándar en las plataformas
comerciales.

## Por qué da valor, más allá de no duplicar filas

El objetivo no es tener la tabla limpia; es que aparezca información que hoy no existe en ninguna
parte.

| Lo que se gana | Por qué importa |
|---|---|
| **La repetición es señal de intención** | Alguien que vuelve dos veces quiere algo. Un contacto que insiste vale más que uno idéntico que entró una sola vez, y ninguna regla de puntuación puede verlo hoy |
| **Histórico de intentos de contacto** | El asesor sabe que ya se le llamó y no funcionó, en vez de repetir la misma llamada y quemar al contacto |
| **Rescate de descartados** | Un contacto descalificado por falta de datos que vuelve con teléfono deja de estarlo. Sin identidad, esa segunda oportunidad se pierde en silencio |
| **Métrica real por canal** | Si el mismo contacto entra por varias campañas, el recuento por canal miente hasta que se deduplican. Se toman decisiones de inversión sobre cifras infladas |

El tercero es el que conecta con lo que la plataforma ya construye: la bandeja de rechazados
existe precisamente para que un contacto insuficiente no se destruya. La identidad es lo que
convertiría esa bandeja en algo más que un archivo muerto.

## La decisión de diseño: el identificador lo elige la organización

Tratar "¿qué campo es la identidad?" como una decisión de diseño pendiente —elegir entre correo,
teléfono o documento antes de poder construir nada— es la respuesta equivocada, porque cada opción
falla de una forma distinta según el negocio:

| Identificador | Dónde funciona | Dónde falla |
|---|---|---|
| Correo | Ventas a empresas con contacto individual | Buzones compartidos (`info@`, `ventas@`) colapsan a media empresa en un solo contacto |
| Teléfono | Ventas a particulares | Los números se reasignan, y una centralita repite el mismo número para todos |
| Documento de identidad | Sector financiero, seguros, educación reglada | Casi nadie lo pide en un formulario de captación, así que estaría vacío la mayor parte del tiempo |

No hay un ganador universal. La organización sabe cuál sirve en su negocio y la plataforma no. Por
eso la identidad debería configurarse, igual que se configuran las reglas de puntuación y de
reparto: el gestor elegiría qué campo —o qué combinación— significa "es la misma persona", y el
sistema haría las asociaciones con ese criterio. Es coherente con el principio que atraviesa todo
el diseño: lo que cambia de una organización a otra no se escribe en el código. Ver
[Qué decide cada organización](../vision/dominio-y-organizacion.md).

Esto tiene una consecuencia práctica: la funcionalidad incluiría una pantalla de configuración, no
sólo un proceso de comparación en segundo plano.

## Lo que hay que decidir antes de construirlo

La elección del identificador deja de ser un bloqueo —pasa a ser configuración—, pero quedan dos
preguntas, y ninguna es de programación.

**Qué hacer con coincidencias parciales.** Mismo teléfono y correo distinto: ¿es la misma persona,
un familiar, o un compañero de trabajo? Las opciones razonables son fusionar automáticamente,
marcarlo como posible duplicado para que alguien lo revise, o tratarlos como distintos. Cada una
tiene un coste comercial distinto cuando se equivoca, y probablemente también deba ser
configurable.

**Cuánto tiempo se conserva un contacto rechazado.** Es una decisión de protección de datos, no
técnica. Guardar indefinidamente el historial de alguien que nunca llegó a ser cliente tiene
implicaciones legales que dependen de la jurisdicción y del sector.

## Relación con lo que ya existe

Una decisión ya tomada condiciona esta funcionalidad, y conviene tenerla presente al retomarla: el
correo del contacto puede faltar. Se decidió a propósito, porque exigirlo destruía leads con
nombre, empresa y sector cuya única falta era no traer correo. Ver
[El modelo de decisión](../vision/modelo-de-decision.md).

La consecuencia para esta mejora es directa: un campo que puede estar vacío no puede ser la
identidad por sí solo. Cuando se construya, el correo podrá ser uno de los identificadores
configurables, pero el sistema tendrá que resolver qué hacer cuando el campo elegido no venga en
un contacto concreto. La respuesta más probable es tratarlo como no emparejable en vez de agrupar
por ausencia, porque agrupar todos los contactos sin correo en uno solo sería el peor resultado
posible.

## Relación con otras mejoras

[La definición del lead](definicion-del-lead.md) tiene el mismo fondo: quién decide qué significa
"el mismo lead" es la organización, no la plataforma. Las dos son la misma idea aplicada a cosas
distintas —qué campos tiene un lead, y qué campos lo identifican— y probablemente compartan la
pantalla de configuración.
