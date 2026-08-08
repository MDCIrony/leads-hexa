# Tarea 3 — La etapa de viabilidad

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, las tres
> decisiones que el plan cierra, el harness y lo que la fase no hace. Vinculan a esta tarea.

Construye la etapa que hoy no existe: **¿se puede trabajar este lead?**, respondida por reglas del
gestor y no por un corte de puntuación escrito en el código. Corta el flujo: lo que descalifica no se
puntúa ni se reparte.

Es la tarea que demuestra los criterios de aceptación 1 y 2 de la fase.

## Ficheros

**Crear:**

| Fichero | Contenido |
|---|---|
| `backend/src/domain/entities/disqualification_rule.py` | La entidad |
| `backend/src/domain/services/viability_engine.py` | El motor |
| `backend/src/application/ports/output/disqualification_rule_repository_port.py` | El puerto |
| `backend/src/infrastructure/adapters/output/persistence/raw_sql_disqualification_rule_repository.py` | El adaptador SQL |
| `backend/src/application/ports/input/disqualification_rule_use_case_ports.py` | Los cuatro ABC |
| `backend/src/application/use_cases/disqualification_rule_use_cases.py` | Los cuatro casos de uso |
| `backend/tests/unit/domain/test_disqualification_rule.py` | Entidad y motor |
| `backend/tests/e2e/test_disqualification_rules.py` | CRUD y aislamiento |

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/domain/entities/lead.py` | Campo `disqualification_reason` y método `disqualify` |
| `backend/src/infrastructure/adapters/output/persistence/raw_sql_lead_repository.py` | Lee y escribe la columna nueva |
| `backend/src/application/ports/output/unit_of_work_port.py` | Declara `disqualification_rules` |
| `backend/src/infrastructure/adapters/output/persistence/postgres_unit_of_work.py` | Instancia el repositorio |
| `backend/tests/unit/mocks/in_memory_uow.py` | El repositorio in-memory y su registro |
| `backend/src/application/use_cases/ingest_lead_use_case.py` | La etapa entra en el pipeline |
| `backend/src/application/dtos/commands.py` | Comandos de crear y actualizar |
| `backend/src/application/dtos/queries.py` | `GetDisqualificationRulesQuery` |
| `backend/src/infrastructure/adapters/input/api/schemas.py` | Tres esquemas |
| `backend/src/infrastructure/adapters/input/api/rule_router.py` | Cuatro endpoints |
| `backend/src/infrastructure/adapters/input/api/dependencies.py` | Cuatro proveedores |
| `backend/src/infrastructure/adapters/input/api/exception_handlers.py` | `DISQUALIFICATION_RULE_NOT_FOUND` → 404 |

**Consume de tareas previas:** `Criterion` con `create`/`matches`/`as_dict`/`from_dict`, la función
`all_match`, y la tabla `disqualification_rules` con la columna `leads.disqualification_reason`, que
la migración 007 de la Tarea 1 ya creó. **No escribas ninguna migración nueva.**

**Lee sólo como patrón, si lo necesitas:** `lead_source.py`, `raw_sql_lead_source_repository.py`,
`lead_source_use_cases.py`, `source_router.py`. El CRUD de `LeadSource` es la forma canónica.

## Paso 1: el lead sabe por qué lo descartaron

En `lead.py`, junto a `discard_reason`, que ya existe y es el precedente exacto:

```python
    disqualification_reason: Optional[str] = None
```

Añádelo al dataclass, a `create()` y a la construcción del final de `create()`, con la misma forma
que `discard_reason`.

Y el método, junto a `qualify`:

```python
    def disqualify(self, reason: str) -> None:
        """A machine decision, carrying the rule's name as its reason.

        Distinct from discard(), where a person looked at the lead and wrote
        why. Merging them would cost the manager the only signal that tells a
        badly written rule from a genuinely bad lead."""
        self.status = LeadStatus.DISQUALIFIED
        self.disqualification_reason = reason
