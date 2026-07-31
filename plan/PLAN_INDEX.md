# Plan Maestro de Implementación - Lead Router Platform

## 1. Principios de Arquitectura y Estándares
- **Monorepo**: Estructura limpia con `backend/`, `frontend/`, `docker-compose.yml` y `plan/`.
- **Backend (Python 3.12+ / `uv` / `pyproject.toml`)**:
  - **Arquitectura Hexagonal Estricta (Ports & Adapters)**.
  - **Dominio**: Value Objects (`EmailAddress`, `Money`, `LeadId`, etc.) y Entidades que asumen **todas** las validaciones de invariantes. Prohibido hacer validaciones de negocio en la capa de servicios.
  - **Persistencia**: **Raw SQL Queries** (sin ORM / sin SQLAlchemy).
  - **Inyección de Dependencias**: Vía el contexto `lifespan` de FastAPI.
- **Frontend (React 19 + TypeScript + Vite + Tailwind CSS)**:
  - **Arquitectura Hexagonal en Frontend**: DTOs -> Mappers -> Domain Models -> UI Components.
  - Cero styling duro / cero CSS plano; únicamente Tailwind CSS.
  - Ningún componente React ni Hook debe consumir respuestas `raw` de la API REST; uso obligatorio de Mappers.

---

## 2. Metodología TDD y Protocolo de Verificación en 3 Pasos

Cada subagente asignado a un paso debe cumplir **estrictamente** con el siguiente protocolo antes de dar su tarea por completada:

### Paso 1: TDD y Validaciones Directas
1. Escribir primero las pruebas (Unitarias o de Integración según el nivel del paso).
2. Ejecutar la suite de pruebas para confirmar el fallo inicial (Red).
3. Escribir la implementación mínima para hacer pasar las pruebas (Green).
4. Refactorizar manteniendo la suite en verde (Refactor).

### Paso 2: Revisión de Consistencia de Alto Nivel
1. El subagente valida internamente la cohesión de su código y ejecuta el linter/runner de pruebas.
2. El agente principal revisa los cambios contra los contratos globales de la arquitectura.
3. Si existe discrepancia con la especificación o entre capas, se instruye a un subagente de corrección con indicaciones puntuales.

### Paso 3: Verificación de Consistencia de Datos en DB Dockerizada e Inspección de Logs
1. Para componentes con interacción a base de datos, se debe levantar el contenedor de DB (`docker compose up -d db` o servicio correspondiente).
2. Se debe verificar empíricamente mediante pruebas de integración que las operaciones de lectura/escritura (Raw SQL) persisten y modifican los datos exactamente como la especificación lo exige.
3. **Inspección de Logs de Servicios**: Es obligatorio inspeccionar los logs del servicio (`docker compose logs backend`, `docker compose logs frontend` o logs de uvicorn/pytest) para verificar que no haya excepciones no capturadas, unhandled tracebacks ni advertencias críticas durante las pruebas.


---

## 3. Estructura de Pasos

- [x] [STEP_00: Monorepo e Infraestructura Base](./STEP_00_MONOREPO_INIT.md)
- [ ] [STEP_01: Capa de Dominio y Tests Unitarios (Backend)](./STEP_01_DOMAIN_AND_UNIT_TESTS.md)
- [ ] [STEP_02: Capa de Aplicación, Puertos y Casos de Uso (Backend)](./STEP_02_APPLICATION_PORTS_USECASES.md)
- [ ] [STEP_03: Adaptadores de Infraestructura y Raw SQL (Backend)](./STEP_03_INFRASTRUCTURE_RAW_SQL_ADAPTERS.md)
- [ ] [STEP_04: FastAPI Lifespan, Contenedor DI y Routers HTTP (Backend)](./STEP_04_FASTAPI_LIFESPAN_DI_API.md)
- [ ] [STEP_05: Capa de Dominio, DTOs y Mappers (Frontend)](./STEP_05_FRONTEND_HEXAGONAL_MAPPERS.md)
- [ ] [STEP_06: Componentes UI y Vistas React 19 + Tailwind (Frontend)](./STEP_06_FRONTEND_UI_COMPONENTS.md)
- [ ] [STEP_07: Integración Docker y Verificación E2E](./STEP_07_DOCKER_AND_E2E_VERIFICATION.md)
