# STEP 00: Inicialización del Monorepo e Infraestructura Base

## 🎯 Objetivo
Configurar el entorno inicial del proyecto en estructura monorepo, inicializando los proyectos de `backend` (con `uv` y `pyproject.toml`) y `frontend` (Vite + React 19 + TypeScript + Tailwind CSS), junto con la configuración de Docker Compose.

---

## 🛠️ Tareas

1. **Estructura del Repositorio**:
   ```
   leads-hexa/
   ├── backend/
   │   ├── pyproject.toml
   │   ├── src/
   │   │   ├── domain/
   │   │   ├── application/
   │   │   └── infrastructure/
   │   └── tests/
   │       ├── unit/
   │       ├── integration/
   │       └── e2e/
   ├── frontend/
   │   ├── package.json
   │   ├── vite.config.ts
   │   ├── tsconfig.json
   │   ├── src/
   │   │   ├── domain/
   │   │   ├── application/
   │   │   ├── infrastructure/
   │   │   └── presentation/
   │   └── tests/
   │       └── unit/
   ├── docker-compose.yml
   └── plan/
   ```

2. **Backend Config**:
   - Inicializar entorno con `uv init --bare backend`.
   - Configurar `pyproject.toml` con dependencias: `fastapi`, `uvicorn`, `httpx`, `pandas`, `openpyxl`, `aiosqlite`, `pytest`, `pytest-asyncio`.

3. **Frontend Config**:
   - Inicializar con Vite + React 19 + TypeScript.
   - Instalar `tailwindcss`, `@tailwindcss/vite`, `vitest`, `@testing-library/react`, `lucide-react`.

4. **Docker Compose**:
   - Crear `docker-compose.yml` con servicios: `db` (PostgreSQL / SQLite volume), `backend`, `frontend`.

---

## 🧪 Protocolo de Verificación TDD y Validaciones (3 Pasos)

### Paso 1: Pruebas Unitarias de Sanidad Iniciales
- **Backend**: Crear un test unitario simple de verificación en `backend/tests/unit/test_sanitizing.py` que valide la ejecución del runner `pytest`.
- **Frontend**: Crear un test unitario simple de verificación en `frontend/tests/unit/sanitizing.test.ts` que funcione con `vitest`.
- Comando de verificación:
  - Backend: `cd backend && uv run pytest`
  - Frontend: `cd frontend && npm run test`

### Paso 2: Validación de Consistencia por el Agente
- Verificar que la estructura de carpetas `domain/`, `application/`, `infrastructure/` cumpla exactamente con los principios del estándar Hexagonal definido en la especificación.

### Paso 3: Verificación de Entorno Docker
- Ejecutar `docker compose config` para garantizar sintaxis válida del archivo Docker Compose.
