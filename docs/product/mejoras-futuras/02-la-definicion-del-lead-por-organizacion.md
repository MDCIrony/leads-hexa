# La definición del lead, por organización

**Estado:** fuera del alcance del MVP
**Qué desbloquea:** que cada organización decida qué campos tiene un lead suyo y qué se exige de cada
uno, en vez de heredar una definición única fijada por la plataforma.

---

## El problema

Hoy la plataforma decide qué es un lead. Tiene nombre, apellidos, empresa, presupuesto, sector,
teléfono y correo; unos campos son obligatorios y otros no; y esa decisión es igual para todos.

Funciona mientras todos los clientes se parezcan. Deja de funcionar en cuanto no lo hacen:

- Una consultora que vende proyectos necesita **presupuesto**; una academia que capta alumnos no
  tiene ese concepto, y ponerle un número inventado es peor que no tenerlo.
- Una inmobiliaria necesita **zona** y **tipo de inmueble**, campos que aquí no existen.
- Una organización considera que un lead sin empresa no sirve; otra trabaja sólo con particulares.

Cuando el modelo no encaja, el cliente hace lo único que puede: mete la información donde quepa.
La zona acaba escrita dentro del sector, el tipo de inmueble dentro del nombre de la empresa. La
plataforma queda técnicamente correcta y comercialmente inútil, porque **ninguna regla puede
aprovechar un dato escondido en un campo que significa otra cosa**.

## Lo que cambia si cada organización define su lead

**La validez deja de ser una propiedad del envío.** Hoy un envío es válido o no lo es, y punto. Con
definición propia por organización, el mismo envío puede ser perfectamente válido para una e
inválido para otra. Y puede ser inválido hoy para una organización y válido mañana, porque cambió
su definición o corrigió cómo traduce los datos de su formulario.

Esto tiene una consecuencia práctica grande: **rechazar algo en el momento de recibirlo es tomar una
decisión permanente con información temporal**. Lo que hoy no encaja puede encajar la semana que
viene sin que el emisor haya cambiado nada.

Por eso todo lo que llega debe guardarse tal como llegó, sin transformarlo, y por eso un envío
rechazado tiene que poder reinterpretarse más tarde sin pedirle a nadie que lo mande otra vez. Esas
dos condiciones el MVP ya las cumple, y conviene no perderlas.

## Lo que se gana

- **El cliente configura su realidad** en vez de adaptarse a la de la plataforma.
- **Las reglas ganan alcance**: se puede puntuar o repartir por zona, por tipo de producto o por
  cualquier campo que la organización haya declarado suyo.
- **Deja de haber datos escondidos.** Cada dato vive en el campo que le corresponde y es
  aprovechable.
- **Las integraciones dejan de romperse por forma.** Si un origen externo manda un campo que la
  organización no había declarado, se guarda igual y se decide después qué hacer con él.

## Qué hay que decidir antes de construirlo

Ninguna de estas es una decisión de programación. Todas son de producto, y sin ellas la
funcionalidad no se puede empezar.

**1. Qué es un lead como mínimo.** Si absolutamente todo es configurable, la plataforma deja de saber
qué está gestionando: no podría ni listar leads con sentido ni ofrecer reglas por defecto. Hace falta
un núcleo pequeño e innegociable —probablemente sólo una forma de nombrar a la persona— y todo lo
demás declarable. Dónde se traza esa línea es la decisión más importante y la más difícil de
cambiar después.

**2. Qué pasa con lo ya capturado cuando la definición cambia.** Una organización lleva seis meses
recibiendo leads y decide que la zona pasa a ser obligatoria. ¿Los leads anteriores quedan
incompletos? ¿Se marcan para revisión? ¿Se ignoran? Cada respuesta lleva a un producto distinto.

**3. Qué ve el gestor.** Definir campos exige una pantalla de configuración con tipos, obligatoriedad
y validaciones. Esa pantalla es fácil de hacer mala: demasiado libre y nadie sabe usarla, demasiado
guiada y no cubre los casos que la justifican.

**4. Cómo se relacionan las reglas con los campos declarados.** Hoy las reglas nombran campos que
existen siempre. Con campos por organización, una regla puede quedarse huérfana si se borra el campo
que miraba. Hay que decidir si eso se impide, se avisa o se deja pasar.

**5. Qué se le promete a quien envía.** Si la plataforma acepta todo y valida después, el formulario
que envía no puede seguir esperando una respuesta inmediata de «esto está bien». Cambia el contrato
con las integraciones, no sólo la pantalla.

## Por qué no entra ahora

Cumple las tres condiciones de entrada de esta carpeta:

**Aporta valor real**: es la diferencia entre servir a un sector y servir a varios.

**No es necesaria para lo que el MVP demuestra.** El MVP enseña separación de responsabilidades,
enrutamiento por reglas y aislamiento entre organizaciones. Todo eso se demuestra igual de bien con
una definición fija, y con una configurable se demostraría peor: la mitad del código pasaría a ser
maquinaria de configuración y taparía lo que se quiere enseñar.

**Está bloqueada por decisiones que no son de programación**: las cinco de arriba, y la primera
—dónde está el mínimo innegociable— es una decisión de producto que condiciona todo lo demás.

## Relación con lo que ya existe

Dos piezas del MVP apuntan hacia aquí y conviene no desmontarlas:

- Cada lead puede llevar **atributos adicionales** además de sus campos fijos. Es la rendija por la
  que hoy entra lo que no cabe.
- Cada origen guarda **cómo traducir** lo que recibe a los campos de la plataforma. Hoy sólo cambia
  nombres; es el sitio natural donde mañana viviría la definición completa.

Y una consecuencia inmediata para el MVP, que no cuesta nada respetar: **no conviene añadir
exigencias nuevas a lo que se acepta al recibir**. Cada una habrá que quitarla cuando la definición
sea de cada organización, y mientras tanto descarta información sin dejar constancia. Es el mismo
razonamiento por el que al hacer el correo opcional se decidió no sustituirlo por ninguna otra
exigencia.

## Relación con otras mejoras

[La identidad del contacto](01-identidad-del-contacto.md) tiene el mismo fondo: quién decide qué
significa «el mismo lead» es la organización, no la plataforma. Las dos son la misma idea aplicada a
cosas distintas —qué campos tiene un lead, y qué campos lo identifican— y probablemente compartan la
pantalla de configuración.
