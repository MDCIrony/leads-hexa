# ADR-0037 · Estructura y tamaño del código

| | |
|---|---|
| **Estado** | Aceptada · F1. El backend heredado se reordena al extraer cada contexto (F3, F4, F5) |
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
  comentarios. Los tests no tienen límite.
- **Carpetas.** Como mucho **12 ficheros `.py` por carpeta**, sin contar `__init__.py` y sin contar
  las subcarpetas. Se agrupa por concepto en subcarpetas; una carpeta por fichero sólo cuando el
  concepto lo pide.
- **Estructura de cada servicio:** `servicio → capa (domain | application | infrastructure) →
  contexto o responsabilidad`. Los tests reflejan la misma estructura.
- **Aislamiento de los tests de dominio.** Un fichero bajo `tests/unit/domain/` sólo importa el
  dominio, la biblioteca estándar, `pytest` y helpers que vivan dentro de `tests/unit/domain/`.
- **Partir no rompe a nadie.** Un módulo que se convierte en paquete reexporta sus nombres públicos
  desde `__init__.py`: `from chassis.outbox import OutboxRelay` sigue funcionando.

**Cómo se hace cumplir:**

- `chassis.testing` ofrece `assert_structure(root, *, max_lines=150, max_files=12, baseline)` y
  `assert_domain_tests_isolated(tests_root, domain_package)`. Leen el árbol y la sintaxis, sin
  importar nada, así que corren sin base de datos ni variables de entorno.
- Cada servicio los llama desde su `tests/architecture/test_structure.py`. `libs/chassis` se valida a
  sí mismo **sin lista base**.

**El backend existente no se reestructura ahora:**

- Sus incumplimientos están en `backend/tests/architecture/structure_baseline.py`, **generada desde el
  árbol** con `uv run python -m chassis.testing src`: 26 entradas, 19 ficheros con su número de
  líneas y 7 carpetas con su número de ficheros.
- La lista **sólo encoge**. El guardián falla si una entrada crece, si queda por encima de lo que mide
  el árbol (hay que bajarla) y si ya cumple el límite (hay que quitarla). Bajar o quitar entradas es
  parte del cambio que adelgaza el código.
- Cada contexto se reordena cuando se extrae a su servicio: identity en F3, intake en F4, el resto de
  lead-core residual en F5. La meta es que F5 termine con la lista vacía.

**El código nuevo cumple desde ya.** En F1 se partieron los cuatro ficheros nuevos:
`chassis/consumer/`, `chassis/outbox/`, `chassis/auth/` e `infrastructure/worker/`. El arranque
`python -m infrastructure.worker` no cambia: el paquete tiene `__main__.py`.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Reestructurar todo el backend ya | Mueve 19 ficheros y 7 carpetas que F3–F5 vuelven a mover al extraer cada contexto: doble trabajo y un diff enorme sin cambio de comportamiento en mitad de F1 |
| Aplicar la regla sólo al extraer cada contexto | Lo nuevo de F1 y F2 (chassis, `backend-worker`, notifications) nacería incumpliendo, y sería deuda desde el primer día |
| Lista base que sólo prohíbe crecer | Un fichero que baja de 300 a 200 líneas podría volver a 300 sin que nadie lo viera |
| Límite de complejidad (`ruff` C901 o similar) en vez de líneas | No dice nada de la anchura de las carpetas, que es lo que hace legible el árbol, y añade una herramienta |

## Consecuencias

**Fácil:**

- El árbol cuenta la arquitectura: `chassis/outbox/` se lee como `envelope`, `relay` y `kafka` antes de
  abrir nada.
- La regla se comprueba en milésimas, dentro de la suite y de `pytest` en `libs/chassis`, sin
  infraestructura.
- La lista base deja medido lo que falta por ordenar, y cuánto, fase a fase.

**Difícil:**

- Partir un módulo añade imports y un `__init__.py` que reexporta, y una clase cohesiva puede rozar el
  límite: `ConsumerLoop` llega a 140 líneas después de sacar las llamadas a Kafka a `consumer/kafka.py`.
- Adelgazar un fichero heredado obliga a tocar la lista base en el mismo commit.
- Nada impide editar la lista base para subir un valor. Lo detecta la revisión: es un diff de una
  línea en un fichero que sólo debería perder líneas.
- 150 y 12 son umbrales elegidos, no derivados. Se revisan con otro ADR si estorban más de lo que
  ayudan.

## Ver también

- [Convenciones · Estructura y tamaño del código](../desarrollo/convenciones.md#estructura-y-tamano-del-codigo)
- [ADR-0001 · Arquitectura hexagonal](0001-arquitectura-hexagonal.md)
- [ADR-0031 · Microservicios por contexto](0031-microservicios-por-contexto.md)
