# Plan de implementación · Presentación Slidev

> **Ejecución:** inline, en esta sesión. Sin subagentes y sin commits: en este repositorio no se
> commitea nada que el usuario no haya pedido explícitamente.

**Objetivo:** construir en `.slides/` una presentación Slidev de 25 diapositivas que explique Lead
Router en 25-30 minutos, según [SPEC.md](SPEC.md).

**Arquitectura:** un único `slides.md` con el contenido, un layout Vue propio (`layouts/blocked.vue`)
que impone cabecera, cuerpo y pie a todas las diapositivas, y una hoja de estilos (`style.css`) que
fija tipografía y densidad. Los diagramas son bloques Mermaid en línea, sin ficheros externos.

**Pila:** Slidev sobre Vue 3 y Vite. Node 24, npm 11. Mermaid viene incluido en Slidev.

## Restricciones globales

- Contenido en **español**, con acentos correctos. Los identificadores de código, en **inglés**.
- **Un elemento dominante por diapositiva**: un diagrama, una tabla o un bloque de código. Nunca dos.
- Todo dato citado —número de fichero, nombre de tabla, nombre de clase— tiene que existir en el
  repositorio. Nada inventado para que la frase quede redonda.
- Sin fuentes remotas en el frontmatter: el build no debe depender de que haya red.
- Sin `git add` ni `git commit` en ningún paso.

## Ficheros

| Fichero | Responsabilidad |
|---|---|
| `.slides/package.json` | Dependencias y los tres scripts: `dev`, `build`, `export` |
| `.slides/slides.md` | Las 25 diapositivas. Único fichero de contenido |
| `.slides/layouts/blocked.vue` | La plantilla común: cabecera con bloque, cuerpo, pie con idea clave |
| `.slides/layouts/portada.vue` | Variante para la diapositiva 1, sin cabecera ni pie |
| `.slides/style.css` | Tipografía, escala de los diagramas Mermaid, densidad de las tablas |
| `.slides/README.md` | Cómo se levanta y cómo se exporta |

---

### Tarea 1 · Scaffolding que compila

**Ficheros:**
- Crear: `.slides/package.json`, `.slides/slides.md`, `.slides/layouts/blocked.vue`,
  `.slides/layouts/portada.vue`, `.slides/style.css`

**Produce:** el layout `blocked`, que acepta dos props del frontmatter — `bloque` (texto de la
cabecera) e `idea` (texto del pie) — y el layout `portada`, sin props.

- [ ] **Paso 1: crear `package.json`**

```json
{
  "name": "leads-hexa-slides",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "slidev --open",
    "build": "slidev build",
    "export": "slidev export"
  }
}
```

- [ ] **Paso 2: instalar Slidev y fijar la versión resuelta**

Ejecutar: `cd .slides && npm install @slidev/cli @slidev/theme-default vue`
Esperado: `node_modules/` creado y las tres dependencias con su versión exacta en `package.json`.

- [ ] **Paso 3: escribir `layouts/blocked.vue`**

```vue
<script setup lang="ts">
defineProps<{ bloque?: string; idea?: string }>()
</script>

<template>
  <div class="slidev-layout blocked">
    <header class="blocked-head">
      <span class="blocked-tag">{{ bloque }}</span>
      <span class="blocked-num">{{ $slidev.nav.currentPage }} / {{ $slidev.nav.total }}</span>
    </header>
    <main class="blocked-body">
      <slot />
    </main>
    <footer class="blocked-foot" v-if="idea">{{ idea }}</footer>
  </div>
</template>
```

- [ ] **Paso 4: escribir `layouts/portada.vue`**

```vue
<template>
  <div class="slidev-layout portada">
    <slot />
  </div>
</template>
```

- [ ] **Paso 5: escribir `style.css`** con la retícula del layout —cabecera de 2.2rem, cuerpo
  elástico, pie de 2rem—, tablas a `0.78em`, y `.slidev-layout` sin el padding por defecto del tema.

- [ ] **Paso 6: escribir un `slides.md` mínimo** — portada más una diapositiva con el layout
  `blocked` y un diagrama Mermaid de tres nodos, para probar los dos layouts a la vez.

