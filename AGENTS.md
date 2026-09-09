# AGENTS.md

## Reglas del repositorio

- Código, comentarios y commits en inglés; documentación y textos de interfaz en español.
- No hagas commits salvo petición explícita. Formato: `type(scope): description`, sin
  `Co-authored-by`.
- Conserva cambios ajenos del worktree. No edites artefactos generados a mano.
- Reutiliza patrones existentes y limita el cambio a la responsabilidad pedida. No introduzcas un
  ORM, gestor de estado global, abstracciones especulativas ni dependencias evitables.

## Backend

- La dependencia apunta hacia dentro: `infrastructure -> application -> domain`.
- `domain` sólo usa la biblioteca estándar. `application` no importa frameworks, drivers ni
  `infrastructure`. Los cuatro tests AST son una barrera, no una recomendación.
- Los routers traducen HTTP; las decisiones viven en casos de uso o dominio. El cableado de casos
  de uso vive en `infrastructure/adapters/input/api/dependencies.py`; `Container` elige adaptadores y
  ciclos de vida.
- Crea un `UnitOfWork` por operación. No compartas transacciones ni conexiones de petición.
- PostgreSQL se usa con SQL crudo y parámetros `%s`; nunca interpolación de SQL. Las migraciones son
  numeradas, idempotentes y se aplican al arrancar. Para constraints sin `IF NOT EXISTS`, consulta
  `pg_constraint`.
- La organización siempre sale de la identidad verificada. Nunca aceptes `tenant_id` operativo en
  URL o body. Un recurso de otra organización responde 404 para no confirmar su existencia.
- No expongas hashes, secretos ni credenciales en respuestas, logs o eventos.

## Ingesta y mensajería

- Ingestar significa registrar primero y procesar después. Las filas quedan en `intake_records`
  antes de encolar; una caída no debe perder el payload recibido.
- RabbitMQ transporta trabajo efímero en `intake.jobs`. Mantén mensajes mínimos
  `{tenant_id, job_id}`, publicación durable, `ack` al terminar, `prefetch=1`, reentrega y DLQ. Si
  no se puede encolar, la API procesa en segundo plano; no rechaza el lead por la caída del broker.
- El worker ejecuta el mismo cableado de ingesta y suscribe también los handlers de notificaciones.
  La reentrega debe seguir siendo idempotente: procesa sólo registros `PENDING` y deriva contadores
  desde persistencia.
- Kafka es el canal saliente del producto. Los eventos se escriben en el outbox dentro de la misma
  transacción que el lead y se publican al topic `leads.{tenant_id}`, con `lead_id` como key.
- La entrega saliente es al menos una vez. Conserva `event_id`; los consumidores deduplican. No
  marques el outbox publicado hasta que todos los dispatchers confirmen.
- Kafka interno usa `kafka:9092`; clientes host usan `localhost:9094`; consumidores dentro de
  Compose usan `kafka:9095`. No mezcles direcciones anunciadas ni elimines las ACL por tenant.
- Los fallos iniciales de Kafka no bloquean la API: el relay reintenta. El healthcheck de RabbitMQ
  debe comprobar listeners (`check_port_connectivity`), no sólo el nodo Erlang.

## Frontend y contrato

- Flujo permitido: `presentation -> application -> domain`, con acceso a HTTP únicamente desde
  `infrastructure`. Las páginas llaman servicios de `application`, nunca `apiClient` directamente.
- `frontend/src/infrastructure/api/schema.d.ts` se genera con `npm run gen:api`; no se edita.
  Regenera después de cambiar OpenAPI.
- Las fixtures se capturan del backend real con `npm run gen:fixtures`; no inventes contratos en
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

Ejecuta la comprobación mínima que pueda fallar por tu cambio y amplía según el riesgo:

```bash
cd backend && uv run pytest -m unit -q
docker compose --profile test run --rm backend-test
cd frontend && npm run test && npm run build
./scripts/verify-e2e.sh
```

- La suite Docker es la prueba con PostgreSQL real. Para un subconjunto:
  `docker compose --profile test run --rm backend-test pytest -q <ruta>`.
- `backend/tests/conftest.py` fija las variables de test y descubre tablas para limpiarlas. No
  repitas configuración de entorno ni mantengas una lista manual de tablas.
- Cada bug deja una prueba que falla sin el arreglo. Prueba comportamiento y contratos, no detalles
  internos.
- `verify-e2e.sh` requiere la pila levantada y se amplía con una función nueva; no se reescribe. Usa
  `--reset` sólo cuando sea imprescindible, porque elimina los volúmenes.
- No reconstruyas imágenes por cambios bajo `src/`, `tests/` o `migrations/`: están montados. Haz
  build cuando cambien dependencias, lockfiles o Dockerfiles.
