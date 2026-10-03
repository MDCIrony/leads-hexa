# Cómo se trabaja en este repositorio

MVP docente de enrutamiento de leads: cuatro servicios FastAPI con arquitectura hexagonal detrás de un
gateway nginx, frontend React, PostgreSQL con SQL crudo (una base y un rol por servicio), Kafka y
RabbitMQ.

## Mapa

| Ruta | Qué es |
|---|---|
| `services/identity/` | Sesiones, MFA, OAuth, organizaciones, agentes, credenciales de integración; firma el token interno y los tokens de servicio |
| `services/intake/` | Fuentes, recepción, jobs, registros, ficheros y la cola `intake.jobs` |
| `services/lead-core/` | Decisión (descarte, puntuación, asignación), leads, reglas, grupos, asesores, webhooks, canal de producto |
| `services/notifications/` | Bandeja de notificaciones |
| `libs/chassis/` | Sólo técnico: verificación de tokens, outbox, consumidor Kafka, persistencia, correlación, helpers de test |
| `contracts/` | OpenAPI interno, esquemas de eventos y fixtures que prueban las dos partes de cada interfaz |
| `gateway/` · `db/` | nginx (rutas y phantom token) · arranque de roles y bases |
| `frontend/` · `bruno/` · `test-consumer/` | Interfaz · flujos HTTP como cliente · aplicación consumidora de ejemplo |

Cada servicio son dos procesos de la misma imagen: `api` y `worker`, que publica el outbox y consume
de los brokers. Puertos en el host: aplicación <http://localhost>, API por el gateway `:8001`, docs
`:8002`, Kafka UI `:8004`, RabbitMQ `:15672`, PostgreSQL `:5433`.

## La documentación es la fuente

Vive en `docs/`, como subproyecto MkDocs Material, y se levanta con `docker compose up -d docs` en
<http://localhost:8002>. El fuente está en `docs/content/`; `docs/mkdocs.yml` va dentro de la imagen,
así que un cambio de `nav` necesita `docker compose up -d --build docs`.

| Antes de… | Lee |
|---|---|
| Tocar una capa o mover una responsabilidad | `docs/content/arquitectura/` |
| Cambiar la comunicación entre servicios o un contrato interno | `docs/content/microservices/` |
| Cambiar el comportamiento de un módulo | `docs/content/modulos/` |
| Discutir por qué algo está hecho así | `docs/content/decisiones/`: 37 ADR |
| Proponer una capacidad nueva | `docs/content/roadmap/` |
| Escribir un endpoint | `docs/content/desarrollo/api-referencia.md` |

**Una decisión de arquitectura nueva se documenta como ADR** en `docs/content/decisiones/`, con su
contexto, sus alternativas y sus consecuencias, y se añade al `nav` de `docs/mkdocs.yml`. Un cambio
que contradiga un ADR vigente no se aplica en silencio: se sustituye el ADR y se marca el anterior
como sustituido.

## Validación

**No hace falta `--build` ni `restart`** para cambios en `src/`, `tests/` o `migrations/`: van
montados y `watchfiles` reinicia cada proceso. Sólo se reconstruye si cambian `pyproject.toml`,
`uv.lock` o un `Dockerfile`.

```bash
docker compose --profile test run --rm <svc>-test     # suite del servicio con su base *_test
cd services/<svc> && uv run pytest -m unit -q         # dominio y aplicación, sin base ni entorno ~1 s
./scripts/verify-e2e.sh                               # el negocio entero sobre HTTP real      ~6 min
./scripts/verify-structure.sh                         # regla de estructura, todo el repo       ~1 s
cd bruno && bru run flows --env local -r              # el contrato como lo ve un cliente      ~10 s
cd libs/chassis && uv run pytest -q -W error          # cuando se toca chassis
cd frontend && npm test && npm run build              # cuando se toca el frontend
```

`<svc>` es `lead-core`, `identity`, `intake` o `notifications`. Un cambio se prueba en la suite del
servicio que es dueño de la ruta: `/auth`, `/tenants` y `/agents` son de identity; `/sources` e
`/intake`, de intake; `/notifications`, de notifications; el resto de `/api/v1`, de lead-core.

Cada comando demuestra algo que los otros no:

- **La suite** cubre todas las capas, incluida la persistencia real, y los tests de contrato contra
  `contracts/`.
- **`pytest -m unit`** corre **sin base de datos y sin variables de entorno**. Si empieza a fallar
  fuera de Docker, se ha infiltrado una dependencia de infraestructura en el dominio.
- **`verify-e2e.sh`** recorre el negocio sobre HTTP real y comprueba la separación (rutas por
  servicio, roles por base, colas, topics, consumidores). Los tests pueden estar verdes con el
  producto roto; esto no. `--reset` recrea los volúmenes y borra todos los datos.
- **`verify-structure.sh`** aplica la regla de estructura (ADR-0037) a todas las raíces Python, sin
  Docker: `src` y `tests` de cada servicio y de `libs/chassis`, `test-consumer/` y `tools/`. Una
  raíz Python nueva se declara ahí; una que no existe cuenta como fallo.
