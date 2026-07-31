# STEP 02: Capa de Aplicación, Puertos y Casos de Uso (Backend)

## 🎯 Objetivo
Definir las interfaces abstractas (Ports) para desacoplar las dependencias externas de la lógica del sistema, e implementar los Casos de Uso principales con adaptadores InMemory para pruebas aisladas.

---

## 🏗️ Componentes a Desarrollar

### 1. Puertos de Salida - Driven Ports (`backend/src/application/ports/output/`)
- `LeadRepositoryPort` (`abc.ABC`): `save(lead)`, `get_by_id(id)`, `list_by_tenant(tenant_id)`.
- `RuleRepositoryPort` (`abc.ABC`): `get_rules_by_tenant(tenant_id)`.
- `AgentRepositoryPort` (`abc.ABC`): `get_available_agents(team)`, `update_active_count(agent_id, count)`.
- `WebhookDispatcherPort` (`abc.ABC`): `dispatch(target_url, secret_token, payload)`.
- `FileParserPort` (`abc.ABC`): `parse_leads_file(file_content, filename) -> List[IngestLeadCommand]`.

### 2. Puertos de Entrada y DTOs - Driving Ports (`backend/src/application/ports/input/`)
- `IngestLeadCommand` (`dataclass(frozen=True)`): Datos de entrada deserializados.
- `IngestLeadInputPort` (`abc.ABC`): `execute(command: IngestLeadCommand) -> Dict[str, Any]`.
- `ProcessBatchInputPort` (`abc.ABC`): `execute(file_content, filename, tenant_id) -> Dict[str, Any]`.
- `ManageRulesInputPort` (`abc.ABC`): ABM de reglas de scoring y routing.

### 3. Casos de Uso - Use Cases (`backend/src/application/use_cases/`)
- `IngestLeadUseCase`:
  1. Instanciar Value Objects & `Lead` Entity (valida invariantes).
  2. Consultar reglas activas vía `RuleRepositoryPort`.
  3. Ejecutar `ScoringEngine` para calcular puntaje y actualizar estado a `QUALIFIED` / `DISQUALIFIED`.
  4. Si califica, ejecutar `RouterEngine` para seleccionar agente vía `AgentRepositoryPort` y actualizar estado a `ASSIGNED`.
  5. Guardar `Lead` vía `LeadRepositoryPort`.
  6. Emitir evento vía `WebhookDispatcherPort`.
- `ProcessBatchUseCase`: Procesa múltiples filas llamando recursivamente al caso de uso de ingesta registrando fila a fila los éxitos o fallos.

---

## 🧪 Protocolo de Verificación TDD y Validaciones (3 Pasos)

### Paso 1: TDD de Casos de Uso con Adaptadores InMemory
1. Crear adaptadores InMemory para los repositorios (`tests/unit/mocks/in_memory_lead_repo.py`, `in_memory_webhook_dispatcher.py`, etc.).
2. Crear suite de tests de casos de uso (`tests/unit/application/test_ingest_lead_use_case.py`):
   - Verificar flujo completo: Ingesta -> Scoring -> Router -> Persistencia -> Despacho de Webhook.
   - Verificar casos de fallo (email inválido, sin reglas, sin agentes disponibles).

Comando de ejecución:
```bash
cd backend && uv run pytest tests/unit/application/
```

### Paso 2: Revisión de Consistencia de Alto Nivel
- Comprobar que los casos de uso dependan ÚNICAMENTE de las interfaces `abc.ABC` de los puertos, nunca de implementaciones concretas de la infraestructura.
- Verificar que las excepciones de flujo sean capturadas y mapeadas a DTOs de resultado coherentes.

### Paso 3: Verificación de Estado In-Memory
- Asegurar que la lógica de aplicación se pueda ejercitar al 100% de cobertura sin necesidad de una base de datos real.
