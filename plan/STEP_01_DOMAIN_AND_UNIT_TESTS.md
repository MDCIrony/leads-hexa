# STEP 01: Capa de Dominio y Tests Unitarios (Backend)

## 🎯 Objetivo
Construir el núcleo del dominio sin ninguna dependencia externa (frameworks, ORM, base de datos o red), implementando Value Objects, Entidades y Servicios de Dominio bajo enfoque TDD estricto.

---

## 🏗️ Componentes a Desarrollar

### 1. Value Objects (`backend/src/domain/value_objects/`)
- `EmailAddress`: Validación estricta del formato de correo electrónico en su instanciación (`__post_init__`). Lanza `InvalidEmailException`.
- `Money` / `Budget`: Validación de montos numéricos (>= 0). Lanza `InvalidBudgetException`.
- `LeadId` / `TenantId` / `AgentId`: Envoltorios de UUID con autogeneración y validación de formato UUID v4.
- `Score`: Puntuación entera con operaciones immutables de incremento/decremento.
- `Operator`: Enum (`EQUALS`, `NOT_EQUALS`, `GREATER_THAN`, `LESS_THAN`, `CONTAINS`, `IN`).
- `LeadStatus`: Enum (`NEW`, `QUALIFIED`, `DISQUALIFIED`, `ASSIGNED`, `FAILED`).
- `AssignmentStrategy`: Enum (`ROUND_ROBIN`, `LOWEST_LOAD`, `DIRECT_AGENT`).

### 2. Entidades (`backend/src/domain/entities/`)
- `Lead`: Atributos (`id`, `tenant_id`, `first_name`, `last_name`, `email`, `budget`, `industry`, `custom_attributes`, `score`, `status`, `assigned_agent_id`, `created_at`).
  - Métodos: `apply_score(delta: int)`, `qualify(threshold_qualified, threshold_disqualified)`, `assign_to_agent(agent_id)`.
- `ScoringRule`: Atributos (`id`, `name`, `field`, `operator`, `value`, `score_delta`).
- `RoutingRule`: Atributos (`id`, `min_score`, `target_team`, `assignment_strategy`, `target_agent_ids`).
- `Agent`: Atributos (`id`, `name`, `email`, `team`, `active_leads_count`, `is_active`).

### 3. Servicios de Dominio (`backend/src/domain/services/`)
- `ScoringEngine`: Evalúa una lista de `ScoringRule` contra las propiedades/custom_attributes de un `Lead`.
- `RouterEngine`: Selecciona el `Agent` adecuado evaluando `RoutingRule` y la estrategia de asignación (ej. menor `active_leads_count`).

---

## 🧪 Protocolo de Verificación TDD y Validaciones (3 Pasos)

### Paso 1: TDD Estricto (Red -> Green -> Refactor)
1. **Tests Unitarios de Value Objects** (`tests/unit/domain/test_value_objects.py`):
   - Probar validación de email válido / inválido.
   - Probar presupuestos negativos / válidos.
2. **Tests Unitarios de Entidades** (`tests/unit/domain/test_entities.py`):
   - Probar transiciones de estado de `Lead` (`NEW` -> `QUALIFIED` -> `ASSIGNED`).
3. **Tests Unitarios de Motores de Dominio** (`tests/unit/domain/test_scoring_engine.py` y `test_router_engine.py`):
   - Cobertura de todos los operadores (`EQUALS`, `GREATER_THAN`, `CONTAINS`, dot notation en `custom_attributes`).
   - Cobertura de estrategias de enrutamiento (`LOWEST_LOAD`, `ROUND_ROBIN`).

Comando de ejecución:
```bash
cd backend && uv run pytest tests/unit/domain/
```

### Paso 2: Revisión de Consistencia de Alto Nivel
- Confirmar que NINGÚN archivo dentro de `src/domain/` importe módulos externos de infraestructura (FastAPI, pydantic, sqlalchemy, etc.). Únicamente librería estándar de Python (`dataclasses`, `uuid`, `enum`, `typing`, `datetime`).
- Verificar que las validaciones residan exclusivamente dentro de los Value Objects y Entidades (cero validaciones en servicios).

### Paso 3: Verificación de Estado In-Memory
- Todos los tests de dominio deben ejecutarse en < 1 segundo sin requerir IO ni conexiones a base de datos.
