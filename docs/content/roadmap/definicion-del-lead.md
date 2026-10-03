# La definición del lead

Que cada organización decida qué campos tiene un lead suyo y qué se exige de cada uno, en vez de
heredar una definición única fijada por la plataforma. Fuera de alcance por ahora.

## El problema

Hoy la plataforma decide qué es un lead. Tiene nombre, apellidos, empresa, presupuesto, sector,
teléfono y correo; unos campos son obligatorios y otros no; y esa decisión es igual para todos.

Funciona mientras los clientes se parezcan entre sí. Deja de funcionar en cuanto no lo hacen:

- Una consultora que vende proyectos necesita presupuesto; una academia que capta alumnos no tiene
  ese concepto, y ponerle un número inventado es peor que no tenerlo.
- Una inmobiliaria necesita zona y tipo de inmueble, campos que hoy no existen.
- Una organización considera que un lead sin empresa no sirve; otra trabaja sólo con particulares.

Cuando el modelo no encaja, el cliente hace lo único que puede: mete la información donde quepa.
La zona acaba escrita dentro del sector, el tipo de inmueble dentro del nombre de la empresa. La
plataforma queda técnicamente correcta y comercialmente inútil, porque ninguna regla puede
aprovechar un dato escondido en un campo que significa otra cosa.

## Lo que cambiaría si cada organización define su lead

La validez dejaría de ser una propiedad del envío. Hoy un envío es válido o no lo es, y punto. Con
una definición propia por organización, el mismo envío podría ser válido para una e inválido para
otra, e inválido hoy para una organización y válido mañana, porque cambió su definición o corrigió
cómo traduce los datos de su formulario.

Esto tiene una consecuencia grande: rechazar algo en el momento de recibirlo sería tomar una
decisión permanente con información temporal. Lo que hoy no encaja puede encajar la semana que
viene sin que quien lo envía haya cambiado nada. Por eso todo lo que llega debe seguir
guardándose tal como llegó, sin transformarlo, y un envío rechazado tiene que poder
reinterpretarse más tarde sin pedirle a nadie que lo mande otra vez. Esas dos propiedades ya las
tiene la plataforma hoy, y conviene no perderlas al construir esto.

## Lo que se ganaría

- **El cliente configura su realidad** en vez de adaptarse a la de la plataforma.
- **Las reglas ganan alcance**: se podría puntuar o repartir por zona, por tipo de producto o por
  cualquier campo que la organización haya declarado suyo.
- **Dejarían de existir datos escondidos.** Cada dato viviría en el campo que le corresponde y
  sería aprovechable.
- **Las integraciones dejarían de romperse por forma.** Si un origen externo manda un campo que la
  organización no había declarado, se guardaría igual y se decidiría después qué hacer con él.

## Por qué esto hace desaparecer el `422` que hoy pierde payloads

El correo es hoy el único campo del formulario de ingesta sin validación de forma en el borde: se
dejó pasar tal cual a propósito, para que un correo mal escrito llegue al dominio y se quede en la
bandeja de revisión, en vez de morir como un rechazo que no deja rastro. Nombre, apellidos,
empresa, sector y presupuesto siguen declarados con un tipo fijo y obligatorio en ese mismo borde:
si el presupuesto llega como texto en lugar de número, o falta cualquiera de esos campos, la
petición se rechaza antes de que el servicio de ingesta llegue a ejecutarse, y ese payload no se
guarda en ninguna parte.

No es un descuido que quedó a medias: es que el esquema de entrada se declara de forma estática y
no puede variar por organización, así que no hay forma de saber, en el borde, qué campos son
realmente obligatorios para quien envía. Ensancharlo campo a campo sólo movería el problema:
seguiría existiendo un conjunto fijo, y el siguiente campo mal tipado volvería a perderse igual.

