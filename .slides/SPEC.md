# Diseño · Presentación de clase sobre Lead Router

| | |
|---|---|
| **Fecha** | 2026-08-10 |
| **Entregable** | `.slides/` — presentación Slidev, 26 diapositivas, 25-30 min |
| **Fuente** | `docs/content/` (6 464 líneas), `backend/migrations/`, `backend/src/` |

## Qué se construye

Una presentación ejecutable con Slidev que explique Lead Router ante una clase de arquitectura de
software. No es un resumen de la documentación: es la **destilación argumental** de los seis puntos
que pidió el encargo, con un diagrama por idea siempre que la idea sea estructural.

El criterio de selección de contenido es uno solo: **entra lo que sostiene un argumento; se queda
fuera lo que sólo describe**. La documentación describe el sistema tal como es; la clase tiene que
explicar por qué las decisiones fueron difíciles.

## Los seis puntos y qué material los sostiene

| # | Punto del encargo | Fuente principal | Argumento que se defiende |
|---|---|---|---|
| 1 | La idea a resolver | `vision/el-problema.md`, `vision/modelo-de-decision.md` | Tres decisiones de naturaleza distinta no caben en una sola escala numérica |
| 2 | Mono-empresa → multitenancy | `vision/dominio-y-organizacion.md`, ADR-0004, ADR-0011, ADR-0014, `migrations/001→008` | Cuando llega el segundo cliente, la mitad del dominio deja de ser dominio |
| 3 | Arquitectura | `arquitectura/index.md`, `c4-componentes.md`, ADR-0001 | Una regla de dependencia sin guardián automático se erosiona |
| 4 | Problemas encontrados | ADR-0009, ADR-0010, ADR-0014, ADR-0003, `otros/donde-se-valida-lo-que-entra.md`, `roadmap/deuda-tecnica.md` | Los defectos caros no dan error: pierden datos en silencio |
| 5 | Python y el repo | `c4-componentes.md`, `domain/value_objects/criterion.py`, `desarrollo/validacion.md` | Cada regla de arquitectura tiene su equivalente ejecutable |
| 6 | Diagramas | Los ~10 diagramas Mermaid ya escritos en la doc | — |

## La columna vertebral: el punto 2 es el eje

El encargo enumera seis puntos, pero no son seis bloques equivalentes. **El punto 2 es la tesis de
la clase** y los demás la sostienen: la arquitectura (3) existe porque hacía falta mover reglas de
lado sin reescribir el sistema; los problemas (4) son en su mayoría el precio de haberlo hecho mal
la primera vez; la implementación (5) es la prueba de que la frontera se sostiene.

La evolución se cuenta con **evidencia del repositorio**, no como relato:

| Migración | Qué había antes | Qué se movió |
|---|---|---|
| `001_baseline_schema.sql` | `scoring_rules` con `field`/`operator`/`value` — **una condición inline por regla**; `routing_rules` con `target_team TEXT`; `agents.team TEXT`; `agents.active_leads_count` desnormalizado; `tenant_id` presente pero **sin tabla `tenants`** | Punto de partida: multi-tenant de nombre, reglas rígidas |
| `002_tenants.sql` | — | Aparece `tenants`, los índices únicos parciales por organización y el administrador de plataforma |
| `003_groups_and_assignment.sql` | `team` era una cadena libre | `sales_groups` como entidad; `routing_rules` → `assignment_rules`; se borra `active_leads_count` (la carga se cuenta al vuelo) |
| `004_lead_lifecycle_and_scoring.sql` | Una regla no se podía apagar ni ordenar | `priority`, `is_active`, `score_breakdown` |
| `007_composable_rules.sql` | Una condición por regla; la viabilidad no existía | `conditions JSONB` (varias condiciones) y `disqualification_rules` |

Ese recorrido es exactamente «las reglas dejan de ser del dominio y pasan a ser configuración», y
se puede enseñar con `git`, no con palabras.

## Registro y tono

Presentación formal: portada sobria, objetivos de la sesión y agenda con
duraciones antes de entrar en materia. Los títulos enuncian el contenido, no lo
dramatizan; el pie de cada diapositiva es una idea clave descriptiva.

## Estructura de las diapositivas

**Una sola plantilla, repetida 26 veces.** Cada diapositiva lleva:

- **Cabecera fija**: número de bloque · nombre del bloque (`2 · De una empresa a muchas`), a la
  izquierda; contador de diapositiva a la derecha.
- **Cuerpo**: un único elemento dominante — un diagrama Mermaid, una tabla comparativa, o un bloque
  de código. Nunca dos.
- **Pie fijo**: una línea, la **idea clave** de la diapositiva, en una frase sin subordinadas. Es lo
  que queda si el alumno sólo lee el pie.

Los bloques no gastan una diapositiva en separadores: el número de bloque en la cabecera cambia y
eso basta. Con 25 diapositivas para 25-30 minutos, un separador cuesta el 4 % del tiempo a cambio de
nada.

## Guion, diapositiva a diapositiva

### Bloque 0 · Apertura (2)

| # | Contenido | Elemento dominante |
|---|---|---|
| 1 | Portada: Lead Router, enrutamiento de leads con arquitectura hexagonal | — |
| 2 | Mapa de la clase: los seis bloques y la pregunta que responde cada uno | Tabla |

### Bloque 1 · La idea (4)

