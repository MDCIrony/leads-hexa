# Glosario

Los términos del dominio de Lead Router, en orden alfabético. Sirve para leer el resto de la
documentación sin tropezar con un nombre que no se ha presentado todavía.

### Asesor

Usuario con rol `AGENT`. Ve únicamente los leads que se le asignaron a él, con su detalle
completo. Recibe una notificación cada vez que se le asigna un lead nuevo.

### Bandeja de entrada

Vista donde el gestor revisa los registros de entrada que no se pudieron interpretar. Desde ahí
corrige el payload y reintenta la promoción a lead, o lo descarta.

### Capacidad

Número máximo de leads activos que puede tener a la vez cada asesor de un grupo de venta. Sin
límite fijado, un asesor puede recibir cualquier cantidad; al llegar al tope, queda excluido de
los candidatos hasta que se libere alguno de sus leads.

### Carga derivada

La cantidad de leads activos de un asesor no se guarda como un número aparte: se calcula contando
sus leads asignados en el momento de repartir. Elimina el riesgo de que ese contador se
desincronice del dato real.

### Condición

Comparación entre un campo del lead y un valor de referencia, con un operador: igual, mayor que,
contiene, está vacío, y algunos más. Es la pieza mínima con la que se construyen las reglas de
descalificación, de puntuación y de asignación.

### Desglose de puntuación

El detalle de qué reglas se cumplieron para un lead concreto y cuántos puntos aportó cada una. Se
guarda junto al lead, así que sigue explicándose aunque la regla que lo produjo se edite o se
borre después.

### Gestor

Usuario con rol `MANAGER`. Administra su organización: asesores, grupos, reglas y fuentes de
leads. Ve todos los leads de su organización y resuelve a mano los que el sistema no pudo
procesar.

### Grupo de venta

Conjunto de asesores que comparten una política de asignación: la misma estrategia de reparto por
defecto y el mismo límite de capacidad. Es el destino habitual de una regla de asignación.

### Lead

Contacto que ha mostrado interés y todavía no está calificado. Existe si sus datos son coherentes,
no si son comercialmente útiles: un lead sin ninguna vía de contacto se crea igual, y una regla de
descalificación lo marca con su motivo.

### Notificación

Aviso interno que recibe un asesor cuando se le asigna un lead, o un gestor cuando un lead se
queda sin asignar o un registro de entrada falla la validación. Se acumulan con un contador de no
leídas.

### Organización

Cliente de la plataforma. Todo lo que un lead, un asesor o una regla puede ver o afectar queda
dentro de su propia organización: nada cruza esa frontera, ni siquiera para el administrador de la
plataforma.

### Origen

La fuente por la que entra un lead: un formulario, una carga de fichero o, más adelante, una
integración externa. Cada origen guarda cómo traducir los campos que envía a los campos que la
plataforma entiende.

### Registro de entrada

Todo lo que llega a la plataforma, guardado tal como llegó, antes de intentar interpretarlo. Si el
payload no se puede convertir en un lead válido, el registro queda visible con el detalle de qué
falló, en vez de perderse.

### Regla de asignación

Decide a qué grupo o a qué asesores concretos se entrega un lead calificado, dentro de un tramo de
puntuación y, si hace falta, condicionado por atributos del lead como el canal o la zona.

### Regla de descalificación

Condición, o conjunto de condiciones, que si se cumple marca un lead como no trabajable, con un
motivo legible. Corta el flujo antes de puntuar: no tiene sentido valorar ni repartir un lead que
nadie puede contactar.

### Regla de puntuación

Suma o resta puntos a un lead cuando se cumplen sus condiciones. La puntuación resultante es lo
que decide, más adelante, qué regla de asignación aplica.

### Trabajo de ingesta

Agrupa una operación de entrada completa, sea un único lead o un fichero entero, y lleva la cuenta
de cuántos registros trajo, cuántos se promovieron a lead y cuántos se rechazaron. Permite
consultar el resultado de una carga después de cerrar la pantalla, y relanzar la que quedó
interrumpida.
