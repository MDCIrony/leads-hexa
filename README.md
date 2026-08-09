# Lead Router

Enrutamiento y autoasignación de leads comerciales, con arquitectura hexagonal sobre FastAPI y
PostgreSQL.

Cuando entra un contacto comercial, alguien tiene que decidir tres cosas: si se puede trabajar,
cuánto vale y quién lo atiende. Lead Router convierte esas decisiones en configuración que escribe
cada organización, en vez de en código que sólo un programador puede cambiar.

## Documentación

**La documentación completa se sirve desde el propio `compose`:**

```bash
docker compose up -d docs
```

Y se lee en **<http://localhost:8002>**.

Ahí están la visión de producto, los diagramas C4, el modelo de datos, la descripción de cada
módulo, las decisiones de arquitectura con su porqué, la referencia de la API y la hoja de ruta.
El fuente vive en [`docs/content/`](docs/content/).

## Inicio rápido

```bash
docker compose up -d
curl http://localhost:8001/health
```

| Servicio | URL |
|---|---|
| API | <http://localhost:8001> |
| API · OpenAPI | <http://localhost:8001/docs> |
| Interfaz web | <http://localhost> |
| Documentación | <http://localhost:8002> |
| PostgreSQL | `localhost:5433` |

El primer usuario se crea sin autenticación y recibe el rol de administrador de plataforma; a partir
de ahí todo exige credencial. El recorrido completo —crear la organización, su gestor, y el primer
lead— está en la guía de [puesta en marcha](docs/content/desarrollo/puesta-en-marcha.md).

## Validación

Tres comandos, cada uno demuestra algo que los otros no:

```bash
docker compose --profile test run --rm backend-test    # suite completa, todas las capas
cd backend && uv run pytest -m unit -q                 # dominio aislado, sin base de datos
./scripts/verify-e2e.sh                                # el negocio sobre HTTP real
```

Ninguno necesita `--build` ni `restart`: el código va montado y la API recarga en caliente. Sólo se
reconstruye si cambian `pyproject.toml`, `uv.lock` o un `Dockerfile`.

Dentro de la suite viajan cuatro pruebas que analizan el AST y fallan si el dominio importa algo de
fuera de la biblioteca estándar, o si la aplicación importa infraestructura. Es un guardián
ejecutable, no una convención escrita.

Los detalles están en [validación](docs/content/desarrollo/validacion.md).

## Estructura del repositorio

```
backend/
  src/domain/          Entidades, value objects, motores y políticas. Sin dependencias externas
  src/application/     Casos de uso y puertos. No conoce frameworks web ni SQL
  src/infrastructure/  Adaptadores: API, persistencia, seguridad, ficheros, eventos
  migrations/          SQL numerado, idempotente, aplicado al arrancar
  tests/               unit · integration · e2e · architecture
frontend/              Interfaz React. Ver la hoja de ruta
docs/                  Subproyecto MkDocs Material
scripts/               verify-e2e.sh, la verificación de negocio
```

La regla de dependencia va siempre hacia dentro: infraestructura conoce a la aplicación, la
aplicación conoce al dominio, y el dominio no conoce a nadie.

## Estado

El backend está funcionalmente completo salvo la integración entrante. Lo que falta para tener
producto es la interfaz web.

| | |
|---|---|
| Ingesta autenticada, individual y por fichero | Disponible |
| Reglas de descalificación, puntuación y asignación configurables | Disponible |
| Autoasignación con carga, capacidad y turnos | Disponible |
| Bandeja de revisión y reproceso | Disponible |
| Avisos internos con contador de no leídos | Disponible |
| Integración entrante firmada | [Hoja de ruta](docs/content/roadmap/webhook-entrante.md) |
| Interfaz web | [Hoja de ruta](docs/content/roadmap/frontend.md) |

## Contribuir

Las convenciones de código, el flujo de ramas y cuándo hace falta una decisión de arquitectura
documentada están en [cómo contribuir](docs/content/desarrollo/contribuir.md).

Lead Router nació como material docente para un curso de arquitectura de software. Esa es la razón
de que esté documentado con este nivel de detalle: el objetivo no es sólo que funcione, sino que se
pueda explicar por qué funciona así.