```

**No toques `_ASSIGNABLE` ni `_DISCARDABLE`.** Que un lead descalificado no se pueda asignar ni
descartar es correcto y ya está cubierto por `test_lead_state_machine.py`.

En `raw_sql_lead_repository.py`, la columna nueva entra en el `INSERT`, en el `ON CONFLICT DO UPDATE`
y en la reconstrucción de la fila. **Es el fichero que más fácil se olvida:** sin él el motivo existe
en la entidad, existe en la tabla y se pierde en cada ida y vuelta.

## Paso 2: la entidad

`disqualification_rule.py`:

```python
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.criterion import Criterion, all_match

if TYPE_CHECKING:
    from domain.entities.lead import Lead


@dataclass
class DisqualificationRule:
    """Says a lead cannot be worked at all, and why.

    Viability is a binary question, so it gets a binary tool instead of a
    number: expressing "no way of contacting them" as a -9999 penalty let any
    other rule rescue the lead by accident."""

    id: UUID
    tenant_id: UUID
    name: str
    conditions: List[Criterion]
    priority: int = 0
    is_active: bool = True

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID],
        name: str,
        conditions: List[Union[Criterion, Dict[str, Any]]],
        priority: int = 0,
        is_active: bool = True,
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "DisqualificationRule":
        clean_name = (name or "").strip()
        if not clean_name:
            raise DomainException(
                "La regla necesita un nombre: es el motivo que verá el gestor",
                error_code="INVALID_RULE_NAME",
            )
        parsed = [c if isinstance(c, Criterion) else Criterion.from_dict(c) for c in conditions]
        if not parsed:
            # A rule with no conditions holds for every lead, so it would
            # disqualify the entire organization on the next ingestion.
            raise DomainException(
                "Una regla de descalificación necesita al menos una condición",
                error_code="INVALID_RULE_CONDITIONS",
            )
        return cls(
            id=UUID(str(rule_id)) if rule_id else uuid.uuid4(),
            tenant_id=UUID(str(tenant_id)),
            name=clean_name,
            conditions=parsed,
            priority=priority,
            is_active=is_active,
        )

    def matches(self, lead: "Lead") -> bool:
        return all_match(self.conditions, lead)
```

`field` no se usa: **no lo importes**.

La lista vacía se rechaza (R3) y es la diferencia con `ScoringRule`. El nombre es obligatorio porque
**es el motivo que se muestra**, no una etiqueta interna.

## Paso 3: el motor

`viability_engine.py`, con la forma de `scoring_engine.py`:

```python
from typing import List, Optional

from domain.entities.disqualification_rule import DisqualificationRule
from domain.entities.lead import Lead


class ViabilityEngine:
    """Answers whether a lead can be worked at all, before it is scored."""

    def evaluate(self, lead: Lead, rules: List[DisqualificationRule]) -> Optional[DisqualificationRule]:
        """Returns the first rule that disqualifies the lead, or None.

        The first one wins rather than all of them: the lead records one
        reason, and priority is what the manager uses to decide which."""
        for rule in self._ordered(rules):
            if rule.matches(lead):
                return rule
        return None

    @staticmethod
    def _ordered(rules: List[DisqualificationRule]) -> List[DisqualificationRule]:
        return sorted(
            (r for r in rules if r.is_active),
            key=lambda r: (-r.priority, str(r.id)),
        )
```

El desempate por `id` como cadena replica el de los otros dos motores: sin él, dos reglas de igual
prioridad se resuelven por el orden en que la base las devolvió.

## Paso 4: puerto, adaptadores y unidad de trabajo

El puerto, con la forma de `lead_source_repository_port.py`:

```python
class DisqualificationRuleRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, rule: DisqualificationRule) -> DisqualificationRule: ...

    @abc.abstractmethod
    def get_by_id_and_tenant(self, rule_id: UUID, tenant_id: UUID) -> Optional[DisqualificationRule]: ...

    @abc.abstractmethod
    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[DisqualificationRule]: ...

    @abc.abstractmethod
    def count_by_tenant(self, tenant_id: UUID) -> int: ...

    @abc.abstractmethod
    def delete(self, rule_id: UUID, tenant_id: UUID) -> bool: ...
