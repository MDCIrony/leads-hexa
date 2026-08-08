# F0.5 — Separación de planos: diseño

**Fecha:** 2026-08-07
**Estado:** ✅ **implementado y verificado.** Se conserva como registro de la decisión de diseño.
El spec vigente del sistema es [el del MVP](2026-08-07-lead-router-mvp-design.md).
**Ámbito:** backend
**Depende de:** F0 (fundación hexagonal), cerrada
**Precede a:** F1 (grupos y motor de asignación)

---

## 1. Por qué existe esta fase

Al implementar F0 se decidió que la organización se deriva del token y deja de viajar en la URL. Esa decisión cerró de raíz los accesos cruzados entre organizaciones, pero dejó al descubierto una contradicción que el diseño original no había resuelto.

Un `ADMIN` de plataforma tiene `tenant_id = None`: no pertenece a ninguna organización. Al derivarse la organización del token, ese administrador **no tiene forma de expresar sobre cuál quiere operar**. Las filas de la matriz de permisos que le concedían ver leads o gestionar reglas quedaron inalcanzables: no fallan con un error claro, simplemente reciben `None` donde esperaban un identificador.

Hay dos salidas posibles, y esta fase implementa la segunda:

1. **Impersonación explícita.** Los endpoints operativos aceptan un `?tenant_id=` que sólo el `ADMIN` puede usar. Conserva la matriz original, a cambio de reintroducir un identificador de organización controlado por el cliente —justo lo que se acaba de eliminar—, aunque restringido a un rol.
2. **Separación de planos.** El `ADMIN` opera en un plano distinto: administra organizaciones y sus gestores, y no accede a los datos operativos de ninguna. Obliga a corregir la matriz de permisos, y a cambio elimina la ambigüedad en lugar de gestionarla.

Se adopta la **separación de planos**. Un superadministrador que no puede leer los leads de sus clientes es una propiedad deseable de un sistema multi-organización, no una carencia: reduce el alcance de una credencial comprometida y hace que el aislamiento entre clientes sea estructural.

## 2. Un segundo motivo: una fuga que sigue abierta

Al revisar el código para esta fase se confirmó que `GET /api/v1/agents` y `GET /api/v1/agents/{agent_id}` **sólo exigen estar autenticado**. No filtran por organización.

En concreto, hoy:

- `list_agents` (`agent_router.py:71-89`) llama a `GetAgentsUseCase`, que invoca `list_active(team=...)` sin ningún criterio de organización.
- `get_agent` (`agent_router.py:92-100`) recupera cualquier agente por identificador, sin comprobar a qué organización pertenece.

Es decir: **un asesor de la organización A puede enumerar y leer los asesores de la organización B**, incluidos sus nombres y correos. Es la última fuga cross-tenant que quedaba viva, y pertenece al mismo dominio que esta fase —quién puede ver qué—, así que se cierra aquí en lugar de arrastrarla a F1.

## 3. Qué cambia

| Concepto | Antes | Después |
|---|---|---|
| Plano del `ADMIN` | Superconjunto de todo: podía todo lo del `MANAGER` y además crear administradores | Plano propio: organizaciones y sus gestores. Sin acceso a leads, reglas, grupos ni asesores |
| Organización | UUID libre sin respaldo en base de datos | Entidad `Tenant` con tabla, ciclo de vida y clave foránea |
| Alta de una organización | No existía | `POST /api/v1/tenants` crea organización y su gestor inicial en una sola transacción |
| `GET /agents` | Cualquier autenticado ve los de todas las organizaciones | Sólo `MANAGER`, y sólo los de la suya |
| Identidad del usuario actual | No se podía consultar | `GET /api/v1/auth/me` |
| `can_access_tenant` para `ADMIN` | Siempre `True` | Siempre `False`: el `ADMIN` no accede a datos de organización |

---

## 4. Decisiones de diseño

