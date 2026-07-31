# STEP 07: Integración Docker y Verificación E2E

## 🎯 Objetivo
Orquestar todo el sistema (Frontend, Backend, Base de Datos PostgreSQL/SQLite) mediante Docker Compose, validando el flujo completo de ingesta, puntuación, enrutamiento, consulta en DB y renderizado en UI.

---

## 🏗️ Componentes a Desarrollar

1. **`backend/Dockerfile`**:
   - Multi-stage build usando imagen `python:3.12-slim` con `uv` preinstalado.
   - Exponer puerto 8000.
2. **`frontend/Dockerfile`**:
   - Multi-stage build usando `node:22-alpine` para build de Vite y Nginx Alpine para servir assets estáticos.
   - Exponer puerto 80.
3. **`docker-compose.yml`**:
   - Servicio `db`: PostgreSQL 16 con volumen persistente y puerto 5432.
   - Servicio `backend`: Depende de `db`, variables de entorno de conexión DB.
   - Servicio `frontend`: Depende de `backend`.

---

## 🧪 Protocolo de Verificación TDD y Validaciones (3 Pasos)

### Paso 1: Verificación de Build e Integración Docker
- Levantar la infraestructura completa con Docker Compose:
```bash
docker compose up --build -d
```
- Verificar que los contenedores `leads_hexa_db`, `leads_hexa_backend` y `leads_hexa_frontend` se encuentren en estado `healthy`/`running`.

### Paso 2: Script de Prueba End-to-End (E2E Integration Test)
- Ejecutar un script de prueba de flujo completo (`tests/e2e/test_system_e2e.py` o vía `curl`):
  1. Crear un Agente de Ventas en la base de datos vía API.
  2. Crear una ScoringRule (`budget > 10000 -> +30 pts`).
  3. Ingestar un Lead con `budget: 15000`.
  4. Confirmar que la respuesta retorne `status: ASSIGNED` y `calculated_score: 30`.

### Paso 3: Verificación de Consistencia de Datos en DB Dockerizada
1. Conectarse a la BD del contenedor dockerizado:
   ```bash
   docker compose exec db psql -U postgres -d leads_db -c "SELECT id, email, score, status, assigned_agent_id FROM leads;"
   ```
2. Validar empíricamente que:
   - La fila del lead existe con los valores calculados.
   - El contador `active_leads_count` del agente asignado se haya incrementado en 1 en la tabla `agents`.
3. Probar la subida de un CSV masivo (20 leads) a través de la UI en el Frontend (`http://localhost`) y verificar que todos los 20 leads aparezcan reflejados en el Dashboard de Leads y en la base de datos.
