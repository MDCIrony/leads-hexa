# STEP 04: FastAPI Lifespan, Contenedor DI y Routers HTTP (Backend)

## 🎯 Objetivo
Configurar el framework web FastAPI utilizando el administrador de contexto `lifespan` para la Inyección de Dependencias (DI) de adaptadores y casos de uso, exponer los endpoints REST y mapear solicitudes HTTP a DTOs de entrada.

---

## 🏗️ Componentes a Desarrollar

### 1. Inyección de Dependencias vía Lifespan (`backend/src/infrastructure/di/`)
- `lifespan(app: FastAPI)`:
  - Inicializar la conexión Raw SQL a la BD y ejecutar migraciones/creación de tablas.
  - Instanciar adaptadores concretos (`RawSqlLeadRepository`, `HttpxWebhookDispatcher`, `PandasFileParser`).
  - Instanciar Casos de Uso (`IngestLeadUseCase`, `ProcessBatchUseCase`, `ManageRulesUseCase`).
  - Asignar instancias a `app.state` (ej: `app.state.ingest_lead_use_case`).

### 2. Controladores / Routers HTTP (`backend/src/infrastructure/adapters/input/api/`)
- `lead_router.py`:
  - `POST /api/v1/tenants/{tenant_id}/leads/ingest`: Recibe Pydantic Request DTO, transforma a `IngestLeadCommand`, invoca `IngestLeadUseCase` desde `app.state`, retorna Response DTO con HTTP 201.
  - `POST /api/v1/tenants/{tenant_id}/leads/batch-upload`: Recibe `UploadFile`, invoca `ProcessBatchUseCase`, retorna HTTP 200 con reporte de filas procesadas.
  - `GET /api/v1/tenants/{tenant_id}/leads`: Listado paginado de leads con filtro por estado.
- `rule_router.py`: Endpoints para crear/listar reglas de scoring y routing.
- `agent_router.py`: Endpoints para gestión de agentes de ventas.

---

## 🧪 Protocolo de Verificación TDD y Validaciones (3 Pasos)

### Paso 1: Pruebas de Endpoints HTTP (E2E / Integration con TestClient)
- Crear suite de tests de API (`tests/e2e/test_lead_endpoints.py`):
  - Ingestar un lead válido vía `POST /ingest` y verificar código HTTP 201 y payload de respuesta.
  - Ingestar datos inválidos (email mal formado) y verificar respuesta HTTP 422 / 400.
  - Probar `POST /batch-upload` enviando un CSV multipart/form-data.

Comando de ejecución:
```bash
cd backend && uv run pytest tests/e2e/
```

### Paso 2: Revisión de Consistencia de Alto Nivel
- Verificar que los Routers HTTP NO contengan lógica de negocio ni validaciones pesadas; solo validación de esquema Pydantic para deserializar el payload y delegación inmediata al caso de uso correspondiente.
- Confirmar que las dependencias se resuelvan desde `request.app.state` o mediante funciones `Depends` vinculadas a la app.

### Paso 3: Verificación de Consistencia de Datos en DB Dockerizada
1. Iniciar la aplicación FastAPI (`uv run uvicorn src.infrastructure.main:app --port 8000`).
2. Enviar petición `POST /api/v1/tenants/.../leads/ingest` usando `curl` o `httpx`.
3. Consultar directamente la base de datos (vía cliente SQL / Docker BD):
   - Confirmar que se creó una fila en la tabla `leads` con el `score` calculado y el `assigned_agent_id` asignado según la regla.