| # | Decisión | Alternativa descartada | Motivo |
|---|---|---|---|
| E1 | El `ADMIN` no accede a datos operativos de ninguna organización | Impersonación con `?tenant_id=` | Elimina la ambigüedad en vez de gestionarla, y acota el daño de una credencial comprometida |
| E2 | Crear organización y su gestor inicial es **una sola operación atómica** | Dos llamadas independientes | Una organización sin gestor es inútil y nadie puede entrar en ella: dejarla a medias es un estado que no aporta nada. Además evita una ventana en la que la organización existe sin dueño |
| E3 | El `ADMIN` ve un **recuento** de asesores por organización, no la lista | Ningún dato agregado / la lista completa | Un panel de plataforma sin ninguna señal de actividad es inútil, pero un recuento no revela identidades. Es el mínimo que hace navegable el plano de plataforma sin romper E1 |
| E4 | `GET /agents` queda restringido a `MANAGER` | Permitirlo también a `AGENT` filtrando por organización | Un asesor no necesita el directorio de sus compañeros para su único caso de uso, que es ver sus leads. Menos superficie, menos datos personales expuestos |
| E5 | El `AGENT` consulta su propio perfil por `GET /auth/me` | Reutilizar `GET /agents/{id}` con comprobación de identidad | Un endpoint de identidad es lo que el frontend necesita de verdad (rol, organización, nombre) y no obliga a exponer el listado |
| E6 | Se conserva la regla de bootstrap, ahora explícita: el primer usuario del sistema es el `ADMIN` de plataforma | Semilla por variable de entorno o comando aparte | Ya funciona, está probada, y no exige orquestación adicional para arrancar el sistema en una demostración |
| E7 | Desactivar una organización desactiva en cascada a sus usuarios | Borrado físico, o desactivar sólo la organización | El borrado destruye histórico. Desactivar sólo la organización dejaría credenciales válidas de usuarios que ya no deberían entrar |

---

## 5. Modelo de dominio

### 5.1 `Tenant` — organización cliente

Entidad nueva. Hasta ahora el identificador de organización circulaba libremente sin ninguna entidad que lo respaldara: cualquiera podía inventarse un UUID y el sistema lo aceptaba.

| Campo | Tipo | Obl. | Por defecto | Descripción |
|---|---|---|---|---|
| `id` | `TenantId` | sí | generado | Identidad de la organización. Es el valor que viaja en el claim `tenant_id` de los tokens de sus usuarios |
| `name` | `str` | sí | — | Nombre comercial. Es lo que el administrador de plataforma ve en su listado y lo único que identifica a la organización de cara a un humano |
| `slug` | `str` | sí | derivado de `name` | Identificador legible y estable, en minúsculas y sin espacios (`acme-corp`). Sirve para referirse a la organización en URLs y registros sin exponer el UUID, y para detectar altas duplicadas por nombre |
| `is_active` | `bool` | no | `True` | Una organización inactiva rechaza la autenticación de todos sus usuarios y la ingesta dirigida a ella, pero conserva íntegros sus datos. Permite suspender un cliente sin destruir nada |
| `created_at` | `datetime` | sí | ahora | Auditoría |

**Comportamiento:** `activate()`, `deactivate()`, `rename(name)`.

**Invariantes:**
- `name` no puede estar vacío ni ser sólo espacios.
- `slug` es único en todo el sistema; se deriva de `name` al crear y no cambia después, aunque la organización se renombre (renombrar no debe romper referencias existentes).

### 5.2 `Agent` — sin cambios estructurales

La entidad no cambia. Lo que cambia es el **significado** de su `tenant_id` nulo, que hasta ahora era ambiguo:

| `role` | `tenant_id` | Significado |
|---|---|---|
| `ADMIN` | **siempre** `None` | Administrador de plataforma. Opera sobre organizaciones, nunca dentro de una |
| `MANAGER` | **siempre** presente | Gestor de esa organización |
| `AGENT` | **siempre** presente | Asesor de esa organización |

