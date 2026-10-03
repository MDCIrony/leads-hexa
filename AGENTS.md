# AGENTS.md

## Reglas del repositorio

- Código, comentarios y commits en inglés; documentación y textos de interfaz en español.
- No hagas commits salvo petición explícita. Formato: `type(scope): description`, sin
  `Co-authored-by`.
- Conserva cambios ajenos del worktree. No edites artefactos generados a mano.
- Reutiliza patrones existentes y limita el cambio a la responsabilidad pedida. No introduzcas un
  ORM, gestor de estado global, abstracciones especulativas ni dependencias evitables.

## Servicios Python

- La dependencia apunta hacia dentro: `infrastructure -> application -> domain`.
- `domain` sólo usa la biblioteca estándar. `application` no importa frameworks, drivers ni
  `infrastructure`. Los cuatro tests AST son una barrera, no una recomendación.
- Cuatro servicios (`services/identity`, `intake`, `lead-core`, `notifications`), cada uno con su
  base y su rol; ninguno lee la base de otro. Lo que necesitan de otro servicio llega por API interna
  (`/internal/v1/…`, con token de servicio), por evento o por una proyección local.
- Los routers traducen HTTP; las decisiones viven en casos de uso o dominio. El cableado de casos de
  uso vive en `infrastructure/adapters/input/api/use_case_factories.py` (en notifications,
  `dependencies.py`); `Container` sólo elige adaptadores y ciclos de vida. `libs/chassis` es sólo
  técnico y sólo se importa desde `infrastructure`.
- Crea un `UnitOfWork` por operación. No compartas transacciones ni conexiones de petición.
- PostgreSQL se usa con SQL crudo y parámetros `%s`; nunca interpolación de SQL. Las migraciones son
  numeradas, idempotentes y se aplican al arrancar. Para constraints sin `IF NOT EXISTS`, consulta
  `pg_constraint`.
- La organización siempre sale de la identidad verificada. Nunca aceptes `tenant_id` operativo en
  URL o body. Un recurso de otra organización responde 404 para no confirmar su existencia.
- No expongas hashes, secretos ni credenciales en respuestas, logs o eventos.

## Ingesta y mensajería

- Toda publicación pasa por el outbox del servicio: la fila se escribe en la misma transacción que el
  cambio y el relay del `worker` la entrega. Canales: `product` (Kafka `leads.{tenant_id}` y
  webhooks), `internal` (Kafka `internal.<servicio>.*`) y `job` (RabbitMQ `intake.jobs`). La API
  nunca habla con un broker.
- La entrega es al menos una vez. Conserva `event_id`; los consumidores deduplican
  (`processed_events`) o aplican por `version` (proyecciones). Una fila sólo se marca publicada
  cuando el broker confirma.
- Ingestar es registrar primero y decidir después. intake guarda job, registros y fichero antes de
  encolar; el `intake-worker` procesa cada registro llamando a `POST /internal/v1/admissions` de
  lead-core, que es idempotente por `(tenant_id, intake_record_id)`. No abras una transacción
  durante esa llamada.
- `intake.jobs`: cola quórum, `prefetch=1`, `ack` al terminar, `nack` con espera si lead-core no
  responde, DLQ tras tres entregas y reproceso por la API. Un dato inválido es `REJECTED`, nunca un
  5xx: un 5xx determinista bloquea el job entero.
- Los contratos entre servicios (OpenAPI interno, eventos, mensaje de la cola) viven en `contracts/`
  y los prueban las dos partes con sus fixtures.
- Kafka dentro de Compose: `kafka:9092`; clientes del host: `localhost:9094` (SASL); consumidores
  externos dentro de Compose: `kafka:9095` (SASL). No mezcles direcciones anunciadas ni elimines las
  ACL por tenant.

## Frontend y contrato

- Flujo permitido: `presentation -> application -> domain`, con acceso a HTTP únicamente desde
  `infrastructure`. Las páginas llaman servicios de `application`, nunca `apiClient` directamente.
- `frontend/src/infrastructure/api/*schema.d.ts` (lead-core, identity, intake, notifications) se
  generan con `npm run gen:api` desde el gateway; no se editan. Regenera después de cambiar OpenAPI.
- Las fixtures se capturan de la API real con `npm run gen:fixtures`; no inventes contratos en
  JSON de test.
- Estado de servidor en hooks, sesión en su contexto, formulario en el formulario y estado visual
  en el componente. No dupliques estado ni agregues un store global.
- Usa Tailwind, `lucide-react` y las primitivas `Button`, `Input`, `Field`. Mantén foco visible,
  labels asociados y `aria-label` en botones sólo-icono. No agregues CSS por componente.
- No uses `any`, `@ts-ignore` sin justificación, `console.log` ni esperas fijas. La ingesta responde
  202: sondea el job hasta un estado terminal con límite.
- Conserva el sobre paginado `{items,total,limit,offset,has_more}` y el sobre de error
  `{error,error_code,message}`. Un 403 no cierra sesión; un 404 no se reinterpretará como 403.

## Documentación

- Consulta `docs/content/decisiones/` antes de cambiar una decisión y `docs/content/roadmap/` antes
  de tratar una exclusión como defecto.
- Un cambio observable de API actualiza su referencia en el mismo diff.
- Crea un ADR sólo para una decisión transversal, una incompatibilidad de contrato o una elección
  con alternativas razonables. Si sustituye otro ADR, márcalo y agrega el nuevo al `nav` de MkDocs.

## Validación

Ejecuta la comprobación mínima que pueda fallar por tu cambio y amplía según el riesgo. `<svc>` es
`lead-core`, `identity`, `intake` o `notifications`:

```bash
cd services/<svc> && uv run pytest -m unit -q
docker compose --profile test run --rm <svc>-test
./scripts/verify-structure.sh
cd frontend && npm run test && npm run build
./scripts/verify-e2e.sh
```

- La suite Docker es la prueba con PostgreSQL real. Para un subconjunto:
  `docker compose --profile test run --rm <svc>-test pytest -q <ruta>`.
- `tests/conftest.py` de cada servicio fija las variables de test y descubre tablas para limpiarlas. No
  repitas configuración de entorno ni mantengas una lista manual de tablas.
- Cada bug deja una prueba que falla sin el arreglo. Prueba comportamiento y contratos, no detalles
  internos.
- `verify-e2e.sh` requiere la pila levantada y se amplía con una función nueva; no se reescribe. Usa
  `--reset` sólo cuando sea imprescindible, porque elimina los volúmenes.
- No reconstruyas imágenes por cambios bajo `src/`, `tests/` o `migrations/`: están montados. Haz
  build cuando cambien dependencias, lockfiles o Dockerfiles.
