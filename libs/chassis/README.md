# chassis

Infraestructura transversal compartida por todos los servicios de Lead Router: verificación del
token interno (Ed25519, ADR-0032) y correlación de peticiones por `X-Request-ID`.

- `chassis.auth`: `Ed25519Signer`, `JwksCache`, `TokenVerifier`, `Claims`.
- `chassis.web`: `RequestIdMiddleware` (ASGI puro), `RequestIdLogFilter`, `configure_logging`.

## Regla de uso

Sólo se importa desde `infrastructure/` de cada servicio. El dominio y la aplicación no lo ven
(Guardián 4/4).

## Tests

```bash
cd libs/chassis && uv run pytest -q
```

## Cambios

Cambiar `chassis` obliga a reconstruir las imágenes de todos los servicios que lo usan.
