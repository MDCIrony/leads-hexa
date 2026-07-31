# Lead Router Platform (Hexagonal Architecture Monorepo)

Plataforma multi-tenant de calificación (scoring) y enrutamiento (routing) de prospectos (leads) construida en Arquitectura Hexagonal pura.

## 📁 Estructura del Monorepo
- `backend/`: FastAPI + Python 3.12 (uv, pyproject.toml, Raw SQL).
- `frontend/`: React 19 + TypeScript + Vite + Tailwind CSS (Hexagonal Mappers).
- `plan/`: Planes paso a paso para ejecución coordinada por subagentes.
- `docker-compose.yml`: Orquestación del sistema completo.

## 🚀 Planes de Implementación
Consulta el [PLAN_INDEX.md](./plan/PLAN_INDEX.md) para el detalle de la hoja de ruta y la estrategia TDD en 3 pasos.
