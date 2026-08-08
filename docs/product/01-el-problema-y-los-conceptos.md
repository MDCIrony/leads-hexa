# El problema y los conceptos

> **Estado: esbozo.** Este documento fija el marco conceptual y el vocabulario. Cada sección está
> pensada para crecer después en un documento propio; los puntos marcados **[ampliar]** señalan
> dónde. No se desarrolla más por ahora.

---

## 1. El problema

Una organización comercial recibe leads —personas o empresas que han mostrado interés— por varios
canales a la vez: un formulario web, una campaña en redes, un fichero que envía un socio, una
llamada. Alguien tiene que decidir, para cada uno, dos cosas distintas:

1. **¿Merece la pena?** No todos valen lo mismo. Uno llega sin teléfono ni correo; otro trae
   presupuesto declarado y es del sector al que vendemos.
2. **¿Quién lo atiende?** El equipo no es homogéneo: hay asesores senior y junior, hay quien lleva
   una zona o un idioma, y todos tienen una carga de trabajo que no debería desequilibrarse.

Sin sistema, esas dos decisiones las toma una persona a mano, lead a lead. Eso produce tres
problemas que se agravan con el volumen:

| Problema | Qué cuesta |
|---|---|
| **Lentitud** | El lead espera en una hoja de cálculo mientras la competencia le llama |
| **Reparto injusto o arbitrario** | Unos asesores saturados y otros ociosos; los buenos leads se los queda quien llega primero |
| **Leads perdidos** | Nadie se hizo responsable, y no queda rastro de por qué |

**Lo que la plataforma hace:** recibe el lead, lo evalúa contra reglas que el gestor escribe, y lo
entrega automáticamente al asesor que corresponde —dejando constancia de por qué—. Cuando ninguna
regla lo cubre, no lo pierde: lo deja visible para que el gestor decida a mano.

**[ampliar]** El coste real del reparto manual, con el recorrido completo de un lead desde que entra
hasta que un asesor lo contacta.

---

## 2. Las dos decisiones son ejes distintos

Es el concepto central, y confundirlos es el error de diseño más común en este tipo de sistemas.

| Eje | Pregunta | Se basa en | Nombre del sector |
|---|---|---|---|
| **Calidad** | ¿Vale la pena? ¿Cuánta atención merece? | Lo completo y prometedor que venga el dato | *Lead scoring* |
| **Destino** | ¿Quién lo atiende? | Canal de origen, zona, idioma, especialidad | *Lead routing / assignment* |

Son **ortogonales**: un lead excelente puede venir de Facebook y otro pésimo también. La calidad no
dice a qué equipo va, y el canal no dice si vale la pena.

Las plataformas profesionales los mantienen separados y los combinan al final. La plataforma que
construimos hace lo mismo: unas reglas puntúan, otras reparten.

**[ampliar]** Cómo se combinan los dos ejes en una matriz de decisión, con ejemplos.

---

## 3. Vocabulario del sector

Términos establecidos que esta plataforma implementa. Sirven para situar lo que hacemos en la
práctica real, no como decoración.

| Término | Qué significa |
|---|---|
| **Lead** | Contacto que ha mostrado interés, aún sin calificar |
| **Lead scoring** | Asignar puntos a un lead según sus atributos, para ordenar por calidad |
| **MQL** — *Marketing Qualified Lead* | Supera el umbral de calidad: marketing dice que vale |
| **SQL** — *Sales Qualified Lead* | Ventas lo acepta y se hace responsable |
| **Lead routing** | Decidir a qué persona o equipo se entrega |
| **Tiering** | Repartir por bandas de calidad hacia niveles de equipo distintos |
| **SDR** — *Sales Development Rep* | Perfil que califica y enriquece el lead antes de pasarlo |
| **AE** — *Account Executive* | Perfil que cierra la venta. Su tiempo es el recurso caro |
| **Speed-to-lead** | Tiempo entre que el lead entra y alguien le contacta |

**La frontera MQL → SQL es literalmente el umbral de puntuación de esta plataforma.** Por debajo, el
lead no se entrega a nadie. Por encima, entra al reparto.

**[ampliar]** Glosario completo, en el documento 05.

---

## 4. Por qué el negocio reparte según la calidad

La lógica económica es una sola: **el tiempo de un asesor senior es el recurso más caro del embudo.**
El scoring existe para no malgastarlo. Cuatro usos profesionales reconocidos:

### 4.1 Tiering — bandas de calidad hacia niveles de equipo

| Banda | A dónde va | Por qué |
|---|---|---|
| Alta | Asesor senior | Trae presupuesto y datos completos: se cierra hablando |
| Media | Asesor junior o SDR | Hay que trabajarlo antes: completar datos, confirmar interés |
| Baja | A nadie | Poner a un humano ahí es pérdida neta. Si su puntuación sube, vuelve a entrar |

