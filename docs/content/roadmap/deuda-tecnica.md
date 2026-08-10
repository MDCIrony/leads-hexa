# Deuda técnica

Puntos ya construidos que funcionan hoy, pero que cuestan mantener o arriesgan un fallo si crece
el uso. A diferencia de la sección anterior, aquí no falta una decisión de producto: falta tiempo
de ingeniería.

## Los diagramas quedaron desfasados

Los tres diagramas de arquitectura del repositorio dibujan un sistema anterior al actual: les
faltan piezas centrales del modelo de dominio y el diagrama de flujo de un lead lo muestra en una
sola etapa, cuando hoy son tres.

**Qué cuesta:** regenerarlos contra el modelo actual. No es trabajo de investigación, es
transcripción cuidadosa.

**Riesgo de no hacerlo:** son material de clase. Un diagrama desactualizado no informa menos que
ningún diagrama: informa mal, con la autoridad visual de un diagrama, y quien lo lea confiará en
una estructura que ya no existe.

## Falta un test de contrato de serialización

Las pruebas automáticas comprueban sobre todo códigos de estado HTTP y qué queda guardado, casi
nunca el cuerpo completo de una respuesta. Eso ha dejado pasar el mismo defecto varias veces: un
campo nuevo llega hasta el borde de la API y el adaptador de salida lo descarta sin que ningún
test lo note.

| Campo que se perdió en la respuesta | Cómo se detectó |
|---|---|
| El correo del lead | Se serializaba como la cadena de texto `"None"` |
| El identificador del origen | Estaba en el diseño; la respuesta lo omitía |
| El identificador del registro de entrada | Mismo patrón, en otra respuesta |
| El motivo de descalificación | Ausente del detalle del lead hasta que una prueba lo necesitó |

**Qué cuesta:** un test que compare el cuerpo entero de una petición `GET` contra lo que se envió
a crear el recurso, en vez de comprobar sólo el código de estado.

**Riesgo de no hacerlo:** el patrón ya se repitió cuatro veces con síntomas distintos. Sin ese
test, el próximo campo que un adaptador descarte lo va a encontrar quien construya la interfaz —o
quien la use—, no la suite.

## Una conexión de arranque se comparte entre hilos sin sincronización

Al arrancar, el proceso abre una conexión de base de datos en modo autocommit que vive mientras
dura el proceso, y la usa el manejador de eventos de webhooks salientes para leer configuración.
Esa conexión se comparte entre todas las peticiones que atiende el servidor, sin ningún mecanismo
que serialice el acceso concurrente.

**Qué cuesta:** que ese manejador pida su conexión al mismo fondo de conexiones que usa el resto
de la aplicación, en vez de abrir la suya propia de por vida.

**Riesgo de no hacerlo:** una conexión de psycopg no está pensada para que varios hilos operen
cursores sobre ella a la vez. Con tráfico bajo no se nota; con tráfico concurrente real, dos
peticiones que caen en el mismo instante pueden interferirse entre sí de formas difíciles de
reproducir.

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

## El documento de diseño maestro sigue marcado como propuesta

El documento de diseño de referencia se sigue titulando "propuesto, pendiente de revisión", con la
mayor parte de sus fases ya cerradas y verificadas contra el sistema real.

**Qué cuesta:** actualizar su encabezado cuando se dé por adoptado.

**Riesgo de no hacerlo:** ninguno funcional. Es una inconsistencia menor entre lo que el
documento dice de sí mismo y lo que demuestra el resto de esta documentación.