- [ ] **Paso 7: verificar que compila**

Ejecutar: `cd .slides && npm run build`
Esperado: termina en `0`, y `dist/index.html` existe.

---

### Tarea 2 · Bloque 1 · La idea (diapositivas 3-6)

**Ficheros:**
- Modificar: `.slides/slides.md`

**Consume:** el layout `blocked` de la tarea 1.

- [ ] **Paso 1: diapositiva 3 — qué es un lead y por qué falla el reparto manual.** Tabla de tres
  filas: lentitud, reparto injusto, leads perdidos, con lo que cuesta cada una.
  Fuente: `docs/content/vision/el-problema.md:25-29`.

- [ ] **Paso 2: diapositiva 4 — tres preguntas de naturaleza distinta.** Tabla con las columnas
  decisión, pregunta, naturaleza y respuesta que admite.
  Fuente: `docs/content/vision/modelo-de-decision.md:11-15`.

- [ ] **Paso 3: diapositiva 5 — qué pasa si se fuerzan en una sola puntuación.** Tabla de los dos
  trucos (restar 9999 para descartar, sumar 9999 para reservar un tramo) y por qué se rompen los dos
  igual. Fuente: `docs/content/vision/modelo-de-decision.md:33-42`.

- [ ] **Paso 4: diapositiva 6 — el pipeline en tres etapas.** Mermaid `flowchart TD` con las tres
  decisiones y sus dos salidas de escape (descalificado, sin asignar).
  Fuente: `docs/content/vision/modelo-de-decision.md:59-68`.

- [ ] **Paso 5: verificar que compila**

Ejecutar: `cd .slides && npm run build`
Esperado: termina en `0`, sin errores de Mermaid en la salida.

---

### Tarea 3 · Bloque 2 · De una empresa a muchas (diapositivas 7-11)

**Ficheros:**
- Modificar: `.slides/slides.md`

- [ ] **Paso 1: diapositiva 7 — el punto de partida.** Bloque SQL con el `CREATE TABLE
  scoring_rules` de `backend/migrations/001_baseline_schema.sql:20-31`, donde la regla tiene
  `field`, `operator` y `value` — **una sola condición inline** — junto a `routing_rules` con
  `target_team TEXT`. Al lado, la frase de qué significa: el criterio de negocio es una columna, y
  cambiarlo es una migración.

- [ ] **Paso 2: diapositiva 8 — la prueba que parte el dominio en dos.** Mermaid `flowchart TD`:
  «¿existe una organización razonable a la que esto no le aplique?» → sí, es regla del gestor; no,
  es invariante del dominio. Con los dos ejemplos: presupuesto negativo (invariante) y lead sin
  teléfono (regla). Fuente: `docs/content/vision/dominio-y-organizacion.md:24-46`.

- [ ] **Paso 3: diapositiva 9 — el catálogo.** Tabla a dos columnas: cuatro invariantes que se
  quedaron en el modelo frente a cuatro decisiones que se fueron a la interfaz. Se eligen las cuatro
  que más se parecen entre sí, para que la frontera se vea.
  Fuente: `docs/content/vision/dominio-y-organizacion.md:53-124`.

- [ ] **Paso 4: diapositiva 10 — la evolución, contada por las migraciones.** Mermaid `timeline` de
  `001` a `007` con lo que cada una movió de lado. Fuente: los ficheros de `backend/migrations/`.

- [ ] **Paso 5: diapositiva 11 — multitenancy real.** Mermaid `flowchart LR` del contexto de
  petición: el JWT entra, una dependencia deriva `tenant_id`, ningún caso de uso lo recibe del
  cliente; y las dos consecuencias — dos planos disjuntos y 404 en vez de 403.
  Fuente: ADR-0004, ADR-0003, ADR-0005.

- [ ] **Paso 6: verificar que compila**

Ejecutar: `cd .slides && npm run build`
Esperado: termina en `0`. Si `timeline` no renderiza, sustituir por `flowchart LR` con cinco nodos
encadenados y anotar el cambio en la respuesta.

---