- **`bru run flows`** recorre los seis flujos de `bruno/flows/` contra el gateway, con una sesión por
  cookie por rol. Las carpetas de referencia no entran.

Dentro de la suite de cada servicio viajan cuatro tests que analizan el AST y fallan si el dominio
importa algo fuera de la biblioteca estándar o la aplicación importa infraestructura. **Deben estar
siempre 4/4.** A su lado, `tests/architecture/test_structure.py` aplica la regla de estructura con
los helpers de `chassis.testing`. Ningún servicio tiene lista base; sólo `test-consumer/` la tiene,
en `scripts/structure_baseline.py`, y **sólo encoge** (`cd libs/chassis && uv run python -m
chassis.testing measure <raíz>` imprime los valores).

`verify-e2e.sh` se **amplía, nunca se reescribe**: un cambio de comportamiento añade su función de
comprobación y la llama desde `main`.

**Por qué importa.** Es lo que permite aceptar trabajo sin releer el diff entero: un agente afirma
que terminó, y el harness dice si es verdad.

### Trampas que ya han costado tiempo

- `docker compose run` **reemplaza** el CMD, no lo extiende. Para un subconjunto:
  `run --rm lead-core-test pytest -q <ruta>`.
- Ningún fichero de test declara las variables de entorno de su servicio: las fija
  `tests/conftest.py` una sola vez antes de importar nada. Copiar un preámbulo
  `os.environ.setdefault(...)` reintroduce un fallo que depende del orden de importación.
- La limpieza entre tests lee las tablas del catálogo: una tabla nueva se trunca sola.
- El cableado de casos de uso vive en la capa de entrada: `api/use_case_factories.py` en identity,
  intake y lead-core (intake comparte con su worker `infrastructure/di/use_cases.py`) y
  `api/dependencies.py` en notifications. Nunca en el `Container`, que sólo elige adaptadores y
  ciclos de vida.
- Las APIs de desarrollo arrancan con `watchfiles`, no con `uvicorn --reload`: el recargador entrega
  el socket por descriptor y deja las conexiones sin `TCP_NODELAY` (≈ 40 ms por llamada interna).
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
   demuestra.
4. **Los hallazgos van en la respuesta**, no enterrados en un fichero de informe.
5. **Quien orquesta revalida** con `verify-e2e.sh`, sin repetir la suite que el subagente ya corrió.
6. **Ficheros compartidos, un solo dueño:** `docker-compose.yml`, `gateway/`, `db/`, `contracts/`,
   `libs/chassis/`, `scripts/` y `CLAUDE.md` los cambia quien orquesta.

## Invariantes

Romper cualquiera es un defecto, no una preferencia de estilo.

| | |
|---|---|
| **Guardián 4/4** | El dominio no importa nada fuera de la biblioteca estándar; la aplicación no importa infraestructura ni frameworks web; `chassis` sólo desde `infrastructure` |
| **Estructura** | Fichero `.py` fuente ≤ 150 líneas (los tests, sin límite de líneas); carpeta ≤ 12 ficheros `.py`, fuentes y tests; `servicio → capa → contexto`; un test de `tests/unit/domain/` sólo importa dominio, stdlib, `pytest` y sus propios helpers; dentro de un servicio, sin reexportaciones de compatibilidad |
| **Una base por servicio** | Ningún servicio lee la base de otro: lo que necesita llega por API interna, evento o proyección local |
| **Toda publicación pasa por el outbox** | En la misma transacción que el cambio; el relay del worker la entrega y los consumidores deduplican por `event_id` |
| **La organización sale del token** | Nunca de la URL ni del cuerpo de la petición |
| **404, no 403** | Al leer una entidad de otra organización. Un 403 confirma que existe |
| **SQL crudo, sin ORM** | Marcadores `%s` de psycopg, sin f-strings en consultas |
| **Migraciones idempotentes** | La suite las reejecuta a propósito. `CREATE TABLE` y `ADD COLUMN` con `IF NOT EXISTS`; `ADD CONSTRAINT` necesita guarda manual contra `pg_constraint` |
| **Contratos** | Un cambio de un cuerpo interno o de un evento se hace en `contracts/` y lo prueban las dos partes; incompatible = fichero `v2` |
| **Idioma** | Código, comentarios y mensajes de commit en inglés. Documentación, en español |
| **Comentarios** | Explican el **porqué**, nunca el qué. Uno que narra la línea siguiente sobra |
| **Commits** | `type(scope): description`, sin `Co-authored-by`. Nunca commitear sin que se pida explícitamente |

## Alcance

Es un MVP con finalidad docente acotada. Varias capacidades que parecen faltar —deduplicación de
contactos, constructor visual de reglas, rango acotado de puntuación, panel del gestor— se
discutieron y se dejaron fuera **a propósito**, cada una con su razón escrita en
`docs/content/roadmap/`.

Antes de proponer una de ellas como si fuera un olvido, conviene mirar ahí.
