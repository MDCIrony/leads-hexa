# 🚀 Lead Router Platform (Multi-tenant Hexagonal Monorepo)

Plataforma multi-tenant de **calificación (scoring)** y **enrutamiento (routing)** de prospectos comercializables (leads), diseñada bajo la **Arquitectura Hexagonal Pura (Ports & Adapters)** y construida en un monorepo desacoplado con **FastAPI**, **React 19**, **Tailwind CSS** y **Consultas Raw SQL (sin ORM)**.

---

## 📐 1. Diagramas de Negocio y Arquitectura

### 🏢 1.1 Diagrama C4 - Nivel 1: Contexto de Negocio
Describe cómo interactúan los actores externos, clientes y administradores con la plataforma **Lead Router**.

```mermaid
graph TD
    ClientApp["🌐 Fuentes de Leads / CRM Cliente<br/>(HTTP Webhooks / REST API)"]
    AdminUser["👨‍💼 Administrador Multi-tenant<br/>(Frontend SPA Dashboard)"]
    LeadRouterSystem["⚡ Lead Router Platform<br/>[Sistema Central Hexagonal]"]
    SalesAgent["👩‍💻 Agentes de Ventas<br/>(Receptores de Leads Asignados)"]
    ClientWebhookTarget["📡 Webhook Saliente del Cliente<br/>(Notificaciones HMAC SHA-256)"]

    ClientApp -->|1. Ingesta Lead Individual / Batch CSV| LeadRouterSystem
    AdminUser -->|2. Configura Reglas de Scoring & Routing| LeadRouterSystem
    LeadRouterSystem -->|3. Enruta Lead a Agente| SalesAgent
    LeadRouterSystem -->|4. Emite Evento LEAD_ASSIGNED / LEAD_QUALIFIED| ClientWebhookTarget
```

---

### 📦 1.2 Diagrama C4 - Nivel 2: Contenedores del Sistema
Visualiza los contenedores principales del monorepo y cómo interactúan entre sí.

```mermaid
graph TB
    subgraph ClientSpace ["Entorno del Cliente / Usuario"]
        SPA["💻 Frontend SPA Container<br/>[React 19 + TypeScript + Vite + Tailwind]<br/>(Nginx Alpine - Puerto 80)"]
        ExternalWebhook["📡 External Webhook Server<br/>(Receptor HTTP HMAC)"]
    end

    subgraph PlatformContainer ["Plataforma Lead Router Container"]
        APIGateway["🔌 FastAPI REST API Router<br/>(Lifespan DI Container - Puerto 8000)"]
        
        subgraph HexagonalCore ["Core de Negocio (Hexagonal)"]
            UseCases["⚙️ Use Cases / Application Layer<br/>(IngestLeadUseCase, ProcessBatchUseCase)"]
            DomainEngine["🧩 Domain Engine<br/>(ScoringEngine, RouterEngine, ValueObjects)"]
        end
        
        RawSQLPersistence["🗄️ Persistencia Raw SQL<br/>(RawSqlLeadRepository - PostgreSQL / SQLite)<br/>*Sin ORM / Sin SQLAlchemy*"]
        HttpxDispatcher["🚀 Webhook Dispatcher<br/>(HttpxWebhookDispatcher + HMAC SHA-256)"]
        PandasParser["📊 File Parser<br/>(PandasFileParser CSV / XLSX)"]
    end

    SPA -->|Proxy Pass /api/v1| APIGateway
    APIGateway -->|Inyecta Dependencias| UseCases
    UseCases -->|Aplica Reglas & Invariantes| DomainEngine
    UseCases -->|Raw SQL Queries| RawSQLPersistence
    UseCases -->|Parsea Archivos| PandasParser
    UseCases -->|Despacha Notificaciones| HttpxDispatcher
    HttpxDispatcher -->|HTTP POST Payload Firmado| ExternalWebhook
```

---

### 🔷 1.3 Diagrama de Arquitectura Hexagonal (Ports & Adapters)
Muestra la separación concéntrica estricta en el Backend. Las capas internas jamás dependen de las externas.