Esta correspondencia pasa a ser una invariante verificada, no una convención implícita. Un `MANAGER` sin organización o un `ADMIN` con ella son estados imposibles de construir.

### 5.3 Enumerados

`AgentRole` no cambia sus valores (`ADMIN`, `MANAGER`, `AGENT`); cambia lo que el `ADMIN` puede hacer.

---

## 6. Política de autorización

### 6.1 Los dos planos

**Plano de plataforma** — sólo `ADMIN`:

- Crear una organización junto con su gestor inicial
- Listar organizaciones, con el recuento de asesores de cada una
- Activar y desactivar organizaciones
- Renombrar organizaciones

**Plano de organización** — `MANAGER` y `AGENT`, siempre acotados a la suya:

- Todo lo operativo: asesores, grupos, reglas, leads

Ninguna operación pertenece a los dos planos. La frontera es la respuesta a "¿esta operación toca datos de negocio de una organización concreta?".

### 6.2 Matriz de permisos corregida

Esta tabla **sustituye** a la de la sección 9.2 del spec del MVP.

| Operación | `ADMIN` | `MANAGER` | `AGENT` |
|---|---|---|---|
| Crear organización con su gestor | ✅ | ❌ | ❌ |
| Listar organizaciones | ✅ | ❌ | ❌ |
| Activar / desactivar / renombrar organización | ✅ | ❌ | ❌ |
| Crear, editar y desactivar asesores | ❌ | ✅ los de su organización | ❌ |
| Listar asesores | ❌ | ✅ los de su organización | ❌ |
| Gestionar grupos, reglas y fuentes | ❌ | ✅ los de su organización | ❌ |
| Ver todos los leads | ❌ | ✅ los de su organización | ❌ |
| Ver sus leads asignados | ❌ | ✅ | ✅ |
| Asignar manualmente y descartar | ❌ | ✅ los de su organización | ❌ |
| Consultar la propia identidad | ✅ | ✅ | ✅ |

Las casillas del `ADMIN` que antes decían ✅ y ahora dicen ❌ son el cambio central de esta fase.

### 6.3 Cambios concretos en `AuthorizationPolicy`

| Método | Antes | Después |
|---|---|---|
| `can_access_tenant(actor, tenant_id)` | `True` para `ADMIN`; comparación para el resto | **`False` para `ADMIN`**; comparación para el resto |
| `can_manage_organization(actor)` | `role in (ADMIN, MANAGER)` | **`role == MANAGER`** |
| `can_manage_platform(actor)` | no existía | **`role == ADMIN`** |
| `can_create_agent_with_role(actor, role)` | `ADMIN` podía crear cualquier rol | Un `MANAGER` crea `MANAGER` y `AGENT` **en su organización**. Nadie crea un `ADMIN` por esta vía: el único administrador nace del bootstrap |
| `can_view_lead(...)` | sin cambios de forma | Deja de conceder acceso al `ADMIN`, por herencia de `can_access_tenant` |
| `can_list_agents(actor)` | no existía | **`role == MANAGER`** |

---

## 7. Contrato de API

### 7.1 Endpoints nuevos — plano de plataforma

```
POST   /api/v1/tenants          crear organización con su gestor inicial   [ADMIN]
GET    /api/v1/tenants          listar, con recuento de asesores           [ADMIN]
PATCH  /api/v1/tenants/{id}     renombrar, activar, desactivar             [ADMIN]
```

**`POST /api/v1/tenants`** — petición:

```json
{
  "name": "Acme Corp",
  "manager": {
    "name": "Ana Ruiz",
    "email": "ana@acme.test",
    "password": "..."
  }
}
```

Respuesta `201`:

```json
{
  "id": "…",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "is_active": true,
  "created_at": "…",
  "manager": { "id": "…", "name": "Ana Ruiz", "email": "ana@acme.test", "role": "MANAGER" }
}
```

