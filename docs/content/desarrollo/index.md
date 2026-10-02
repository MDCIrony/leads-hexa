# Desarrollo

Mapa de esta sección para quien va a programar en Lead Router: dónde vive cada cosa en el
repositorio y en qué orden conviene leer el resto de páginas.

## Dónde vive cada cosa

El backend sigue arquitectura hexagonal: el dominio no depende de nada, la aplicación orquesta
casos de uso sobre puertos, y la infraestructura conecta ambos con el mundo exterior (HTTP,
PostgreSQL). El porqué está en [Arquitectura](../arquitectura/index.md); esta tabla es sólo el mapa
de ficheros.

| Ruta | Contiene |
|---|---|
| `backend/src/domain` | Entidades, value objects, políticas y servicios de dominio. No importa nada fuera de la biblioteca estándar de Python. |
| `backend/src/application` | Casos de uso, puertos de entrada y salida, DTOs. Orquesta el dominio; no importa infraestructura ni un framework web. |
| `backend/src/infrastructure` | Adaptadores: routers de FastAPI en `adapters/input/api`, persistencia en PostgreSQL en `adapters/output/persistence`, el contenedor de inyección en `di/`, configuración y el punto de entrada `main.py`. |
| `backend/tests` | `unit/`, `integration/`, `e2e/` y `architecture/` — una carpeta por marcador de pytest. |
| `backend/migrations` | SQL versionado, aplicado automáticamente al arrancar la API. |
| `frontend` | Esqueleto React + Vite + TypeScript, servido por nginx en el `compose`. La interfaz de producto todavía no está construida; ver la hoja de ruta. |
| `docs` | Este sitio (MkDocs). Contenido en `docs/content/`, navegación en `docs/mkdocs.yml`. |

## Orden de lectura

1. [Puesta en marcha](puesta-en-marcha.md) — de cero a un lead ingerido, con comandos reales.
2. [Validación](validacion.md) — los cuatro comandos que demuestran que un cambio no rompió nada.
3. [Convenciones](convenciones.md) — cómo se escribe código aquí.
4. [Cómo contribuir](contribuir.md) — ramas, revisión y cuándo hace falta un ADR.
5. [API · Referencia](api-referencia.md) y [API · Errores](api-errores.md) — el contrato HTTP
   completo.

## Ver también

- [Arquitectura](../arquitectura/index.md) — las tres capas y el porqué de cada frontera.
- [Módulos](../modulos/index.md) — qué hace cada módulo de negocio.
- [Decisiones](../decisiones/index.md) — el archivo de ADRs.
