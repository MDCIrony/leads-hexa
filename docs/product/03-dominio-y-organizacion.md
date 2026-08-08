# Qué pertenece al dominio y qué a la organización

> **Estado: catálogo vivo.** Enumera las reglas que la plataforma da por ciertas siempre —y que por
> tanto nadie puede cambiar— frente a las que cada organización decide por su cuenta. Se actualiza
> cuando una regla cambia de lado, que es algo que pasa y conviene registrar.
>
> Está escrito en lenguaje de negocio a propósito: si un invariante no se puede enunciar sin hablar
> de código, probablemente no es un invariante. La contraparte técnica vive en
> [`docs/specs/`](../specs/2026-08-07-lead-router-mvp-design.md).

---

## 1. Por qué esta distinción decide el producto

Toda aplicación de negocio contiene dos clases de afirmación, y se parecen mucho por fuera:

- *"Un presupuesto no puede ser negativo"*
- *"Un lead sin teléfono no vale la pena"*

Las dos suenan a validación. Las dos se escriben igual de fácil. Pero **sólo una de ellas es cierta
en cualquier organización, de cualquier sector, en cualquier país**. La otra es una opinión
comercial de un cliente concreto.

Si las tratas igual, pasa una de dos cosas, y las dos son caras:

| Error | Síntoma | Qué acaba ocurriendo |
|---|---|---|
| **Meter una regla dentro del dominio** | El sistema es rígido. Un cliente pide "una excepción para nuestro caso" y **hay que desplegar** para dársela | Ramas por cliente, banderas de configuración disfrazadas, y datos que se pierden porque el modelo los rechazó |
| **Sacar un invariante fuera del dominio** | Aparecen datos incoherentes que nadie sabe de dónde salieron | La misma validación repetida en cinco sitios, y siempre falta uno |

Este documento existe para no cometer ninguno de los dos por accidente.

---

## 2. La prueba

> **¿Puedes imaginar una organización razonable a la que esta afirmación no le aplique?**
>
> Si **sí** → es una **regla de la organización**. Va a la interfaz, la escribe el gestor.
> Si **no** → es un **invariante del dominio**. Va al modelo, y no se negocia.

Aplicada a los dos ejemplos de arriba:

| Afirmación | ¿Alguna organización razonable la rompería? | Veredicto |
|---|---|---|
| "Un presupuesto no puede ser negativo" | No. Un presupuesto negativo no significa nada en ninguna parte | **Invariante** |
| "Un lead sin teléfono no vale la pena" | Sí: una consultora que contacta por LinkedIn, una inmobiliaria que trabaja por WhatsApp | **Regla** |

Una segunda prueba, útil cuando la primera no basta:

> **¿Esta afirmación dice que el dato es coherente, o que el dato es rentable?**
>
> **Coherente** → dominio. **Rentable** → organización.

Un lead sin teléfono es un dato perfectamente coherente: tiene nombre, empresa, sector y momento de
entrada. No es rentable. Son cosas distintas, y sólo la primera le incumbe al modelo.

---

## 3. Lo que la plataforma da por cierto siempre

Estas reglas **no se pueden desactivar ni configurar**. Violarlas no produce un lead malo: produce
un lead que no tiene sentido.

### Sobre el lead

| Regla | Por qué es universal |
|---|---|
| Si trae correo, tiene forma de correo | `pepito@@` no es una dirección en ninguna organización |
| El presupuesto no puede ser negativo | Un presupuesto negativo no significa nada |
| Tiene una identidad propia y una organización dueña | Sin dueño no se sabe quién puede verlo |
| Sólo se asigna un lead **calificado o sin asignar** | Repartir uno sin evaluar es repartir a ciegas |
| Sólo se **reasigna** uno que ya tenía asesor | Si no lo tenía, no hay nada que reasignar |
| Sólo se **libera** uno que estaba asignado | |
| El asesor destino pertenece **a la misma organización** que el lead | Lo contrario es una fuga de datos entre clientes |
| **Descartar exige escribir un motivo** | Un descarte sin motivo no es información, es un agujero |
| Un lead descartado no vuelve al reparto | Lo contrario haría el descarte inútil |

