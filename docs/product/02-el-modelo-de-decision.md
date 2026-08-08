# El modelo de decisión

> **Estado: esbozo conceptual.** Fija el marco con el que la plataforma decide qué hacer con cada
> lead. Parte describe cómo funciona hoy; parte describe hacia dónde debe ir, y está marcado como
> tal. Léase después de [01 — El problema y los conceptos](01-el-problema-y-los-conceptos.md).

---

## 1. Tres decisiones de naturaleza distinta

Cada lead que entra dispara tres preguntas. Parecen variaciones de lo mismo —"¿qué hago con esto?"—
pero **no son del mismo tipo**, y ahí está la clave del diseño:

| Decisión | Pregunta | Naturaleza | Respuesta que admite |
|---|---|---|---|
| **Viabilidad** | ¿Se puede trabajar? | **Binaria** | Sí o no. No hay término medio |
| **Calidad** | ¿Cuánto vale? | **Continua** | Un valor en una escala, que ordena y admite tramos |
| **Destino** | ¿Quién lo atiende? | **Categórica** | Un equipo o una persona de un conjunto |

Un ejemplo de cada una:

- **Viabilidad:** el lead no dejó ni teléfono ni correo. No es que valga poco — es que **no hay
  forma de contactarle**. Ni el mejor asesor puede hacer nada.
- **Calidad:** trae presupuesto declarado, empresa y un sector al que vendemos. Vale más que otro
  que sólo dejó el nombre. Se puede ordenar.
- **Destino:** entró por la campaña de Facebook, y esa campaña la atiende el equipo A. Nada que ver
  con lo bueno que sea.

Son **independientes**. Un lead puede ser viable, excelente y venir de Facebook. Otro puede ser
viable, mediocre y venir del formulario web.

---

## 2. Qué pasa cuando se confunden

Si el sistema sólo ofrece una herramienta —la puntuación— para las tres decisiones, el gestor se ve
obligado a codificar en un número cosas que no son un número. Aparecen dos trucos, que son el mismo
error en espejo:

| Lo que el gestor quiere | El truco que se ve forzado a hacer | Por qué se rompe |
|---|---|---|
| "Sin contacto, descartar siempre" | Restarle una cantidad enorme de puntos para garantizar que caiga por debajo del corte | Está usando una escala continua para expresar un sí/no. Cualquier otra regla que sume puede rescatarlo por accidente |
| "Los de Facebook, al equipo A" | Sumarle una cantidad enorme y reservarle un tramo alto | Dos canales necesitan tramos que no se solapen, y cualquier regla de calidad desplaza el lead fuera del suyo |

**El síntoma común:** en cuanto un gestor escribe números enormes (±1000, ±9999) para forzar un
comportamiento, el modelo le está quedando corto. Ese número no expresa calidad; expresa *"por
favor, haz que esto caiga donde yo quiero"*.

La corrección no es afinar los números. Es **darle a cada decisión la herramienta de su naturaleza**:

| Decisión | Herramienta correcta |
|---|---|
| Viabilidad (binaria) | **Reglas de descalificación**: condiciones sobre campos, con motivo |
| Calidad (continua) | **Reglas de puntuación**: suman y restan puntos |
| Destino (categórica) | **Reglas de asignación**: condiciones sobre atributos + tramo de puntuación |

---

## 3. El recorrido de un lead, en tres etapas

```
   entra el lead
        │
        ▼
┌───────────────────┐   no se puede trabajar
│ 1. VIABILIDAD     │────────────────────────►  DESCALIFICADO  (con motivo legible)
│    ¿se puede?     │
└─────────┬─────────┘
          │ sí
          ▼
┌───────────────────┐
│ 2. CALIDAD        │  le asigna una puntuación y deja constancia
│    ¿cuánto vale?  │  de qué reglas se cumplieron
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐   ninguna regla lo cubre,
│ 3. DESTINO        │   o nadie tiene hueco
│    ¿quién?        │────────────────────────►  SIN ASIGNAR  (espera al gestor)
└─────────┬─────────┘
          │
          ▼
      ASIGNADO
```

Tres etapas, tres responsabilidades. La primera **corta el flujo**: no tiene sentido puntuar ni
repartir algo que nadie puede trabajar.