| # | Contenido | Elemento dominante |
|---|---|---|
| 3 | Qué es un lead y por qué el reparto manual falla con volumen | Tabla de los tres costes |
| 4 | Tres preguntas de naturaleza distinta: binaria, continua, categórica | Tabla |
| 5 | Qué pasa si se fuerzan las tres en una sola puntuación: los dos trucos de ±9999 | Tabla |
| 6 | El pipeline en tres etapas, cada una con su herramienta | Mermaid `flowchart` |

### Bloque 2 · De una empresa a muchas (5)

| # | Contenido | Elemento dominante |
|---|---|---|
| 7 | El punto de partida: la regla vivía en el código, una condición por fila | Código SQL de `001` + pseudocódigo del umbral |
| 8 | La pregunta que lo parte en dos: ¿existe una organización razonable a la que esto no le aplique? | Mermaid `flowchart` (árbol de decisión) |
| 9 | El catálogo: qué se quedó en el dominio y qué se fue a la interfaz | Tabla a dos columnas |
| 10 | Lo que la migración enseña: `001` → `007` como historia del cambio | Mermaid `timeline` |
| 11 | Multitenancy real: el tenant sale del token, dos planos disjuntos, 404 en vez de 403 | Mermaid `flowchart` |

### Bloque 3 · Cómo está estructurado (5)

| # | Contenido | Elemento dominante |
|---|---|---|
| 12 | Las tres capas y la regla de dependencia | Mermaid `flowchart` (hexágono en capas) |
| 13 | Puertos y adaptadores: qué se enchufa dónde | Mermaid `flowchart` (C4 nivel 3, reducido) |
| 14 | El guardián: cuatro tests que leen el AST y no dejan que la regla se erosione | Código Python |
| 15 | Las tres etapas y sus tres motores, con la unidad compartida `Criterion` | Mermaid `flowchart` |
| 16 | El lead como máquina de estados: seis estados, dos terminales | Mermaid `stateDiagram` |

### Bloque 4 · Lo que salió mal (4)

| # | Contenido | Elemento dominante |
|---|---|---|
| 17 | Lo que entraba se perdía: tres peticiones rotas, dos sin dejar rastro | Tabla de las tres peticiones |
| 18 | La inversión que lo resuelve: el servicio deja de escribir el registro y pasa a leerlo | Mermaid `sequenceDiagram` |
| 19 | El umbral invisible: una regla detrás de una puerta que nadie veía | Mermaid `flowchart` antes/después |
| 20 | Las fugas entre organizaciones y el cursor de turnos que se reiniciaba en cada petición | Tabla de tres defectos con su causa común |

### Bloque 5 · Python y el repositorio (4)

| # | Contenido | Elemento dominante |
|---|---|---|
| 21 | El árbol de `backend/src/`: dónde vive cada capa | Árbol de ficheros |
| 22 | El dominio sin dependencias: `Criterion` y su lista blanca | Código Python |
| 23 | Puerto → caso de uso → adaptador, el mismo concepto en tres ficheros | Código Python (tres fragmentos) |
| 24 | Cómo se valida: tres comandos, y qué demuestra cada uno | Tabla |

### Bloque 6 · Cierre (1)

| # | Contenido | Elemento dominante |
|---|---|---|
| 25 | Cinco cosas que llevarse, y lo que se dejó fuera a propósito | Tabla |

## Decisiones técnicas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Slidev** con `slides.md` único | Un fichero por bloque con `src:` | 25 diapositivas caben en un fichero legible; partirlo añade seis ficheros y una tabla de contenidos que mantener |
| **Mermaid nativo** | Draw.io exportado a SVG | Los diagramas ya existen en Mermaid dentro de la doc; reutilizarlos es transcripción, no rediseño. Un `.drawio` por diagrama son doce ficheros binarios que hay que reexportar cada vez que cambia una etiqueta |
| **Tema `default` + CSS propio** | Un tema de terceros (`seriph`, `apple-basic`) | El tema propio es un fichero de estilos; un tema de terceros es una dependencia más que impone su tipografía y hay que pelear para adaptarla |
| **Un layout propio, `blocked`** | Repetir la cabecera y el pie a mano en 25 diapositivas | La consistencia que pide el encargo se garantiza sola si la plantilla es un layout, no una convención |
| **Contenido en español, código en inglés** | — | Es la convención del repositorio |

## Qué queda fuera, a propósito

- **La referencia de la API.** 60 endpoints no son material de clase.
- **El detalle del módulo de notificaciones y del webhook saliente.** Son satélites del argumento.
- **El frontend.** Está a medio construir y no aporta a ninguno de los seis puntos.
- **Las notas del presentador para cada diapositiva.** El pie con la idea clave es la nota. Añadir
  un guion hablado duplica el contenido en dos sitios que divergen.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Un diagrama Mermaid grande no cabe en 980×552 px | Cada diagrama de la doc se reduce al mínimo que sostiene la idea; el ER completo (14 tablas) no entra y se sustituye por la máquina de estados |
| La versión de Slidev cambia la sintaxis de los layouts | Se fija la versión en `package.json` y se verifica con un build real antes de entregar |
| El contenido no cabe en 25-30 minutos | Un elemento dominante por diapositiva es el límite duro; si algo necesita dos, es que son dos diapositivas o sobra una |

## Criterio de aceptación

1. `npm run build` en `.slides/` termina sin errores.
2. Las 25 diapositivas tienen cabecera, cuerpo único y pie con idea clave.
3. Hay al menos 10 diagramas Mermaid y ninguno se sale del área visible.
4. Todo dato numérico o nombre de fichero citado existe en el repositorio.