### Sobre las reglas que escribe el gestor

| Regla | Por qué es universal |
|---|---|
| Una regla tiene nombre | Una regla sin nombre no se puede administrar ni auditar |
| Una regla de puntuación apunta a un campo que existe y es puntuable | Ver la zona gris, §6 |
| "Está entre estos valores" exige una lista de valores | Comparar contra un solo valor no es estar en un conjunto |
| El tramo máximo no puede ser menor que el mínimo | Un tramo invertido no captura nada |
| Una regla de asignación **apunta a alguien**: un grupo o asesores concretos | Una regla sin destino no reparte |

### Sobre grupos y organizaciones

| Regla | Por qué es universal |
|---|---|
| Un grupo tiene nombre | |
| Una organización tiene nombre | |
| La capacidad por asesor, si se fija, es un número con sentido | Una capacidad negativa no limita nada |

### Sobre quién ve qué

Son las reglas más duras del sistema: no protegen la coherencia del dato, protegen **la separación
entre clientes**.

| Regla | Consecuencia de romperla |
|---|---|
| Nadie accede a los datos de otra organización | Fuga entre clientes |
| El administrador de la plataforma **no alcanza ningún dato comercial** | Quien crea las organizaciones no debe leer sus leads |
| Sólo el gestor administra su organización | |
| Un gestor no puede crear un administrador de plataforma | Escalada de privilegios |
| Un asesor sólo ve **sus propios** leads | Ver los del compañero es ver su cartera |
| Pedir un dato de otra organización responde **"no existe"**, no "no puedes" | "No puedes" confirma que existe. Se puede enumerar así |

Esa última merece detenerse: es la diferencia entre negar el acceso y **negar la existencia**. Si el
sistema respondiera "prohibido", cualquiera podría averiguar qué leads tiene la competencia probando
identificadores. Respondiendo "no existe", no se aprende nada.

---

## 4. Lo que decide cada organización

Estas reglas las escribe el gestor desde la interfaz, y **dos organizaciones tendrán configuraciones
completamente distintas sin que ninguna esté mal**.

| Decisión | Quién la toma | Estado |
|---|---|---|
| Qué campos suman puntos, y cuántos | Gestor | ✅ Configurable |
| Si una regla de puntuación está activa | Gestor | ✅ Configurable |
| En qué orden se evalúan las reglas | Gestor | ✅ Configurable |
| Qué tramo de puntuación va a qué grupo | Gestor | ✅ Configurable |
| Cómo se elige dentro del grupo: por turnos, al menos cargado, a uno concreto | Gestor | ✅ Configurable |
| Cuántos leads activos aguanta un asesor | Gestor | ✅ Configurable |
| Qué asesores forman cada grupo | Gestor | ✅ Configurable |
| **A partir de qué puntuación un lead merece asesor** | Gestor | ❌ **Enterrado en el código** |
| **Qué hace que un lead sea contactable** | Gestor | ❌ **Escrito como invariante** |
| **Qué canal o zona atiende cada equipo** | Gestor | ❌ **No se puede expresar** |

Las tres últimas son el trabajo pendiente. No es que falten funciones: es que **están en el lado
equivocado de la línea**.

---

## 5. Las tres que están en el lado equivocado

Vale la pena verlas de cerca, porque cada una falla de una manera distinta y las tres se detectan
con la misma prueba de la §2.

### 5.1 El corte de puntuación que nadie ve

**Lo que hay:** un número fijo escrito en el código decide a partir de qué puntuación un lead entra
al reparto. Nadie lo ve, nadie lo cambia.

**Por qué es una regla, no un invariante:** una consultora que factura por proyectos grandes pondrá
el listón altísimo; un concesionario que vende volumen lo pondrá casi a cero. Ninguna de las dos se
equivoca.

