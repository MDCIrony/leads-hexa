# Cómo contribuir

Flujo de contribución, tanto para el equipo como para quien llega de fuera.

## Ramas

`main` es la rama estable. El trabajo se hace en una rama propia a partir de `main`, con un nombre
que diga qué contiene — no hace falta un prefijo fijo (`feature/`, `fix/`…), pero sí que se
entienda sin abrir el diff.

## Antes de abrir una propuesta de cambio

Los cinco comandos de [Validación](validacion.md) sobre el cambio completo:

```bash
docker compose --profile test run --rm lead-core-test
cd services/lead-core && uv run pytest -m unit -q
./scripts/verify-e2e.sh
./scripts/verify-structure.sh
cd bruno && bru run flows --env local -r
```

Los cuatro tests de arquitectura de cada servicio deben seguir en 4/4, y los guardianes de estructura
(`tests/architecture/test_structure.py` y `verify-structure.sh`, [ADR-0037](../decisiones/0037-estructura-y-tamano-del-codigo.md))
en verde: un fichero fuente de más de 150 líneas, una carpeta de más de 12 ficheros —también de
tests— o una entrada de lista base que crece (sólo queda la de `test-consumer/`) hacen fallar el cambio. Si el cambio toca `scripts/verify-e2e.sh`, se
amplía —una función `verify_fN` nueva, llamada desde `main`— y no se reescribe: las comprobaciones
anteriores son la prueba de que lo que ya funcionaba sigue funcionando.

## Cómo se revisa

- El diff explica el porqué del cambio, no sólo el qué — ver
  [Convenciones](convenciones.md).
- Un cambio de comportamiento observable desde la API se refleja en
  [API · Referencia](api-referencia.md) o [API · Errores](api-errores.md) en el mismo cambio, no en
  uno posterior: una referencia desactualizada cuesta más de lo que ahorra escribirla después.
- Un cambio que rompe una de las invariantes del sistema —la organización sale siempre del token,
  un recurso ajeno responde 404 y no 403, SQL crudo sin ORM, migraciones idempotentes— se justifica
  explícitamente o se revierte. No es una preferencia de estilo.

## Cuándo hace falta un ADR nuevo

Un ADR documenta una decisión de diseño con alternativas reales y sus consecuencias, no cualquier
cambio. Hace falta uno nuevo cuando el cambio:

- Introduce o retira una regla que cruza capas — por ejemplo, qué puede importar el dominio.
- Cambia el contrato de la API de forma incompatible: un código de estado, la forma de una
  respuesta.
- Elige entre alternativas donde la que no se tomó es razonable, y alguien va a proponerla de nuevo
  si no queda escrito por qué se descartó.

Un cambio que sólo implementa una decisión ya tomada en un ADR existente no necesita uno nuevo: se
enlaza al que ya existe.

### Cómo se escribe

Se numera correlativo al último de [Decisiones](../decisiones/index.md)
(`NNNN-titulo-en-minusculas.md`) y sigue la misma estructura que los anteriores: contexto, decisión,
alternativas consideradas y por qué se descartaron, consecuencias. Se enlaza desde `docs/mkdocs.yml`
(la sección `Decisiones` del `nav`) en el mismo cambio que lo añade — un ADR que no aparece en la
navegación no lo encuentra nadie.

## Cómo se edita esta documentación

El sitio es MkDocs con el tema Material, y se sirve desde el propio `compose`:

```bash
docker compose up docs
```

en [http://localhost:8002](http://localhost:8002). El contenido vive en `docs/content/` y se monta
como volumen de sólo lectura: un cambio en un fichero `.md` se ve en el navegador al guardar, sin
reconstruir el contenedor. La navegación se edita a mano en `docs/mkdocs.yml` (clave `nav`) — una
página nueva que no se añade ahí no aparece en el sitio, aunque el fichero exista.

Convenciones del contenido: español con ortografía completa, encabezados con mayúscula sólo en la
primera palabra, enlaces relativos con extensión `.md`, diagramas en Mermaid sin colores fijos —el
sitio tiene modo claro y modo oscuro, y un color fijo se vuelve ilegible en uno de los dos.

Antes de proponer un cambio en la documentación, comprueba que el sitio construye sin avisos:

```bash
docker compose run --rm docs mkdocs build --strict
```

El modo estricto convierte en error cualquier enlace roto y cualquier página que falte en el `nav`.
Es la misma comprobación que conviene tener en integración continua.

!!! note "Los diagramas necesitan red la primera vez"
    El tema carga Mermaid desde `unpkg.com` cuando la página tiene diagramas, y el navegador lo
    guarda en caché a partir de ahí. Sin salida a internet los bloques aparecen como texto en vez de
    dibujarse: el contenido se lee igual, pero conviene saberlo antes de una demostración.

## Para quien llega de fuera

El flujo es el habitual de un proyecto abierto: bifurcar el repositorio, trabajar en una rama
propia y abrir una propuesta de cambio contra `main` cuando los cinco comandos de validación pasan.
La revisión sigue los mismos criterios que para el equipo interno.
