# Cómo se trabaja en este repositorio

MVP docente de enrutamiento de leads. Backend FastAPI, frontend React, PostgreSQL con SQL crudo,
arquitectura hexagonal.

## La documentación es la fuente

Vive en `docs/`, como subproyecto MkDocs Material, y se levanta con `docker compose up -d docs` en
<http://localhost:8002>. El fuente está en `docs/content/`.

| Antes de… | Lee |
|---|---|
| Tocar una capa o mover una responsabilidad | `docs/content/arquitectura/` |
| Cambiar el comportamiento de un módulo | `docs/content/modulos/` |
| Discutir por qué algo está hecho así | `docs/content/decisiones/` — 21 ADRs |
| Proponer una capacidad nueva | `docs/content/roadmap/` |
| Escribir un endpoint | `docs/content/desarrollo/api-referencia.md` |

**Una decisión de arquitectura nueva se documenta como ADR** en `docs/content/decisiones/`, con su
contexto, sus alternativas y sus consecuencias, y se añade al `nav` de `docs/mkdocs.yml`. Un cambio
que contradiga un ADR vigente no se aplica en silencio: se sustituye el ADR y se marca el anterior
como sustituido.

Las carpetas `docs/specs/` y `docs/plans/` **ya no existen**. Su contenido vive destilado en las
secciones de arriba; lo que era instrucción de ejecución se retiró a propósito.

## Validación

Tres comandos. **Ninguno necesita `--build` ni `restart`**: el código y los tests van montados como
volúmenes, y la API recarga en caliente lo que cambie en `src/`. Sólo se reconstruye si cambian
`pyproject.toml`, `uv.lock` o el `Dockerfile`.

```bash
docker compose --profile test run --rm backend-test    # suite completa     ~4 min
cd backend && uv run pytest -m unit -q                 # dominio aislado    ~1 s
./scripts/verify-e2e.sh                                # negocio sobre HTTP ~3 s
```

Cada uno demuestra algo que los otros no:

- **La suite** cubre todas las capas, incluida la persistencia real.
- **`pytest -m unit`** corre **sin base de datos y sin variables de entorno**. Si empieza a fallar
  fuera de Docker, se ha infiltrado una dependencia de infraestructura en el dominio.
- **`verify-e2e.sh`** recorre el negocio sobre HTTP real. Los tests pueden estar verdes con el
  producto roto; esto no.

Dentro de la suite viajan cuatro tests que analizan el AST y fallan si el dominio importa algo de
fuera o la aplicación importa infraestructura. **Deben estar siempre 4/4.**

`verify-e2e.sh` se **amplía, nunca se reescribe**: cada fase añade su función `verify_fN` y la llama
desde `main`. No necesita base limpia salvo que una migración lo exija, y entonces se pasa `--reset`.

**Por qué importa.** Es lo que permite aceptar trabajo sin releer el diff entero: un agente afirma
que terminó, y el harness dice si es verdad.

### Trampas que ya han costado tiempo

- `docker compose run` **reemplaza** el CMD, no lo extiende. Para un subconjunto:
  `run --rm backend-test pytest -q <ruta>`.
- Ningún fichero de test declara `DATABASE_URL` ni `JWT_SECRET`. Los fija `conftest.py` una sola vez
  antes de importar nada. Copiar un preámbulo `os.environ.setdefault(...)` de otro fichero
  reintroduce un fallo que depende del orden de importación.
- La limpieza entre tests lee las tablas del catálogo: una tabla nueva se trunca sola, no hay lista
  que mantener.
- El cableado de casos de uso vive en el módulo de dependencias de la API, no en el contenedor de
  inyección.
- `rm` es interactivo en este equipo; usar `rm -f`.

## Reparto del trabajo entre agentes

El trabajo se ejecuta por tareas, una por subagente, cada una con su commit. Sin estas reglas un
ejecutor gasta la mayor parte de su presupuesto leyendo antes de escribir una línea.

1. **El encargo es la fuente de requisitos**, y lleva dentro lo que hay que construir. El subagente
   no explora el repositorio para entender *qué* hacer, sólo para ver *cómo* encaja. Si el encargo no
   cuadra con el código, eso *es* un hallazgo: se aplica con criterio y se reporta.
2. **Lista cerrada de ficheros** en cada despacho, separando los que modifica de los que sólo lee
   como patrón. Abrir uno fuera de la lista sin motivo es un fallo de la tarea.
3. **Excepción reactiva, y sólo reactiva.** Si un test falla en un fichero no listado, o falta un
   dato concreto para escribir algo fiel, se abre y se declara. Si en dos o tres lecturas no
   aparece, **se para y se reporta** en vez de inventar un sustituto que rebaje lo que la prueba
   demuestra. Lo prohibido es el reconocimiento general sin una pregunta delante.
4. **Los hallazgos van en la respuesta**, no enterrados en un fichero de informe. Un arreglo que
   sólo aparece en un informe obliga a revisar el diff entero, que es justo lo que el harness evita.
5. **Quien orquesta revalida** con `verify-e2e.sh`, sin repetir la suite que el subagente ya corrió.

## Invariantes

Romper cualquiera es un defecto, no una preferencia de estilo.

| | |
|---|---|
| **Guardián 4/4** | El dominio no importa nada fuera de la biblioteca estándar; la aplicación no importa infraestructura ni frameworks web |
| **La organización sale del token** | Nunca de la URL ni del cuerpo de la petición |
| **404, no 403** | Al leer una entidad de otra organización. Un 403 confirma que existe |
| **SQL crudo, sin ORM** | Marcadores `%s` de psycopg, sin f-strings en consultas |
| **Migraciones idempotentes** | La suite las reejecuta a propósito. `CREATE TABLE` y `ADD COLUMN` con `IF NOT EXISTS`; `ADD CONSTRAINT` no admite esa sintaxis y necesita guarda manual contra `pg_constraint` |
| **Idioma** | Código, comentarios y mensajes de commit en inglés. Documentación, en español |
| **Comentarios** | Explican el **porqué**, nunca el qué. Uno que narra la línea siguiente sobra |
| **Commits** | `type(scope): description`, sin `Co-authored-by`. Nunca commitear sin que se pida explícitamente |

## Alcance

Es un MVP con finalidad docente acotada. Varias capacidades que parecen faltar —deduplicación de
contactos, constructor visual de reglas, rango acotado de puntuación— se discutieron y se dejaron
fuera **a propósito**, cada una con su razón escrita en `docs/content/roadmap/`.

Antes de proponer una de ellas como si fuera un olvido, conviene mirar ahí.
