# chassis

Infraestructura transversal compartida por todos los servicios de Lead Router: verificación del
token interno (Ed25519, ADR-0032) y correlación de peticiones por `X-Request-ID`.

- `chassis.auth`: `Ed25519Signer`, `JwksCache`, `TokenVerifier`, `Claims`.
- `chassis.web`: `RequestIdMiddleware` (ASGI puro), `RequestIdLogFilter`, `configure_logging`.
- `chassis.outbox`: `OutboxRelay` (un carril por canal: `product`, `internal`, `job`), `run_relay`,
  `envelope`, `KafkaEventDispatcher`. No importa ningún broker; los productores se inyectan.
- `chassis.consumer`: `Envelope`, `ConsumerLoop` (reintentos con backoff y DLQ
  `internal.dlq.<grupo>`), `ensure_topics`, `TopicSpec`. El consumidor se crea con
  `enable.auto.commit=false` y `auto.offset.reset=earliest`.
- `chassis.rabbit`: `RabbitJobDispatcher` (publica con *confirms*, `mandatory` y persistente).
- `chassis.testing`: `assert_structure` y `assert_domain_tests_isolated`, los guardianes de estructura
  (ADR-0037) que cada servicio llama desde `tests/architecture/`. `python -m chassis.testing measure <raíz>`
  imprime la lista base de un árbol y `check <raíz>` la aplica; `scripts/verify-structure.sh` la usa
  para todo el repositorio.

## Extras

Cada servicio instala sólo el cliente que usa:

| Extra | Instala | Lo necesita |
|---|---|---|
| `kafka` | `confluent-kafka` | `ensure_topics` y `ConsumerLoop.run` (importan `confluent_kafka` al usarse); los productores y consumidores que se inyectan |
| `rabbit` | `pika` | `chassis.rabbit` |

## Regla de uso

Sólo se importa desde `infrastructure/` de cada servicio. El dominio y la aplicación no lo ven
(Guardián 4/4).

## Tests

```bash
cd libs/chassis && uv sync --all-extras && uv run pytest -q
```

## Cambios

Cambiar `chassis` obliga a reconstruir las imágenes de todos los servicios que lo usan.