Es el reparto SDR / AE que usa cualquier equipo comercial estructurado: uno califica y enriquece,
otro cierra.

### 4.2 La frontera de entrega a ventas

El uso más extendido. Por debajo del umbral, el lead **no se le da a ningún vendedor**. Por encima,
ventas lo acepta. Las plataformas del sector construyen buena parte de su producto sobre esa
frontera.

### 4.3 Prioridad de contacto diferenciada

Los leads de calidad alta entran en una cola con compromiso de contacto agresivo; los demás, en una
cola normal. Es principio establecido que la probabilidad de conversión cae con el tiempo de
respuesta, así que la velocidad se reserva para donde paga.

### 4.4 Dos dimensiones: comportamiento y ajuste

Algunas plataformas separan la puntuación en dos ejes y reparten por la combinación:

- **Puntuación** (número): comportamiento — abrió el correo, visitó la web, descargó el documento
- **Grado** (letra): ajuste al perfil de cliente ideal — sector, tamaño, cargo

| Combinación | Significa | Se entrega a |
|---|---|---|
| Perfil ideal + muy activo | Listo para hablar | Asesor senior, de inmediato |
| Perfil ideal + frío | Merece la pena esperarlo | Seguimiento automático |
| Mal perfil + muy activo | Suele ser investigación, un estudiante o un competidor | A nadie |

Nuestra plataforma trabaja con **un solo eje** por decisión de alcance: es un MVP. La estructura de
reglas permitiría el segundo sin rediseñar nada.

**[ampliar]** Cada uno de los cuatro casos con una configuración de reglas completa, en el
recetario (documento 04).

---

## 5. Cómo se configura hoy

Ejemplo real y funcional con lo que la plataforma ya soporta. El gestor escribe reglas de dos tipos.

**Reglas de puntuación** — cuánto vale el lead:

| Si… | Suma |
|---|---|
| Tiene teléfono | +30 |
| El presupuesto supera 5.000 | +25 |
| El sector es Tecnología, SaaS o Fintech | +40 |
| Tiene empresa declarada | +15 |

**Reglas de asignación** — a quién se entrega:

| Banda de puntuación | Grupo | Cómo se elige dentro del grupo |
|---|---|---|
| 80 o más | Senior | Al menos cargado |
| Entre 40 y 79 | Enriquecimiento | Por turnos |

Con esa configuración:

- Un lead con teléfono, presupuesto y sector objetivo suma **95** → asesor senior
- Uno con sólo empresa y sector suma **55** → equipo de enriquecimiento, que le busca el teléfono
- Uno sin nada suma **0** → no lo toca nadie

El gestor puede ver, para cada lead, **qué reglas se cumplieron y cuántos puntos aportó cada una**.
No es una caja negra: la puntuación se explica sola.

**[ampliar]** Guía paso a paso de creación de reglas desde la interfaz, en el documento 02.

---

## 6. Qué falta para cubrir el problema completo

Dos huecos identificados, ambos reales. Se registran aquí porque forman parte de la explicación
honesta del producto, no sólo de la planificación.

### 6.1 No se puede repartir por canal ni por zona

Hoy las reglas de asignación sólo saben condicionar por **banda de puntuación**. No hay forma de
expresar *"todos los que vienen de Facebook van al grupo A"*, que es el patrón de reparto más común
que existe.

Se puede simular dando muchos puntos al origen y reservando una banda alta, pero es frágil: dos
orígenes necesitan bandas que no se solapen, y cualquier otra regla de puntuación desplaza el lead
fuera de la suya.

**Qué haría falta:** que una regla de asignación pueda condicionar por cualquier atributo del lead,
igual que ya hacen las reglas de puntuación.

### 6.2 Hay una franja de leads que queda en tierra de nadie

La calificación usa dos cortes en vez de uno, y entre ambos queda una franja donde el lead ni se
califica ni se descalifica: **se queda sin entrar al reparto y sin quedar marcado como rechazado.**
Para el gestor es indistinguible de un lead recién llegado sin procesar.

**Qué haría falta:** un solo umbral, con dos salidas —entra al reparto o queda rechazado—. La
granularidad de "cuánto vale" ya la dan las bandas de las reglas de asignación, que es su sitio
natural.

**[ampliar]** Ambos huecos, cuando se cierren, pasan a la sección 5 como funcionalidad y desaparecen
de aquí.

---

## 7. Qué no hace la plataforma

Delimitarlo es parte de explicarla. Fuera de alcance en el MVP:

- **No es un CRM.** No sigue la venta después de la asignación: no hay estados de contactado,
  ganado o perdido.
- **No hace puntuación predictiva.** Las reglas las escribe el gestor; no hay modelo que aprenda
  del histórico.
- **No integra plataformas externas por su cuenta.** La entrada por webhook está prevista en el
  diseño pero no implementada.
- **No envía correos ni gestiona campañas.** Reparte leads; lo que ocurre después es de otro
  sistema.
