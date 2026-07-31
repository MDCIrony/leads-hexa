# STEP 03: Adaptadores de Infraestructura y Raw SQL (Backend)

## 🎯 Objetivo
Implementar los adaptadores de salida para la infraestructura real usando **consultas SQL directas (Raw Queries)** sin ORM (SQLite en dev / PostgreSQL compatible), despachador HTTP con `httpx` y parser de archivos con `pandas`.

---

## 🏗️ Componentes a Desarrollar

### 1. Adaptadores de Persistencia Raw SQL (`backend/src/infrastructure/adapters/output/persistence/`)
- **Gestor de Conexión & Esquema**:
  - Script SQL de creación de tablas: `leads`, `scoring_rules`, `routing_rules`, `agents`, `webhook_configs`.
  - Conector `RawSqlDatabase`: Manejo directo de cursores y ejecuciones SQL parametrizadas (`?` o `%s`) para evitar inyecciones SQL.
- `RawSqlLeadRepository`: Implementación de `LeadRepositoryPort` con `INSERT INTO leads ...` y `SELECT ... FROM leads`.
- `RawSqlRuleRepository`: Implementación de `RuleRepositoryPort` con `SELECT ... FROM scoring_rules`.
- `RawSqlAgentRepository`: Implementación de `AgentRepositoryPort` con `SELECT ... UPDATE agents SET active_leads_count = ...`.

### 2. Despachador HTTP Webhook (`backend/src/infrastructure/adapters/output/http/`)
- `HttpxWebhookDispatcher`: Implementación de `WebhookDispatcherPort` usando `httpx.AsyncClient`. Generación de firma HMAC SHA-256 en header `X-LeadRouter-Signature`.

### 3. Parser de Archivos Batch (`backend/src/infrastructure/adapters/output/parsers/`)
- `PandasFileParser`: Implementación de `FileParserPort` para procesar archivos `.csv` y `.xlsx` retornando instancias de `IngestLeadCommand`.

---

## 🧪 Protocolo de Verificación TDD y Validaciones (3 Pasos)

### Paso 1: Pruebas de Integración TDD
- **Pruebas de Repositorio Raw SQL** (`tests/integration/test_raw_sql_lead_repo.py`):
  - Probar creación de esquema e inserción/lectura real de registros con Raw SQL.
- **Pruebas de Parser** (`tests/integration/test_pandas_file_parser.py`):
  - Parsear archivos CSV y Excel de prueba con filas válidas e inválidas.

Comando de ejecución:
```bash
cd backend && uv run pytest tests/integration/
```

### Paso 2: Revisión de Consistencia de Alto Nivel
- Confirmar que NINGÚN adaptador use ORM como SQLAlchemy o Peewee. Las consultas deben ser Raw SQL puras parametrizadas.
- Verificar que las tuplas resultantes del DB cursor sean mapeadas correctamente a las Entidades de Dominio en el adaptador.

### Paso 3: Verificación de Consistencia de Datos en DB Dockerizada
1. Levantar el servicio de base de datos (`docker compose up -d db` o SQLite test DB en memoria/archivo).
2. Ejecutar inserción mediante `RawSqlLeadRepository` y verificar ejecutando una consulta SQL directa que las columnas `id`, `tenant_id`, `score`, `status`, `assigned_agent_id` tengan los tipos y valores exactos esperados.