> La etapa 1 **existe desde F2c**, con reglas que el gestor escribe. Antes su papel lo hacía un corte
> de puntuación fijado en el código, que nadie veía ni podía cambiar.

---

## 4. Semántica de los estados

Un lead sólo puede estar en un estado, y cada uno responde a **quién decidió y por qué**. Es lo que
permite que la interfaz muestre bandejas con sentido en vez de una lista indiferenciada.

| Estado | Significa | Quién decidió | Qué hace el gestor |
|---|---|---|---|
| **Nuevo** | Acaba de entrar. Aún sin procesar | — | Nada. Es transitorio |
| **Descalificado** | No se puede trabajar | La máquina, por una regla | Revisa si la regla está bien escrita |
| **Calificado** | Vale la pena; pendiente de reparto | La máquina | Nada. Es transitorio |
| **Sin asignar** | Vale la pena, **pero nadie lo cubre** | La máquina se rindió | **Lo asigna a mano** |
| **Asignado** | Tiene asesor responsable | La máquina o el gestor | Puede reasignarlo o liberarlo |
| **Descartado** | Rechazado por una persona, con motivo escrito | **Un humano** | Consulta el histórico |

Dos distinciones que parecen sutiles y son las que dan valor:

**Descalificado ≠ Descartado.** El primero es automático y su motivo lo da una regla ("sin datos de
contacto"). El segundo es una persona que miró el lead y escribió por qué no. Fundirlos perdería la
información de *quién decidió*, que es justo lo que el gestor necesita para saber si sus reglas
están bien.

**Descalificado ≠ Sin asignar.** El primero no vale la pena; el segundo sí vale pero no encontró
destino. Si se mezclaran, la bandeja de revisión manual del gestor se llenaría de basura junto a
leads buenos, y dejaría de revisarla. Ese umbral es lo que mantiene la bandeja utilizable.

### La bandeja de rechazados

Descalificados y descartados van a la misma vista, con una columna que distingue **máquina** de
**persona**. No es un archivo muerto: es donde el gestor comprueba si sus reglas están descartando lo
que debe. Una regla mal escrita se detecta ahí, no en los leads que sí pasaron.

---

## 5. Cómo se componen las reglas

Una regla suelta rara vez expresa un criterio real. *"Descartar al que no tenga forma de
contactarnos"* no es una condición, son dos que deben cumplirse **a la vez**: sin teléfono **y** sin
correo. Si le falta sólo una, se le puede escribir o llamar.

Escribir esas dos condiciones como dos reglas separadas produce el resultado contrario al buscado:

| Lead | Teléfono | Correo | Con dos reglas sueltas | ¿Correcto? |
|---|---|---|---|---|
| Ana | — | ana@empresa.com | Descalificada | ❌ Se le puede escribir |
| Beto | 600 123 456 | — | Descalificado | ❌ Se le puede llamar |
| Carla | — | — | Descalificada | ✅ |

Dos de cada tres mal, y no se arregla añadiendo más reglas: reglas separadas siempre significan
*"basta con que se cumpla alguna"*.

**La regla lleva varias condiciones, y se cumple cuando se cumplen todas.** Con eso solo, el gestor
tiene las dos formas de combinar que necesita, sin aprender ningún concepto nuevo:

| Lo que quiere expresar | Cómo lo escribe |
|---|---|
| Se cumplen **todas** las condiciones | **Una regla** con varias condiciones |
| Basta con que se cumpla **alguna** | **Varias reglas**, una por condición |

Nunca aparecen las palabras "Y" ni "O" en la interfaz. El gestor lee *"esta regla se cumple cuando
pasa todo esto"*, y si quiere alternativas, escribe otra regla.

### Hacia dónde crece *(visión de producto, fuera del MVP)*

La regla con varias condiciones es deliberadamente **la pieza mínima sobre la que se construye
todo lo demás**. Un producto maduro en este espacio termina ofreciendo un **constructor visual**:
un lienzo donde el gestor arrastra nodos de condición, los encadena, y ve el recorrido que seguirá
un lead antes de guardarlo.

| Etapa | Qué añade |
|---|---|
| **Hoy** | Una condición por regla. Sólo permite "basta con alguna" |
| **Siguiente paso** | Varias condiciones por regla. Ya se expresa cualquier criterio real |
| **Producto** | Lienzo visual: nodos de condición encadenados, con vista previa del recorrido |
| **Producto maduro** | Biblioteca de reglas predefinidas por sector, y bloques reutilizables que el gestor compone y nombra |

Nada de esto cambia el modelo de datos: un lienzo visual es **otra forma de escribir las mismas
condiciones**. Por eso la decisión de hoy —permitir varias condiciones en una regla— es la que
abre la puerta, y por eso conviene tomarla bien aunque la interfaz tarde en llegar.

---

## 6. El lead que vuelve *(fuera del alcance de este MVP)*

Un mismo contacto puede entrar **varias veces**: rellenó el formulario, no le llamaron, volvió a
pedir información dos semanas después. Hoy la plataforma trata cada entrada como un lead nuevo e
independiente.

Reconocer que es el mismo se llama **deduplicación** o **resolución de identidad**, y no entra en
esta entrega. La razón no es su tamaño: es que **el campo por el que dos entradas son «la misma
persona» lo decide cada organización**, no la plataforma, así que la funcionalidad incluye su propia
configuración.

Está desarrollado en
[Mejoras futuras · Identidad del contacto](mejoras-futuras/01-identidad-del-contacto.md): el valor
que aporta, por qué el identificador es configurable y las dos decisiones que siguen abiertas.

Aquí sólo importa retener una consecuencia del correo opcional (§1): **un campo que puede faltar no
puede ser la identidad por sí solo**.

---

## 7. Qué es invariante y qué es regla

Las tres etapas anteriores plantean una pregunta que atraviesa todo el diseño: **de las cosas que
el sistema valida, ¿cuáles son ciertas siempre y cuáles decide cada organización?**

El criterio corto:

> **¿Puedes imaginar una organización razonable a la que esta afirmación no le aplique?**
> Si sí, es una **regla** que el gestor configura. Si no, es un **invariante** del modelo.

Aplicado a la contactabilidad: *"si viene un correo, tiene forma de correo"* es invariante —no hay
organización para la que `pepito@@` sea válido—. *"Un lead sin contacto no vale la pena"* es regla:
una consultora contacta por redes, una inmobiliaria por mensajería, un concesionario por teléfono.

Hoy la segunda está escrita como si fuera la primera, y eso hace que el lead sin correo **se pierda**
en vez de quedar en una bandeja revisable.

**El catálogo completo —qué está en cada lado hoy, qué está en el lado equivocado, y los casos que
siguen en discusión— vive en [03 — Dominio y organización](03-dominio-y-organizacion.md).**

---

## 8. Distancia entre este modelo y lo que hay hoy

| Elemento del modelo | Estado |
|---|---|
| Reglas de puntuación con condiciones sobre campos | ✅ Funciona |
| Desglose visible de qué reglas se cumplieron | ✅ Funciona |
| Reparto por tramo de puntuación, con estrategias | ✅ Funciona |
| Asignación y descarte manuales, con motivo | ✅ Funciona |
| Estado propio para "vale pero nadie lo cubre" | ✅ Funciona |
| **Etapa de viabilidad con reglas del gestor** | ✅ Funciona |
| **Condiciones "está vacío" / "no está vacío"** | ✅ Funciona |
| **Combinar varias condiciones en una regla** | ✅ Funciona |
| **Reparto por canal, zona o especialidad** | ✅ Funciona |
| **Lead sin correo, conservado y revisable** | ✅ Funciona. El correo es opcional, y lo que no se puede interpretar queda en la bandeja con su detalle en vez de perderse |
| **Identidad del contacto entre entradas** | ❌ No existe |

Las cuatro que estaban en rojo se apoyaban en **la misma pieza**: la capacidad de evaluar una
condición —*este campo, comparado así, con este valor*— contra un lead. Extraerla como unidad
compartida y reutilizarla en las tres etapas es lo que las cerró de una vez, en lugar de con cuatro
parches sueltos.

Lo único que sigue abierto es la identidad del contacto, y no por tamaño: el campo que decide si dos
entradas son la misma persona lo elige cada organización, así que arrastra su propia configuración.
Está desarrollado en [Mejoras futuras · Identidad del contacto](mejoras-futuras/01-identidad-del-contacto.md).