### Tarea 4 · Bloque 3 · Cómo está estructurado (diapositivas 12-16)

**Ficheros:**
- Modificar: `.slides/slides.md`

- [ ] **Paso 1: diapositiva 12 — las tres capas.** Mermaid `flowchart LR` con los tres subgrafos y
  la flecha punteada de inversión de dependencias entre puerto de salida y adaptador.
  Fuente: `docs/content/arquitectura/index.md:51-71`.

- [ ] **Paso 2: diapositiva 13 — puertos y adaptadores.** Tabla de cinco filas puerto → adaptador
  (`LeadRepositoryPort` → `RawSqlLeadRepository`, `PasswordHasherPort` → `BcryptPasswordHasher`,
  `TokenServicePort` → `JwtTokenService`, `ClockPort` → `SystemClock`, `FileParserPort` →
  `PandasFileParser`), con la nota de que son 19 en total y el composition root los cablea.
  Fuente: `docs/content/arquitectura/c4-componentes.md:114-134`.

- [ ] **Paso 3: diapositiva 14 — el guardián.** Bloque Python con los cuatro nombres de test de
  `backend/tests/architecture/test_dependency_rule.py` y la explicación de por qué lee el AST en vez
  de importar el módulo. Fuente: ADR-0001 y `docs/content/arquitectura/index.md:83-98`.

- [ ] **Paso 4: diapositiva 15 — las tres etapas y sus tres motores.** Mermaid `flowchart TD` con
  `ViabilityEngine` (se detiene en la primera regla que se cumple), `ScoringEngine` (acumula todas)
  y `AssignmentEngine` (cascada de reglas por prioridad), y `Criterion` como pieza compartida.
  Fuente: `docs/content/modulos/reglas.md:70-79` y `arquitectura/recorrido-de-un-lead.md:81-134`.

- [ ] **Paso 5: diapositiva 16 — el lead como máquina de estados.** Mermaid `stateDiagram-v2` con
  los seis estados. Fuente: `docs/content/arquitectura/modelo-de-datos.md:270-286`.

- [ ] **Paso 6: verificar que compila**

Ejecutar: `cd .slides && npm run build`
Esperado: termina en `0`.

---

### Tarea 5 · Bloque 4 · Lo que salió mal (diapositivas 17-20)

**Ficheros:**
- Modificar: `.slides/slides.md`

- [ ] **Paso 1: diapositiva 17 — lo que entraba se perdía.** Tabla de las tres peticiones rotas con
  su respuesta y si dejaron registro: correo sin arroba → `202` y registro; presupuesto no numérico
  → `422` y nada; campo obligatorio ausente → `422` y nada. Más el detalle contraintuitivo: un
  presupuesto `-50` sí deja registro y un `"abc"` no.
  Fuente: `docs/content/otros/donde-se-valida-lo-que-entra.md:119-160`.

- [ ] **Paso 2: diapositiva 18 — la inversión.** Mermaid `sequenceDiagram` de cuatro participantes:
  quien envía, recepción, registro de entrada y procesamiento. La idea del pie: el servicio deja de
  escribir en el registro y pasa a leer de él.
  Fuente: `docs/content/otros/donde-se-valida-lo-que-entra.md:224-243` y ADR-0010.

- [ ] **Paso 3: diapositiva 19 — el umbral invisible.** Mermaid `flowchart LR` con dos ramas: antes,
  dos cortes de puntuación —uno fijo en el código, otro en las reglas del gestor— que nadie
  sincroniza; después, un solo corte, la banda más baja de las reglas de asignación.
  Fuente: ADR-0014.

- [ ] **Paso 4: diapositiva 20 — tres defectos con la misma causa.** Tabla: fuga cross-tenant por
  `tenant_id` en la URL; listado de asesores sin filtrar por organización; cursor de turnos que se
  reiniciaba porque vivía en una instancia que FastAPI recreaba en cada petición. La columna final
  nombra la causa común: un dato de confianza en manos de quien no debía tenerlo.
  Fuente: ADR-0004, ADR-0003 y `docs/content/arquitectura/c4-componentes.md:141-149`.

