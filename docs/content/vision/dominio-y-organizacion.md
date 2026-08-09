# Qué decide cada organización

Qué reglas da por ciertas la plataforma siempre, frente a las que cada organización configura por
su cuenta, y el criterio que separa unas de otras.

## Por qué esta distinción decide el producto

Toda aplicación de negocio contiene dos clases de afirmación, y se parecen mucho por fuera:

- "Un presupuesto no puede ser negativo"
- "Un lead sin teléfono no vale la pena"

Las dos suenan a validación. Las dos se escriben igual de fácil. Pero sólo una de ellas es cierta
en cualquier organización, de cualquier sector, en cualquier país. La otra es una opinión
comercial de un cliente concreto.

Tratarlas igual sale caro, y de dos formas distintas:

| Error | Síntoma | Qué acaba ocurriendo |
|---|---|---|
| **Meter una regla dentro del dominio** | El sistema es rígido. Un cliente pide una excepción para su caso y hay que desplegar código para dársela | Ramas por cliente, banderas de configuración disfrazadas, datos que se pierden porque el modelo los rechaza |
| **Sacar un invariante fuera del dominio** | Aparecen datos incoherentes que nadie sabe de dónde salieron | La misma validación repetida en varios sitios, y siempre falta uno |

## La prueba

> ¿Puedes imaginar una organización razonable a la que esta afirmación no le aplique?
>
> Si **sí** → es una **regla de la organización**. Va a la interfaz, la escribe el gestor.
> Si **no** → es un **invariante del dominio**. Va al modelo, y no se negocia.

Aplicada a los dos ejemplos de arriba:

| Afirmación | ¿Alguna organización razonable la rompería? | Veredicto |
|---|---|---|
| "Un presupuesto no puede ser negativo" | No. Un presupuesto negativo no significa nada en ninguna parte | Invariante |
| "Un lead sin teléfono no vale la pena" | Sí: una consultora que contacta por LinkedIn, una inmobiliaria que trabaja por WhatsApp | Regla |

Una segunda prueba, útil cuando la primera no basta:

> ¿Esta afirmación dice que el dato es coherente, o que el dato es rentable?
>
> **Coherente** → dominio. **Rentable** → organización.

Un lead sin teléfono es un dato perfectamente coherente: tiene nombre, empresa, sector y momento
de entrada. Lo que no es, necesariamente, es rentable para todos. Son cosas distintas, y sólo la
primera le incumbe al modelo.

## Lo que la plataforma da por cierto siempre

Estas reglas no se pueden desactivar ni configurar. Violarlas no produce un lead malo: produce un
lead que no tiene sentido.

### Sobre el lead

| Regla | Por qué es universal |
|---|---|
| Si trae correo, tiene forma de correo | `pepito@@` no es una dirección en ninguna organización |
| El presupuesto no puede ser negativo | Un presupuesto negativo no significa nada |
| Tiene una identidad propia y una organización dueña | Sin dueño no se sabe quién puede verlo |
| Sólo se asigna un lead calificado o sin asignar | Repartir uno sin evaluar es repartir a ciegas |
| Sólo se reasigna uno que ya tenía asesor | Si no lo tenía, no hay nada que reasignar |
| Sólo se libera uno que estaba asignado | |
| El asesor destino pertenece a la misma organización que el lead | Lo contrario es una fuga de datos entre clientes |
| Descartar exige escribir un motivo | Un descarte sin motivo no es información, es un agujero |
| Un lead descartado no vuelve al reparto | Lo contrario haría el descarte inútil |

### Sobre las reglas que escribe el gestor

| Regla | Por qué es universal |
|---|---|
| Una regla tiene nombre | Una regla sin nombre no se puede administrar ni auditar |
| Una regla de puntuación apunta a un campo que existe y es puntuable | Ver la zona gris, más abajo |
| "Está entre estos valores" exige una lista de valores | Comparar contra un solo valor no es estar en un conjunto |
| El tramo máximo no puede ser menor que el mínimo | Un tramo invertido no captura nada |
| Una regla de asignación apunta a alguien: un grupo o asesores concretos | Una regla sin destino no reparte |

### Sobre grupos y organizaciones

| Regla | Por qué es universal |
|---|---|
| Un grupo tiene nombre | |
| Una organización tiene nombre | |
| La capacidad por asesor, si se fija, es un número con sentido | Una capacidad negativa no limita nada |

### Sobre quién ve qué

Son las reglas más duras del sistema: no protegen la coherencia del dato, protegen la separación
entre clientes.

| Regla | Consecuencia de romperla |
|---|---|
| Nadie accede a los datos de otra organización | Fuga entre clientes |
| El administrador de la plataforma no alcanza ningún dato comercial | Quien crea las organizaciones no debe leer sus leads |
| Sólo el gestor administra su organización | |
| Un gestor no puede crear un administrador de plataforma | Escalada de privilegios |
| Un asesor sólo ve sus propios leads | Ver los del compañero es ver su cartera |
| Pedir un dato de otra organización responde "no existe", no "no puedes" | "No puedes" confirma que existe. Se puede enumerar así |