```

`delete` filtra por `tenant_id` **dentro del `DELETE`**, no sólo antes: es la diferencia con
`delete_assignment_rule`, que hoy borra por id suelto y depende de que el caso de uso haya
comprobado la propiedad.

Las tres implementaciones van juntas y **omitir una rompe la suite entera**:

1. `raw_sql_disqualification_rule_repository.py` — SQL crudo, marcadores `%s` (C3). `conditions` se
   guarda con `Jsonb([c.as_dict() for c in rule.conditions])` y se lee con `row["conditions"] or []`
2. `InMemoryDisqualificationRuleRepository` en `in_memory_uow.py`
3. El registro en ambos UoW: `unit_of_work_port.py` declara
   `disqualification_rules: DisqualificationRuleRepositoryPort`, y `postgres_unit_of_work.py` lo
   instancia en `__enter__` con los demás

## Paso 5: la etapa entra en el pipeline

En `ingest_lead_use_case.py`, el motor se instancia en `__init__` junto a los otros dos
(`self.viability_engine = ViabilityEngine()`), y el bloque de puntuación queda envuelto:

```python
            # Viability runs first and cuts the flow: scoring and routing
            # something nobody can work is wasted work with a misleading result.
            breakdown = ScoreBreakdown(applied=[], total=0)
            breached = self.viability_engine.evaluate(
                lead, self.uow.disqualification_rules.list_by_tenant(lead.tenant_id.value, limit=10_000)
            )
            if breached is not None:
                lead.disqualify(breached.name)
            else:
                scoring_rules = self.uow.rules.get_scoring_rules_by_tenant(lead.tenant_id.value)
                breakdown = self.scoring_engine.evaluate(lead, scoring_rules)
                # The rules that produced a score can be edited or deleted
                # later, so the lead keeps its own record to explain itself.
                lead.score_breakdown = breakdown.applied
                lead.qualify(self.threshold_qualified, self.threshold_disqualified)

                if lead.status == LeadStatus.QUALIFIED:
                    ...   # el bloque de asignación se queda EXACTAMENTE como está
```

`breakdown` se inicializa antes del `if` porque el `return` final usa
`applied_rules_count=len(breakdown.applied)`: sin eso, un lead descalificado revienta con
`UnboundLocalError` justo en el camino que la fase añade.

**`lead.qualify(...)` conserva sus dos umbrales en esta tarea.** Los retira la Tarea 4; tocarlo aquí
mezclaría dos cambios que se revisan mejor por separado.

El `limit=10_000` replica lo que ya hace la carga de grupos en este mismo bloque.

## Paso 6: el CRUD

Cuatro endpoints en `rule_router.py`, todos con
`context: RequestContext = Depends(require_organization_manager)`:

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/api/v1/rules/disqualification` | Crea |
| `GET` | `/api/v1/rules/disqualification` | Lista paginada |
| `PATCH` | `/api/v1/rules/disqualification/{rule_id}` | Actualiza, patrón «`None` = sin cambio» |
| `DELETE` | `/api/v1/rules/disqualification/{rule_id}` | Borra |

Los esquemas siguen el patrón de `LeadSource`, con `CriterionSchema` de la Tarea 2:

```python
class DisqualificationRuleCreate(BaseModel):
    name: str
    conditions: List[CriterionSchema]
    priority: int = 0
    is_active: bool = True


class DisqualificationRuleUpdate(BaseModel):
    name: Optional[str] = None
    conditions: Optional[List[CriterionSchema]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class DisqualificationRuleResponse(BaseModel):
    id: str
    name: str
    conditions: List[CriterionSchema]
    priority: int
    is_active: bool


class PaginatedDisqualificationRulesResponse(BaseModel):
    items: List[DisqualificationRuleResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
```