**Cómo se manifiesta el error:** el gestor escribe una regla de reparto para leads mediocres y **no
se dispara nunca**, sin ningún mensaje de error. Su regla está detrás de una puerta que él no sabe
que existe y que no puede mover.

### 5.2 El correo obligatorio

**Lo que hay:** un lead sin correo no se puede crear. El que llega sin él **se pierde**, sin dejar
rastro.

**Por qué es una regla:** hay organizaciones que trabajan sólo por teléfono, y otras por redes. Que
el correo sea imprescindible es una opinión, no una verdad.

**Cómo se manifiesta el error:** desaparecen leads y nadie sabe cuántos ni por qué. No hay bandeja
donde revisarlos, ni forma de rescatarlos si el mismo contacto vuelve más adelante con datos
completos.

**Lo que sí sigue siendo invariante:** que *si* viene un correo, tenga forma de correo. Se mantiene
el formato; se suelta la obligatoriedad.

### 5.3 El reparto que sólo entiende de puntuación

**Lo que hay:** una regla de asignación sólo puede condicionar por tramo de puntuación.

**Por qué es una regla:** *"los de la campaña de Facebook al equipo A"* no tiene nada que ver con la
calidad del lead. Es una decisión de organización interna del equipo.

**Cómo se manifiesta el error:** el gestor recurre a trucos —dar cientos de puntos a un canal para
reservarle un tramo— que se rompen en cuanto añade cualquier otra regla de puntuación.

---

## 6. La zona gris: casos donde la respuesta se discute

No todo cae limpio de un lado. Estos casos son los interesantes, y merecen argumentarse en vez de
decidirse por costumbre.

### Qué campos puede leer una regla de puntuación

Hoy existe una lista cerrada de campos sobre los que se puede puntuar. Una regla no puede leer
cualquier cosa del lead.

**Argumento para que sea invariante (el que ganó):** sin esa lista, una regla podría leer la
organización dueña del lead, o su identificador interno, y convertir un dato de sistema en un
criterio comercial. No es una restricción de negocio, es una **frontera de seguridad**: impide que
la configuración alcance las tripas del modelo.

**Argumento en contra:** limita al gestor a lo que el desarrollador previó. La válvula de escape son
los atributos personalizados, que sí son libres: lo que la fuente envíe, se puede puntuar.

### El descarte manual sobre un lead ya descalificado

Hoy un lead que el sistema descalificó no puede descartarlo un humano encima.

**Argumento a favor de la restricción:** el estado es un único campo. Descartar **sustituye** el
veredicto del sistema en vez de añadirse a él, y se pierde la información de que fue automático.

**Argumento en contra:** el gestor puede tener contexto que el sistema no tiene —una llamada, un
aviso de un compañero— y hoy no puede dejarlo escrito en ninguna parte.

**Sin resolver.** La salida probablemente no sea elegir un bando, sino dejar de guardar el veredicto
en un solo campo.

### La puntuación no tiene límites

Hoy una puntuación puede ser cualquier número, por absurdo que sea. No hay techo ni suelo.

**Por qué está sin decidir:** un rango sensato (0–100, por ejemplo) haría las reglas comparables
entre organizaciones y detectaría configuraciones rotas. Pero fijarlo obliga a decidir qué pasa
cuando la suma se sale, y eso es una regla de negocio más, no un detalle.

**Es un hueco conocido, no una decisión tomada.**

---

## 7. Cómo usar este documento

Cuando aparezca una validación nueva, antes de escribirla:

1. **Enúnciala en una frase, sin hablar de código.** Si no se puede, revisa qué estás validando.
2. **Pasa la prueba de la §2:** ¿existe una organización razonable a la que no le aplique?
3. **Si es regla**, va a la interfaz: el gestor la escribe, la edita y la desactiva.
4. **Si es invariante**, va al modelo, y este documento gana una fila.

Y cuando una regla cambie de lado —porque un cliente pidió una excepción razonable, o porque algo
que parecía negociable resultó no serlo— **anótalo aquí con el motivo**. Ese registro es el que
convierte la lista en una herramienta de diseño y no en un inventario.