Esa última merece detenerse: es la diferencia entre negar el acceso y negar la existencia. Si el
sistema respondiera "prohibido", cualquiera podría averiguar qué leads tiene la competencia
probando identificadores. Respondiendo "no existe", no se aprende nada. El razonamiento completo
está en [ADR-0005](../decisiones/0005-404-en-vez-de-403.md).

## Lo que decide cada organización

Estas reglas las escribe el gestor desde la interfaz, y dos organizaciones tendrán
configuraciones completamente distintas sin que ninguna esté mal.

| Decisión | Por qué es de la organización, no de la plataforma |
|---|---|
| Qué campos suman puntos, y cuántos | Cada negocio pesa sus propios atributos |
| Si una regla de puntuación está activa | Se prueban criterios sin borrarlos |
| En qué orden se evalúan las reglas | Sólo afecta a la trazabilidad del desglose, y eso también lo decide quien lo lee |
| Qué tramo de puntuación va a qué grupo | Define su propia estructura de equipos |
| Cómo se elige dentro del grupo: por turnos, al menos cargado, a uno concreto | Cada equipo reparte carga a su manera |
| Cuántos leads activos aguanta un asesor | Depende del producto que vende y de cuánto tarda en cerrarlo |
| Qué asesores forman cada grupo | Estructura interna del equipo comercial |
| A partir de qué puntuación un lead merece asesor | Una consultora que factura proyectos grandes pone el listón alto; un concesionario que vende volumen lo pone casi a cero |
| Qué hace que un lead sea contactable | Una consultora contacta por LinkedIn; una inmobiliaria, por WhatsApp; ninguna se equivoca |
| Qué canal o zona atiende cada equipo | Es una decisión de organización interna del equipo, no algo que la plataforma pueda presuponer |

Las tres últimas son las que más fácil se confunden con invariantes, porque parecen reglas de
sentido común. La prueba de la sección anterior es la que las separa: siempre hay una organización
razonable para la que la afirmación contraria también tiene sentido.

## La zona gris: casos donde la respuesta se discute

No todo cae limpio de un lado. Estos casos son los interesantes, y merecen argumentarse en vez de
decidirse por costumbre.

### Qué campos puede leer una regla de puntuación

Existe una lista cerrada de campos sobre los que se puede puntuar. Una regla no puede leer
cualquier cosa del lead.

**Argumento para que sea invariante (el que ganó):** sin esa lista, una regla podría leer la
organización dueña del lead, o su identificador interno, y convertir un dato de sistema en un
criterio comercial. No es una restricción de negocio, es una frontera de seguridad: impide que la
configuración alcance las tripas del modelo.

**Argumento en contra:** limita al gestor a lo que el desarrollador previó. La válvula de escape
son los atributos personalizados, que sí son libres: lo que la fuente envíe, se puede puntuar.

### El descarte manual sobre un lead ya descalificado

Un lead que el sistema descalificó no puede descartarlo un humano encima.

**Argumento a favor de la restricción:** el estado es un único campo. Descartar sustituiría el
veredicto del sistema en vez de añadirse a él, y se perdería la información de que fue automático.

**Argumento en contra:** el gestor puede tener contexto que el sistema no tiene —una llamada, un
aviso de un compañero— y hoy no puede dejarlo escrito en ninguna parte.

**Sin resolver.** La salida probablemente no sea elegir un bando, sino dejar de guardar el
veredicto en un solo campo.

### La puntuación no tiene límites

Una puntuación puede ser cualquier número, por absurdo que sea. No hay techo ni suelo.

**Por qué está sin decidir:** un rango sensato (0–100, por ejemplo) haría las reglas comparables
entre organizaciones y detectaría configuraciones rotas. Pero fijarlo obliga a decidir qué pasa
cuando la suma se sale, y eso es una regla de negocio más, no un detalle. Está recogido en la
[hoja de ruta](../roadmap/index.md) como una de las capacidades fuera de alcance por ahora.

**Es un hueco conocido, no una decisión tomada.**

## Cómo usar este documento

Cuando aparezca una validación nueva, antes de escribirla:

1. Enúnciala en una frase, sin hablar de código. Si no se puede, revisa qué estás validando.
2. Pasa la prueba de más arriba: ¿existe una organización razonable a la que no le aplique?
3. Si es regla, va a la interfaz: el gestor la escribe, la edita y la desactiva.
4. Si es invariante, va al modelo, y este catálogo gana una fila.

Y cuando una regla cambie de lado —porque un cliente pidió una excepción razonable, o porque algo
que parecía negociable resultó no serlo— anótalo aquí con el motivo. Ese registro es el que
convierte la lista en una herramienta de diseño y no en un inventario.