El paginado se construye como en `source_router.py:51-68`: `has_more=(offset + len(items)) < total`.

**No pongas un validador de longitud mínima en `conditions`.** La rechaza el dominio con
`INVALID_RULE_CONDITIONS`, que es donde vive la regla; duplicarla en Pydantic daría un `422` sin
código de error en vez del `400` con su código.

Los casos de uso replican `lead_source_use_cases.py`, con el helper de C5 delante:

```python
def _get_owned_rule(uow: UnitOfWorkPort, tenant_id: UUID, rule_id: UUID) -> DisqualificationRule:
    """Una regla de otra organización debe leerse como inexistente."""
    rule = uow.disqualification_rules.get_by_id_and_tenant(rule_id, tenant_id)
    if rule is None:
        raise DomainException(
            "La regla no existe",
            error_code="DISQUALIFICATION_RULE_NOT_FOUND",
        )
    return rule
```

Y `exception_handlers.py` necesita la fila `"DISQUALIFICATION_RULE_NOT_FOUND": 404` en
`STATUS_BY_ERROR_CODE`, **o C5 se rompe en silencio** devolviendo 400. Es el error que ya costó un
ciclo en F2b.

## Tests

**`test_disqualification_rule.py`** (marcador `unit`):

| Caso | Esperado |
|---|---|
| Regla sin condiciones | `INVALID_RULE_CONDITIONS` |
| Regla sin nombre o sólo espacios | `INVALID_RULE_NAME` |
| Regla con una condición que se cumple | `matches` verdadero |
| El motor sin reglas | `None` |
| El motor con una regla inactiva que se cumpliría | `None` |
| Dos reglas se cumplen, prioridades distintas | Devuelve la de **mayor** prioridad |
| Dos reglas se cumplen, misma prioridad | Devuelve siempre la misma (desempate estable por id) |

Y **el caso que da nombre a la fase**, con su tabla entera:

| Lead | Teléfono | Correo | Esperado |
|---|---|---|---|
| Ana | — | `ana@empresa.com` | **No** se descalifica |
| Beto | `600123456` | — | **No** se descalifica |
| Carla | — | — | **Se descalifica** |

Escrito como **una sola regla con dos condiciones** `IS_EMPTY` sobre `phone` y sobre `email`. Es el
criterio de aceptación 1 y la razón de que las condiciones sean una lista: con dos reglas sueltas,
dos de los tres casos salen mal.

**`test_disqualification_rules.py`** (e2e):

| Caso | Esperado |
|---|---|
| Crear, listar, actualizar y borrar | El ciclo completo |
| Crear con `conditions: []` | `400` con `INVALID_RULE_CONDITIONS` |
| `GET`, `PATCH` o `DELETE` de una regla de otra organización | **404**, nunca 403 |
| Un asesor (`AGENT`) llama a cualquiera de los cuatro | `403` |
| Ingerir un lead sin teléfono ni correo con la regla activa | El lead queda `DISQUALIFIED` con `disqualification_reason` igual al **nombre de la regla** |
| Ese mismo lead | `score` **cero** y sin desglose: no se puntuó |

El último par es el criterio de aceptación 2: el motivo es el de la regla, no una puntuación.

La ingesta es asíncrona desde F2d: usa el helper `ingest_and_resolve` de
`backend/tests/e2e/_intake_helpers.py` y consulta el lead después.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q
cd .. && ./scripts/verify-e2e.sh            # debe seguir verde: no hay reglas sembradas
git commit -m "feat(domain): let the manager say which leads cannot be worked"
```

`verify-e2e.sh` sigue verde porque ninguna organización del harness tiene reglas de descalificación,
y sin reglas el motor devuelve `None` y el pipeline se comporta igual que antes. Si se pone rojo,
algo cambió de comportamiento sin reglas y eso es un fallo de la tarea.