```mermaid
graph TD
    subgraph DrivingAdapters ["1. Adaptadores de Entrada (Driving)"]
        FastAPIRouters["FastAPI Routers<br/>(/ingest, /batch-upload, /rules, /agents)"]
    end

    subgraph ApplicationLayer ["2. Capa de Aplicación (Ports & Use Cases)"]
        subgraph InputPorts ["Driving Ports (Interfaces)"]
            IngestPort["IngestLeadInputPort"]
            BatchPort["ProcessBatchInputPort"]
        end
        
        subgraph Interactors ["Casos de Uso (Use Cases)"]
            IngestUC["IngestLeadUseCase"]
            BatchUC["ProcessBatchUseCase"]
        end

        subgraph OutputPorts ["Driven Ports (Interfaces)"]
            LeadRepoPort["LeadRepositoryPort"]
            RuleRepoPort["RuleRepositoryPort"]
            AgentRepoPort["AgentRepositoryPort"]
            DispatcherPort["WebhookDispatcherPort"]
            ParserPort["FileParserPort"]
        end
    end

    subgraph DomainCore ["3. Capa de Dominio (Núcleo Puro sin Librerías)"]
        Entities["Entidades:<br/>Lead, ScoringRule, RoutingRule, Agent"]
        ValueObjects["Value Objects (Validaciones):<br/>EmailAddress, Money, Score, LeadId, TenantId"]
        DomainServices["Servicios de Dominio:<br/>ScoringEngine, RouterEngine"]
    end

    subgraph DrivenAdapters ["4. Adaptadores de Salida (Driven)"]
        RawSQLRepo["RawSqlLeadRepository<br/>(Consultas Directas SQL)"]
        HttpxDisp["HttpxWebhookDispatcher<br/>(httpx HMAC)"]
        PandasPars["PandasFileParser<br/>(pandas CSV/XLSX)"]
    end

    FastAPIRouters -->|Invoca| IngestPort
    FastAPIRouters -->|Invoca| BatchPort
    IngestPort -.->|Implementa| IngestUC
    BatchPort -.->|Implementa| BatchUC
    IngestUC -->|Instancia & Valida| ValueObjects
    IngestUC -->|Orquesta| DomainServices
    IngestUC -->|Usa| LeadRepoPort
    IngestUC -->|Usa| DispatcherPort
    RawSQLRepo -.->|Implementa| LeadRepoPort
    HttpxDisp -.->|Implementa| DispatcherPort
    PandasPars -.->|Implementa| ParserPort
```

---

### 🔄 1.4 Diagrama de Flujo y Secuencia: Ingesta Individual & Evaluación

```mermaid
sequenceDiagram
    autonumber
    actor Client as Cliente / Webhook
    participant API as FastAPI Router
    participant UC as IngestLeadUseCase
    participant VO as Value Objects (Email, Money)
    participant SE as ScoringEngine
    participant RE as RouterEngine
    participant DB as RawSqlLeadRepository (DB)
    participant WH as HttpxWebhookDispatcher

    Client->>API: POST /api/v1/tenants/{tenant_id}/leads/ingest
    API->>UC: execute(IngestLeadCommand)
    UC->>VO: EmailAddress(email) + Money(budget)
    alt Email o Budget Inválido
        VO-->>UC: Lanza InvalidEmailException / InvalidBudgetException
        UC-->>API: LeadProcessedResult(status="FAILED", error="...")
        API-->>Client: HTTP 422 / 400 Bad Request
    else Validaciones Exitosas
        VO-->>UC: Value Objects Válidos instanciados
        UC->>SE: evaluate(lead, scoring_rules)
        SE-->>UC: Retorna Score Delta Acumulado (+35 pts)
        UC->>UC: lead.qualify(threshold_qualified=30)
        alt Lead Estado == QUALIFIED
            UC->>RE: select_agent(lead, routing_rules, agents)
            RE-->>UC: Retorna Agente Seleccionado (LOWEST_LOAD)
            UC->>UC: lead.assign_to_agent(agent.id)
        end
        UC->>DB: save(lead) [Raw SQL INSERT INTO leads]
        DB-->>UC: Lead Persistido
        UC->>WH: dispatch(target_url, secret_token, payload)
        WH-->>UC: Webhook Entregado (Firma HMAC OK)
        UC-->>API: LeadProcessedResult(status="ASSIGNED", score=35)
        API-->>Client: HTTP 201 Created JSON
    end
```

---

## 📁 2. Estructura del Monorepo

