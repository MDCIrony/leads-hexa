# Documentación de producto

Esta carpeta explica **qué problema resuelve la plataforma y cómo se usa**. Va dirigida a quien la
opera —el gestor y el asesor— y a quien necesita entender el porqué antes que el cómo.

No se confunde con el resto de `docs/`, que es material de construcción:

| Carpeta | Para quién | Responde a |
|---|---|---|
| **`product/`** (esta) | Gestor, asesor, evaluador | ¿Qué problema resuelve? ¿Cómo se usa? |
| [`specs/`](../specs/) | Quien implementa | ¿Qué hay que construir y con qué contratos? |
| [`plans/`](../plans/) | Quien implementa | ¿En qué orden y con qué pasos? |
| [`api/`](../api/) | Quien integra | ¿Qué endpoints hay y qué devuelven? |
| [`diagrams/`](../diagrams/) | Quien diseña | ¿Cómo encajan las piezas? |
| [`conceptos/`](../conceptos/) | Quien estudia | ¿Por qué se decidió así, y qué alternativas había? |

Una regla para no mezclarlas: aquí **no se nombra una clase, un fichero ni un endpoint**. Si un
párrafo sólo se entiende sabiendo Python, pertenece a `specs/`.

---

## Índice

| Documento | Estado | Contenido |
|---|---|---|
| [01 — El problema y los conceptos](01-el-problema-y-los-conceptos.md) | **Esbozo** | Por qué existe la plataforma, los dos ejes de decisión, el vocabulario del sector y los casos de uso profesionales que la respaldan |
| [02 — El modelo de decisión](02-el-modelo-de-decision.md) | **Esbozo** | Las tres decisiones y su naturaleza (binaria, continua, categórica), qué pasa cuando se confunden, el recorrido en tres etapas, la semántica de cada estado, cómo se componen las reglas y el lead que vuelve |
| [03 — Dominio y organización](03-dominio-y-organizacion.md) | **Catálogo vivo** | Qué reglas son ciertas siempre y cuáles decide cada organización. La prueba para distinguirlas, el catálogo de ambos lados, las tres que están en el lado equivocado y los casos aún en discusión |
| [Mejoras futuras](mejoras-futuras/) | **Fuera de alcance** | Capacidades que se discutieron y se decidieron para después, con lo que habría que resolver antes de construirlas |

## Por escribir

Ninguno de estos existe todavía. Se listan para fijar el alcance, no como promesa de fecha.

| Documento | Contenido previsto | Depende de |
|---|---|---|
| `04 — Guía del gestor` | Dar de alta asesores y grupos, escribir reglas de puntuación y de asignación, leer la bandeja de entrada, asignar y descartar a mano | F4 (las vistas) |
| `05 — Guía del asesor` | Entrar, leer la cartera propia, consultar el detalle de un lead | F4 |
| `06 — Recetario de reglas` | Configuraciones que resuelven casos reales: reparto por calidad, por canal, por carga, equipos de enriquecimiento | Condiciones por atributo en las reglas de asignación |
| `07 — Glosario` | Lead, tenant, grupo, puntuación, banda, asignación, descarte, MQL/SQL, SDR/AE | — |
| `08 — Preguntas frecuentes` | Por qué un lead no se asignó, por qué una regla no se cumple, qué significa cada estado | Uso real |

## Cómo se escribe aquí

- **En español**, como el resto de la documentación. El código sigue siendo inglés.
- **Sin jerga de implementación.** El lector es un gestor comercial, no un desarrollador.
- **Cada afirmación funcional debe ser cierta hoy.** Lo que aún no existe se marca como pendiente y
  se dice en qué fase llega. Una guía que describe funciones inexistentes es peor que no tener guía.
