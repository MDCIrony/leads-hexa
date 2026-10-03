# Deuda técnica

Puntos ya construidos que funcionan hoy, pero que cuestan mantener o arriesgan un fallo si crece
el uso. A diferencia de la sección anterior, aquí no falta una decisión de producto: falta tiempo
de ingeniería.

## Cada lead de un lote recarga las reglas de su organización

Al procesar una carga de fichero, cada fila dispara sus propias consultas para traer las reglas de
descalificación, de puntuación y de asignación de la organización, en vez de traerlas una sola vez
para todo el lote. Un fichero de mil filas multiplica esas consultas por mil.

**Qué cuesta:** cargar las reglas una vez al empezar a procesar el lote y pasarlas a cada lead,
en vez de que cada uno las pida por su cuenta.

**Riesgo de no hacerlo:** con los volúmenes de una carga de fichero real, el tiempo de
procesamiento crece con el número de filas más de lo que debería, y la base de datos recibe una
carga de consultas repetidas e idénticas.

## El motor de puntuación muta el lead en vez de sólo describirlo

`ScoringEngine.evaluate` no se limita a calcular el desglose de puntuación: dentro del mismo
bucle, aplica cada delta directamente sobre el lead que recibe. El caso de uso que lo llama, ya de
vuelta, vuelve a tocar el lead para asignarle el desglose. El efecto de la puntuación queda
repartido entre dos sitios para lo que conceptualmente es una sola operación.

**Qué cuesta:** que el motor devuelva sólo el desglose, sin tocar el lead, y que aplicarlo sea
responsabilidad de quien lo llama.

**Riesgo de no hacerlo:** un motor con efecto de lado es más difícil de probar de forma aislada y
más difícil de reutilizar —por ejemplo, para simular una puntuación sin comprometerla— porque
calcular ya implica mutar.

## Las rutas de leads están repartidas entre dos prefijos

Dar de alta un lead vive bajo el prefijo de ingesta; consultarlo, asignarlo o descartarlo vive
bajo el prefijo de leads. Quien busca "los endpoints de leads" esperaría razonablemente
encontrarlos juntos.

No es un error: la separación entre recibir y consultar es deliberada y responde a que son dos
fases con responsabilidades distintas. Es fricción de descubrimiento, no un defecto de
comportamiento.

**Qué cuesta:** revisar el agrupado de rutas cuando se publique una versión de la API pensada para
consumo externo, no sólo para el frontend propio.

**Riesgo de no hacerlo:** ninguno funcional mientras el único consumidor sea la interfaz que se
construye a la vez que la API. El coste aparece si un tercero integra directamente contra ella.
