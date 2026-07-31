# STEP 05: Capa de Dominio, DTOs y Mappers (Frontend)

## 🎯 Objetivo
Implementar la arquitectura hexagonal en la SPA de React 19 / TypeScript, aislando la lógica de dominio del frontend, definiendo DTOs de infraestructura y mappers estrictos para desacoplar el consumo de la API REST.

---

## 🏗️ Componentes a Desarrollar

### 1. Modelos de Dominio del Frontend (`frontend/src/domain/`)
- `lead.model.ts`: Entidad de Lead en UI (tipos fuertes, enums, métodos helpers de formato de score y status).
- `rule.model.ts`: Entidad Rule en UI (campos, operadores, score deltas).
- `agent.model.ts`: Entidad Agent en UI.

### 2. DTOs de Infraestructura (`frontend/src/infrastructure/dtos/`)
- `lead-api.dto.ts`: Interfaces exactas que reflejan las respuestas JSON del backend (`LeadIngestResponseDto`, `LeadListItemDto`).
- `rule-api.dto.ts`: DTOs de lectura/escritura de reglas.

### 3. Mappers (`frontend/src/application/mappers/`)
- `lead.mapper.ts`:
  - `toDomain(dto: LeadListItemDto): LeadModel`
  - `toIngestCommandDto(model: Partial<LeadModel>): LeadIngestRequestDto`
- `rule.mapper.ts`: `toDomain`, `toDto`.
- `agent.mapper.ts`: `toDomain`, `toDto`.

### 4. Puertos y Servicios de Infraestructura HTTP (`frontend/src/infrastructure/api/`)
- `lead-api.client.ts`: Consume la API con `fetch`/`axios` devolviendo DTOs primarios.
- `lead.service.ts`: Orquesta la llamada al cliente HTTP y aplica obligatoriamente los `mappers` antes de entregar los datos a los hooks o componentes de la vista.

---

## 🧪 Protocolo de Verificación TDD y Validaciones (3 Pasos)

### Paso 1: Tests Unitarios TDD de Mappers y Servicios (Vitest)
- Crear tests unitarios en `frontend/tests/unit/mappers/lead.mapper.test.ts`:
  - Validar que datos en snake_case del backend DTO se mapeen correctamente a propiedades camelCase y tipos del modelo de dominio del frontend.
  - Validar manejo de valores nulos o campos opcionales (`assigned_agent`, `custom_attributes`).
- Crear tests unitarios en `frontend/tests/unit/services/lead.service.test.ts`:
  - Simular respuesta de la API con MSW o Mocks y comprobar que el servicio retorne modelos de dominio mapeados.

Comando de ejecución:
```bash
cd frontend && npm run test
```

### Paso 2: Revisión de Consistencia de Alto Nivel
- Garantizar que NINGÚN componente o Hook en React consuma directamente las interfaces DTO de infraestructura.
- Confirmar que los mappers sean la única frontera donde se realiza conversión de tipos e idromorfismos de datos del servidor.

### Paso 3: Verificación de Mocks In-Memory
- La capa de dominio y mappers del frontend deben probarse con 100% de aislamiento en Vitest sin requerir un servidor backend encendido.