```
leads-hexa/
├── backend/                            # FastAPI + Python 3.12 (uv, pyproject.toml)
│   ├── src/
│   │   ├── domain/                     # NÚCLEO PURO (Value Objects, Entities, Domain Services)
│   │   ├── application/                # CASOS DE USO Y PUERTOS (Interfaces abc.ABC & DTOs)
│   │   └── infrastructure/             # ADAPTADORES (FastAPI, Raw SQL, httpx, pandas)
│   ├── tests/
│   │   ├── unit/                       # Unit tests de Dominio y Aplicación
│   │   ├── integration/                # Integration tests de Raw SQL y Parsers
│   │   └── e2e/                        # Tests E2E de API y Flujo Completo
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                           # React 19 + TypeScript + Vite + Tailwind CSS
│   ├── src/
│   │   ├── domain/                     # Modelos de Dominio Frontend
│   │   ├── application/                # Mappers (DTO <-> Domain) & Services
│   │   ├── infrastructure/             # DTOs REST & Axios API Client
│   │   └── presentation/               # UI Components & Pages (Tailwind v4)
│   ├── tests/                          # Tests unitarios con Vitest
│   ├── Dockerfile
│   └── nginx.conf                      # SPA Server + Reverse Proxy Proxy Pass /api/v1
├── docs/
│   └── diagrams/                       # Archivos .drawio nativos de diagramas
│       ├── c4_context_container.drawio
│       ├── hexagonal_architecture.drawio
│       └── lead_processing_flow.drawio
├── docker-compose.yml                  # Orquestación completa (DB, Backend, Frontend)
└── README.md
```

---

## 🛠️ 3. Reglas Técnicas y Principios de Diseño

1. **Invariantes en Value Objects**: Validaciones como la sintaxis del correo electrónico ([EmailAddress](file:///home/mdcast/Escritorio/PrivateProjects/arquitectura/leads-hexa/backend/src/domain/value_objects/email.py)) o presupuestos no negativos ([Money](file:///home/mdcast/Escritorio/PrivateProjects/arquitectura/leads-hexa/backend/src/domain/value_objects/money.py)) residen 100% dentro del constructor del Value Object. Cero validaciones duras en la capa de servicios.
2. **Consultas Raw SQL Directas**: Se prohíbe el uso de ORMs como SQLAlchemy. La persistencia en [RawSqlLeadRepository](file:///home/mdcast/Escritorio/PrivateProjects/arquitectura/leads-hexa/backend/src/infrastructure/adapters/output/persistence/raw_sql_lead_repository.py) se realiza mediante consultas SQL puras con marcadores de posición parametrizados (`?`).
3. **Mappers Hexagonales en Frontend**: La capa de presentación y los hooks de React jamás consumen DTOs de infraestructura en bruto. [LeadMapper](file:///home/mdcast/Escritorio/PrivateProjects/arquitectura/leads-hexa/frontend/src/application/mappers/lead.mapper.ts) transforma respuestas `snake_case` a modelos de dominio `camelCase`.
4. **Contenedor DI en Lifespan**: FastAPI inicializa conexiones y contenedores de casos de uso en el ciclo de vida `lifespan` de [main.py](file:///home/mdcast/Escritorio/PrivateProjects/arquitectura/leads-hexa/backend/src/infrastructure/main.py), inyectándolos en `app.state`.

---

## 🚀 4. Guía de Inicio Rápido

### Prerrequisitos
- Python 3.12+ con `uv` instado (`pip install uv` o vía ejecutable astral-sh).
- Node.js 22+ y `npm`.
- Docker & Docker Compose.

### Ejecución Local del Backend
```bash
cd backend
uv sync                     # Instalar dependencias
uv run pytest -m unit       # Tests de dominio y casos de uso, sin variables de entorno
uv run uvicorn src.infrastructure.main:app --reload --port 8000
```

### Ejecución Local del Frontend
```bash
cd frontend
npm install                 # Instalar dependencias
npm run test                # Ejecutar tests unitarios con Vitest
npm run build               # Validar compilación TypeScript + Vite build
npm run dev                 # Iniciar servidor dev en http://localhost:5173
```

### Ejecución con Docker Compose (Stack Completo)
```bash
docker compose up --build -d
```
Acceder a:
- **Frontend SPA**: `http://localhost:80`
- **Backend API Docs (Swagger UI)**: `http://localhost:8001/docs`

### Ejecución de la Suite de Pruebas

Sin infraestructura (dominio y casos de uso, sin variables de entorno):
```bash
cd backend && uv run pytest -m unit
```

Suite completa (125 tests: unit, integration, e2e y architecture) dentro de
Docker, que es la única forma reproducible de ejecutarla porque requiere
`DATABASE_URL` apuntando a un PostgreSQL real:
```bash
docker compose --profile test run --rm backend-test
```

El puerto 5433 del host publica el PostgreSQL del compose. Sirve para
ejecutar la suite completa desde fuera del contenedor exportando
`DATABASE_URL` y `TEST_DATABASE_URL` hacia `localhost:5433`. Si ya tienes un
PostgreSQL local escuchando en ese puerto, cambia el mapeo en
`docker-compose.yml`.