Cuando cada organización declare sus propios campos, ese esquema fijo deja de tener sentido: la
validación de forma ya no puede ocurrir en un tipo estático del borde, tiene que ocurrir después,
contra la definición de la organización que corresponda. El `422` no se corrige con una
comprobación más — desaparece porque deja de existir un esquema único contra el que fallar antes
de guardar. Es la misma clase de inversión que ya resolvió el caso del correo, aplicada al resto
de los campos.

## Qué hay que decidir antes de construirlo

Ninguna de estas es una decisión de programación. Todas son de producto, y sin ellas la
funcionalidad no se puede empezar.

**1. Qué es un lead como mínimo.** Si absolutamente todo es configurable, la plataforma deja de
saber qué está gestionando: no podría ni listar leads con sentido ni ofrecer reglas por defecto.
Hace falta un núcleo pequeño e innegociable —probablemente sólo una forma de nombrar a la
persona— y todo lo demás declarable. Dónde se traza esa línea es la decisión más importante y la
más difícil de cambiar después.

**2. Qué pasa con lo ya capturado cuando la definición cambia.** Una organización lleva seis meses
recibiendo leads y decide que la zona pasa a ser obligatoria. ¿Los leads anteriores quedan
incompletos? ¿Se marcan para revisión? ¿Se ignoran? Cada respuesta lleva a un producto distinto.

**3. Qué ve el gestor.** Definir campos exige una pantalla de configuración con tipos,
obligatoriedad y validaciones. Esa pantalla es fácil de hacer mal: demasiado libre y nadie sabe
usarla, demasiado guiada y no cubre los casos que la justifican.

**4. Cómo se relacionan las reglas con los campos declarados.** Hoy las reglas nombran campos que
existen siempre. Con campos por organización, una regla puede quedarse huérfana si se borra el
campo que miraba. Hay que decidir si eso se impide, se avisa o se deja pasar.

**5. Qué se le promete a quien envía.** Si la plataforma acepta todo y valida después, el
formulario que envía no puede seguir esperando una respuesta inmediata de "esto está bien". Cambia
el contrato con las integraciones, no sólo la pantalla.

## Por qué no entra ahora

Cumple las tres condiciones que hacen que algo quede fuera a propósito:

**Aporta valor real**: es la diferencia entre servir a un sector y servir a varios.

**No es necesaria para lo que la plataforma demuestra hoy.** El objetivo es enseñar separación de
responsabilidades, enrutamiento por reglas y aislamiento entre organizaciones. Eso se demuestra
igual de bien con una definición fija, y con una configurable se demostraría peor: buena parte del
código pasaría a ser maquinaria de configuración y taparía lo que se quiere enseñar.

**Está bloqueada por decisiones que no son de programación**: las cinco de arriba, y la primera
—dónde está el mínimo innegociable— es una decisión de producto que condiciona todo lo demás.

## Relación con lo que ya existe

Dos piezas ya construidas apuntan hacia aquí y conviene no desmontarlas:

- Cada lead puede llevar atributos adicionales además de sus campos fijos. Es la rendija por la
  que hoy entra lo que no cabe.
- Cada origen guarda cómo traducir lo que recibe a los campos de la plataforma. Hoy sólo cambia
  nombres; es el sitio natural donde mañana viviría la definición completa.

Y una consecuencia inmediata que no cuesta nada respetar mientras tanto: no conviene añadir
exigencias nuevas a lo que se acepta al recibir un lead. Cada una habría que quitarla cuando la
definición pase a ser de cada organización, y mientras tanto descarta información sin dejar
constancia. Es el mismo razonamiento por el que, al hacer el correo opcional, se decidió no
sustituirlo por ninguna otra exigencia.

## Relación con otras mejoras

[La identidad del contacto](identidad-del-contacto.md) tiene el mismo fondo: quién decide qué
significa "el mismo lead" es la organización, no la plataforma. Las dos son la misma idea aplicada
a cosas distintas —qué campos tiene un lead, y qué campos lo identifican— y probablemente
compartan la pantalla de configuración.
