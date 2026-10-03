# ADR-0037 · Estructura y tamaño del código

| | |
|---|---|
| **Estado** | Aceptada. El backend heredado se reordenó al extraer cada contexto: las listas base del backend están vacías y se borraron. Sólo queda `scripts/structure_baseline.py`, de `test-consumer/` y `demo/` |
| **Fecha** | 2026-10-02 |
| **Ámbito** | Backend · `libs/chassis` · Tests |

## Contexto

El repositorio es docente: el árbol de ficheros tiene que dejar ver la arquitectura hexagonal, y los
diagramas que la describen, sin abrir un solo fichero. Hoy no lo consigue:

- El backend tiene **19 ficheros de más de 150 líneas** (`schemas.py` 497, `dependencies.py` 483,
  `commands.py` 412) y **7 carpetas de más de 12 ficheros** (`application/ports/output/` tiene 27, todos
  los contextos mezclados).
- El código nuevo de F1 ya nacía con el mismo patrón: `chassis/consumer.py` (260 líneas),
  `chassis/outbox.py` (209), `chassis/auth.py` (177) y `infrastructure/worker.py` (249).

Una regla escrita sin comprobación mecánica no frena eso: cada cambio añade «sólo unas líneas» al
fichero donde ya está lo parecido.

## Decisión

**La regla:**

- **Tamaño.** Como mucho **150 líneas físicas por fichero `.py` fuente**, con líneas en blanco y
  comentarios. Los tests no tienen límite de líneas.
- **Carpetas.** Como mucho **12 ficheros `.py` por carpeta**, sin contar `__init__.py` y sin contar
  las subcarpetas. **Vale también para los tests**: una carpeta con decenas de tests de conceptos
  mezclados se lee tan mal como una de fuentes. Se agrupa por concepto en subcarpetas; una carpeta por fichero sólo cuando el
  concepto lo pide.
- **Estructura de cada servicio:** `servicio → capa (domain | application | infrastructure) →
  contexto o responsabilidad`. Los tests reflejan la misma estructura.
- **Aislamiento de los tests de dominio.** Un fichero bajo `tests/unit/domain/` sólo importa el
  dominio, la biblioteca estándar, `pytest` y helpers que vivan dentro de `tests/unit/domain/`. Un
  import relativo se resuelve contra el fichero y falla si sale de ahí. Los imports dinámicos
  (`importlib`) no se detectan.
- **Partir no rompe a nadie.** Un módulo que se convierte en paquete reexporta sus nombres públicos
  desde `__init__.py`: `from chassis.outbox import OutboxRelay` sigue funcionando.

**Cómo se hace cumplir:**

- `chassis.testing` ofrece `assert_structure(root, *, max_lines=150, max_files=12, baseline)` y
  `assert_domain_tests_isolated(tests_root, domain_package)`. `max_lines=None` quita el límite de
  líneas y deja el de carpetas: así se miden los tests. Leen el árbol y la sintaxis, sin importar
  nada, así que corren sin base de datos ni variables de entorno.
- **Un punto de entrada en la raíz:** `scripts/verify-structure.sh` aplica la regla a cada raíz Python
  declarada (`backend/src`, `backend/tests`, `libs/chassis/src`, `libs/chassis/tests`,
  `test-consumer/`, `demo/`, `tools/`), cada una con su lista base, con
  `python -m chassis.testing check` y sin Docker.
- Además, cada servicio los llama desde su `tests/architecture/test_structure.py`, para que la suite
  no dependa de que alguien corra el script. `libs/chassis` se valida a sí mismo **sin lista base**.

**El backend existente no se reestructura ahora:**

- Sus incumplimientos están en listas base **generadas desde el árbol** con
  `python -m chassis.testing measure <raíz>`:
    - `backend/tests/architecture/structure_baseline.py`, de `backend/src`: 26 entradas, 19 ficheros
      con su número de líneas y 7 carpetas con su número de ficheros.
    - `backend/tests/architecture/tests_structure_baseline.py`, de `backend/tests`: 4 carpetas
      (`integration/` 30, `e2e/` 25, `unit/domain/` 19, `unit/application/` 18).
    - `scripts/structure_baseline.py`, de las raíces sin suite propia: `test-consumer/app.py` (556) y
      `demo/seed.py` (348).
- Las listas **sólo encogen**. El guardián falla si una entrada crece, si queda por encima de lo que mide
  el árbol (hay que bajarla) y si ya cumple el límite (hay que quitarla). Bajar o quitar entradas es
  parte del cambio que adelgaza el código.
- Cada contexto se reordena cuando se extrae a su servicio: identity en F3, intake en F4, el resto de
  lead-core residual en F5. La meta es que F5 termine con las listas del backend vacías.

**El código nuevo cumple desde ya.** En F1 se partieron los cuatro ficheros nuevos:
`chassis/consumer/`, `chassis/outbox/`, `chassis/auth/` e `infrastructure/worker/`. El arranque
`python -m infrastructure.worker` no cambia: el paquete tiene `__main__.py`. `worker/` es el nombre
del proceso worker de cada servicio; el consumidor de `intake.jobs`, que hasta ahora vivía en
`infrastructure/workers/`, pasa a su propio paquete `infrastructure/intake_worker/`
(`python -m infrastructure.intake_worker`) hasta que intake se extraiga en F4.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Reestructurar todo el backend ya | Mueve 19 ficheros y 7 carpetas que F3–F5 vuelven a mover al extraer cada contexto: doble trabajo y un diff enorme sin cambio de comportamiento en mitad de F1 |
| Aplicar la regla sólo al extraer cada contexto | Lo nuevo de F1 y F2 (chassis, `backend-worker`, notifications) nacería incumpliendo, y sería deuda desde el primer día |
| Lista base que sólo prohíbe crecer | Un fichero que baja de 300 a 200 líneas podría volver a 300 sin que nadie lo viera |
| Límite de complejidad (`ruff` C901 o similar) en vez de líneas | No dice nada de la anchura de las carpetas, que es lo que hace legible el árbol, y añade una herramienta |

## Consecuencias

**Fácil:**

- El árbol cuenta la arquitectura: `chassis/outbox/` se lee como `row`, `envelope`, `relay` y `kafka`
  antes de abrir nada.
- La regla se comprueba en menos de un segundo para todo el repositorio, sin infraestructura, y
  también dentro de la suite y de `pytest` en `libs/chassis`.
- La lista base deja medido lo que falta por ordenar, y cuánto, fase a fase.

**Difícil:**

- Partir un módulo añade imports y un `__init__.py` que reexporta, y una clase cohesiva puede rozar el
  límite: `ConsumerLoop` llega a 140 líneas después de sacar las llamadas a Kafka a `consumer/kafka.py`.
- Adelgazar un fichero o una carpeta heredados obliga a tocar su lista base en el mismo commit.
- Una raíz Python nueva no está cubierta hasta que se declara en `scripts/verify-structure.sh`.
- Nada impide editar la lista base para subir un valor. Lo detecta la revisión: es un diff de una
  línea en un fichero que sólo debería perder líneas.
- 150 y 12 son umbrales elegidos, no derivados. Se revisan con otro ADR si estorban más de lo que
  ayudan.

## Ver también

- [Convenciones · Estructura y tamaño del código](../desarrollo/convenciones.md#estructura-y-tamano-del-codigo)
- [ADR-0001 · Arquitectura hexagonal](0001-arquitectura-hexagonal.md)
- [ADR-0031 · Microservicios por contexto](0031-microservicios-por-contexto.md)