- [ ] **Paso 5: verificar que compila**

Ejecutar: `cd .slides && npm run build`
Esperado: termina en `0`.

---

### Tarea 6 · Bloque 5 · Python y el repositorio (diapositivas 21-24)

**Ficheros:**
- Modificar: `.slides/slides.md`
- Leer como referencia: `backend/src/domain/value_objects/criterion.py`,
  `backend/src/application/ports/output/`, `backend/src/infrastructure/di/container.py`

- [ ] **Paso 1: leer los tres ficheros de referencia** para copiar firmas reales, no aproximadas.
  Si una firma no coincide con lo que dice la documentación, gana el código y se anota en la
  respuesta final.

- [ ] **Paso 2: diapositiva 21 — el árbol de `backend/src/`.** Bloque de texto con el árbol a dos
  niveles y el recuento real: 149 ficheros Python, 88 de test, 8 migraciones.

- [ ] **Paso 3: diapositiva 22 — el dominio sin dependencias.** Bloque Python con `Criterion` y su
  lista blanca `EVALUABLE_FIELDS`, tomado de `criterion.py`. La idea del pie: el dominio sólo importa
  la biblioteca estándar, y hay un test que lo comprueba.

- [ ] **Paso 4: diapositiva 23 — el mismo concepto en tres ficheros.** Tres fragmentos cortos: el
  puerto ABC, el caso de uso que lo consume y el adaptador SQL que lo implementa, con la ruta de
  cada uno encima.

- [ ] **Paso 5: diapositiva 24 — cómo se valida.** Tabla de los tres comandos con lo que demuestra
  cada uno y su tiempo: suite completa (~45 s), `pytest -m unit` (~1 s, sin base de datos ni
  variables de entorno), `verify-e2e.sh` (~3 s, negocio sobre HTTP real).
  Fuente: `docs/content/desarrollo/validacion.md` y `CLAUDE.md`.

- [ ] **Paso 6: verificar que compila**

Ejecutar: `cd .slides && npm run build`
Esperado: termina en `0`.

---

### Tarea 7 · Cierre, README y revisión de datos

**Ficheros:**
- Modificar: `.slides/slides.md`
- Crear: `.slides/README.md`

- [ ] **Paso 1: diapositiva 25 — qué llevarse.** Tabla de cinco lecciones, cada una enunciada como
  afirmación y no como tema, más una fila final con lo que se dejó fuera a propósito
  (deduplicación, constructor visual de reglas, rango acotado de puntuación).

- [ ] **Paso 2: escribir `README.md`** con los tres comandos (`npm install`, `npm run dev`,
  `npm run build`), dónde tocar el contenido y dónde el estilo.

- [ ] **Paso 3: revisar los datos citados.** Recorrer el `slides.md` terminado y comprobar contra el
  repositorio cada número, nombre de fichero, nombre de clase y nombre de tabla. Cualquiera que no
  se pueda confirmar se corrige o se quita.

- [ ] **Paso 4: verificar el recuento de diapositivas**

Ejecutar: `rg -c '^---$' .slides/slides.md`
Esperado: coherente con 25 diapositivas.

- [ ] **Paso 5: build final**

Ejecutar: `cd .slides && npm run build`
Esperado: termina en `0`, `dist/` generado.

---

## Autorrevisión

**Cobertura del spec:** los seis puntos del encargo están cubiertos — idea (tarea 2), evolución
(tarea 3), arquitectura (tarea 4), problemas (tarea 5), Python y repo (tarea 6), cierre (tarea 7).
Los diagramas están repartidos por todas ellas: 10 diagramas Mermaid en las diapositivas 6, 8, 10,
11, 12, 15, 16, 18 y 19, más el de prueba de la tarea 1 que se sustituye por contenido real.

**Sin marcadores de posición:** cada paso nombra la fuente exacta —fichero y rango de líneas— de
donde sale su contenido. No hay ningún «rellenar después».

**Consistencia:** el layout se llama `blocked` en las siete tareas y sus dos props son `bloque` e
`idea` en todas. La verificación es siempre el mismo comando, `npm run build` desde `.slides/`.