Ambas escrituras ocurren en **una sola transacción** (decisión E2): si la creación del gestor falla —por ejemplo, por correo duplicado—, la organización tampoco se crea.

**`GET /api/v1/tenants`** — respuesta paginada donde cada elemento lleva `agent_count`, el recuento de asesores activos. Es un agregado, no una lista: no revela identidades (decisión E3).

**`PATCH /api/v1/tenants/{id}`** — acepta `name` y/o `is_active`. Desactivar arrastra a todos los usuarios de la organización (decisión E7).

### 7.2 Endpoint nuevo — identidad

```
GET /api/v1/auth/me       [cualquier autenticado]
```

```json
{
  "id": "…",
  "name": "Ana Ruiz",
  "email": "ana@acme.test",
  "role": "MANAGER",
  "tenant_id": "…",
  "tenant_name": "Acme Corp"
}
```

Para un `ADMIN`, `tenant_id` y `tenant_name` son nulos.

Es lo que el frontend necesita para decidir qué panel mostrar. Hoy el token lleva el rol como claim, pero la dependencia que resuelve la identidad lo ignora y relee de base de datos, así que el cliente no tiene forma de conocer su propio rol.

### 7.3 Endpoints modificados

| Endpoint | Cambio |
|---|---|
| `POST /api/v1/agents` | El bootstrap sigue creando el primer `ADMIN`. Fuera de él, sólo un `MANAGER` puede crear, siempre dentro de su organización, y sólo roles `MANAGER` o `AGENT`. El campo `tenant_id` **desaparece de la petición**: se toma del contexto |
| `GET /api/v1/agents` | Restringido a `MANAGER`. Devuelve sólo los de su organización. **Cierra la fuga descrita en §2** |
| `GET /api/v1/agents/{id}` | Restringido a `MANAGER`, y sólo si el agente pertenece a su organización. Devuelve `404` —no `403`— cuando pertenece a otra: responder `403` confirmaría que ese identificador existe |
| Todos los operativos | Un `ADMIN` recibe ahora `403` con un mensaje explícito, en lugar de comportarse de forma indefinida con una organización nula |

### 7.4 Contrato de puertos afectado

`AgentRepositoryPort` gana el criterio de organización, que hoy no admite en ningún método:

```python
def list_by_tenant(self, tenant_id: UUID, team: Optional[str] = None,
                   limit: int = 100, offset: int = 0) -> List[Agent]: ...
def count_by_tenant(self, tenant_id: UUID, team: Optional[str] = None) -> int: ...
def get_by_id_and_tenant(self, agent_id: UUID, tenant_id: UUID) -> Optional[Agent]: ...
def count_active_by_tenant(self, tenant_id: UUID) -> int: ...
```

Los métodos actuales sin organización (`list_active`, `count_active`, `get_by_id`) se conservan sólo donde el llamante no puede tener organización: la resolución de identidad a partir del token y la comprobación de bootstrap.

Puerto nuevo:

```python
class TenantRepositoryPort(abc.ABC):
    def save(self, tenant: Tenant) -> Tenant: ...
    def get_by_id(self, tenant_id: UUID) -> Optional[Tenant]: ...
    def get_by_slug(self, slug: str) -> Optional[Tenant]: ...
    def list_all(self, limit: int = 100, offset: int = 0) -> List[Tenant]: ...
    def count_all(self) -> int: ...
```

`UnitOfWorkPort` incorpora `tenants`.

---

## 8. Persistencia

Migración `002_tenants.sql`:

```sql
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agents_tenant ON agents (tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_email_per_tenant
    ON agents (tenant_id, email) WHERE tenant_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_platform_admin_email
    ON agents (email) WHERE tenant_id IS NULL;
```

Los tipos siguen la convención de la migración base (`TEXT` para identificadores y fechas, `INTEGER` para booleanos). Corregirlos a `UUID`, `TIMESTAMPTZ` y `BOOLEAN` corresponde a F1, que reescribe el esquema con tests funcionales que los cubren.

Los tres índices merecen explicación:

- `idx_agents_tenant` sostiene el filtro por organización que esta fase introduce en todas las consultas de asesores.
- `idx_agents_email_per_tenant` impide dos usuarios con el mismo correo dentro de una organización. Hoy no existe ninguna restricción de unicidad sobre `agents.email`, así que pueden coexistir duplicados y el login autentica contra una fila arbitraria.
- `idx_agents_platform_admin_email` aplica la misma unicidad entre administradores de plataforma, que no tienen organización y quedarían fuera del índice anterior.

**No se añade clave foránea de `agents.tenant_id` a `tenants.id`** en esta fase: las filas existentes apuntan a identificadores de organización que nunca tuvieron respaldo, y la restricción fallaría al aplicarse. La migración de F1, que reescribe los tipos, es el punto donde se saneará y se añadirá.

---

## 9. Migración de datos existentes

Una base de datos de desarrollo ya tiene agentes con `tenant_id` que no corresponden a ninguna fila de `tenants`. La migración `002` los deja como están: crea la tabla, no toca los datos.

Para que el sistema quede coherente, se añade un **comando de sincronización** que crea una organización por cada `tenant_id` distinto encontrado en `agents`, con un nombre derivado. Se ejecuta a mano, no al arrancar:

```bash
docker compose exec backend python -m infrastructure.cli.sync_tenants
```

Es la alternativa razonable a arrastrar datos inconsistentes o a exigir una base limpia. Para una demostración desde cero no hace falta: el flujo normal es bootstrap del `ADMIN` y luego crear organizaciones por API.

---

## 10. Estrategia de pruebas

Coherente con la establecida en F0.

| Nivel | Qué cubre |
|---|---|
| Unitario | La política con los dos planos, valor por valor de la matriz. Las invariantes de `Tenant`. La generación de `slug`. Los casos de uso de organización con dobles in-memory |
| Integración | El repositorio de organizaciones contra PostgreSQL. La migración `002`, incluyendo que los índices únicos rechazan de verdad los duplicados |
| Extremo a extremo | Un recorrido: bootstrap del `ADMIN` → crea organización con su gestor → el gestor entra y ve su organización vacía → el `ADMIN` recibe `403` al pedir leads → un asesor de otra organización recibe `404` al pedir un agente ajeno |
| Arquitectura | El guardián existente debe seguir en 4/4 |

**Test de regresión obligatorio para la fuga de §2:** dos organizaciones con un asesor cada una; el gestor de la primera lista asesores y debe ver exactamente uno, el suyo. Sin ese test, la fuga puede reaparecer sin que nadie lo note.

---

## 11. Qué NO entra en esta fase

- Los tipos de columna siguen siendo los de la migración base. F1 los corrige.
- `Agent.team` sigue siendo una cadena libre. F1 lo sustituye por `group_id`.
- No hay panel de métricas de plataforma más allá del recuento de asesores.
- No hay traspaso de organización entre gestores, ni un segundo administrador de plataforma: el único nace del bootstrap.
- No se toca el motor de asignación ni el ciclo de vida del lead.

---

## 12. Criterio de aceptación

1. El guardián de arquitectura sigue en 4/4.
2. Un `ADMIN` recibe `403` en todos los endpoints operativos, con un mensaje que explica que su plano es el de plataforma.
3. Un `MANAGER` sólo ve asesores de su organización, demostrado con el test de regresión de dos organizaciones.
4. Un `AGENT` recibe `403` al listar asesores, y `GET /auth/me` le devuelve su identidad.
5. `POST /api/v1/tenants` con un correo de gestor ya existente no deja la organización creada a medias.
6. El sistema arranca desde volumen vacío, aplica ambas migraciones, y el recorrido completo funciona contra los contenedores.
