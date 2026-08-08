# Tarea 2 — La puntuación compone condiciones

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, las tres
> decisiones que el plan cierra, el harness y lo que la fase no hace. Vinculan a esta tarea.

`ScoringRule` pasa de llevar un trío plano a llevar una lista de condiciones. Es el cambio que hace
expresable *«presupuesto alto **y** sector objetivo»* como una sola regla.

**Rompe el contrato de `POST /api/v1/rules/scoring`.** El cuerpo cambia de `field/operator/value` a
`conditions`. No se mantiene compatibilidad: el sistema no está desplegado y los únicos datos son de
prueba (spec §4).

## Ficheros

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/domain/entities/rule.py` | `ScoringRule` lleva `conditions`, y su factoría cambia de firma |
| `backend/src/application/dtos/commands.py` | `CreateScoringRuleCommand` lleva `conditions` |
| `backend/src/application/use_cases/rule_use_cases.py` | `CreateScoringRuleUseCase` construye los `Criterion` |
| `backend/src/infrastructure/adapters/output/persistence/raw_sql_rule_repository.py` | Lee y escribe la columna `conditions` |
| `backend/src/infrastructure/adapters/input/api/schemas.py` | `CriterionSchema`, y los dos esquemas de regla |
| `backend/src/infrastructure/adapters/input/api/rule_router.py` | Los dos endpoints de puntuación |
| `backend/tests/unit/mocks/in_memory_rule_repo.py` | Deduplica por id, como hace el SQL |
| `backend/tests/unit/domain/test_scoring_rule.py` | 11 tests: la construcción cambia |
| `backend/tests/unit/domain/test_scoring_engine.py` | 5 tests: la construcción cambia |
| `backend/tests/e2e/test_scoring_rule_value_types.py` | 3 tests: el cuerpo de la petición cambia |

**Consume de la Tarea 1:** `Criterion` con `create`, `matches`, `as_dict` y `from_dict`; la función de
módulo `all_match(conditions, lead)`; la columna `scoring_rules.conditions` y la retirada de
`field`/`operator`/`value`.

**No toques el motor de puntuación.** `scoring_engine.py` llama a `rule.matches(lead)` y esa firma no
cambia.

## Paso 1: la entidad

En `rule.py`, `ScoringRule` queda:

```python
@dataclass
class ScoringRule:
    """A rule that adds or subtracts points when all its conditions hold.

    Several conditions instead of one is what lets a manager write "high
    budget AND target industry" as a single rule. Alternatives are separate
    rules: there is no OR."""

    id: UUID
    tenant_id: UUID
    name: str
    conditions: List[Criterion]
    score_delta: int
    priority: int = 0
    is_active: bool = True

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID],
        name: str,
        conditions: List[Union[Criterion, Dict[str, Any]]],
        score_delta: int,
        priority: int = 0,
        is_active: bool = True,
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "ScoringRule":
        # Accepts dicts so the SQL adapter can hand over what JSONB gave it
        # without importing Criterion to rebuild each one.
        parsed = [c if isinstance(c, Criterion) else Criterion.from_dict(c) for c in conditions]
        return cls(
            id=UUID(str(rule_id)) if rule_id else uuid.uuid4(),
            tenant_id=UUID(str(tenant_id)),
            name=name,
            conditions=parsed,
            score_delta=score_delta,
            priority=priority,
            is_active=is_active,
        )

    def matches(self, lead: "Lead") -> bool:
        return all_match(self.conditions, lead)
```

**`as_criterion()` desaparece**: existía sólo para el paso intermedio de la Tarea 1.

La validación de campo ya no vive aquí — la hace `Criterion.create` —, así que borra de
`ScoringRule.create` los tres bloques de `raise DomainException`. La reexportación de
`SCORABLE_FIELDS` **se queda**: hay tests que la importan de `rule.py`.

Una lista de condiciones vacía en `ScoringRule` es **válida** y significa «se aplica siempre»
(R3 sólo la prohíbe en `DisqualificationRule`). No añadas una comprobación.

## Paso 2: el DTO y el caso de uso

En `commands.py`:

```python
@dataclass(frozen=True)
class CreateScoringRuleCommand:
    tenant_id: UUID
    name: str
    # Plain dicts, not Criterion: the DTO stays a transport shape and the use
    # case is where it becomes a domain object.
    conditions: List[Dict[str, Any]]
    score_delta: int
    priority: int = 0
    is_active: bool = True
```

En `rule_use_cases.py`, `CreateScoringRuleUseCase.execute` pasa `conditions=command.conditions`
directamente a `ScoringRule.create`, que ya sabe convertirlos. **No construyas los `Criterion` a
mano**: duplicaría la validación.

## Paso 3: el adaptador SQL

`save_scoring_rule` pierde tres columnas y gana una:

```python
    def save_scoring_rule(self, tenant_id: UUID, rule: ScoringRule) -> ScoringRule:
        self.connection.execute(
            """
            INSERT INTO scoring_rules (
                id, tenant_id, name, conditions, score_delta, priority, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                name = EXCLUDED.name,
                conditions = EXCLUDED.conditions,
                score_delta = EXCLUDED.score_delta,
                priority = EXCLUDED.priority,
                is_active = EXCLUDED.is_active
            """,
            (
                rule.id,
                tenant_id,
                rule.name,
                Jsonb([c.as_dict() for c in rule.conditions]),
                rule.score_delta,
                rule.priority,
                rule.is_active,
            ),
        )
        return rule
```

Y `get_scoring_rules_by_tenant` cambia sus tres claves por una:

```python
                ScoringRule.create(
                    tenant_id=r["tenant_id"],
                    rule_id=r["id"],
                    name=r["name"],
                    conditions=r["conditions"] or [],
                    score_delta=r["score_delta"],
                    priority=r["priority"],
                    is_active=r["is_active"],
                )
```

`or []` porque una fila anterior a la migración podría traer `NULL` si el `DEFAULT` no la alcanzó.

## Paso 4: los esquemas y el router

En `schemas.py`, un esquema nuevo y dos modificados:

```python
class CriterionSchema(BaseModel):
    field: str
    operator: Operator
    # Optional because IS_EMPTY and IS_NOT_EMPTY ask about presence, not value.
    value: Any = None


class ScoringRuleCreate(BaseModel):
    name: str
    conditions: List[CriterionSchema]
    score_delta: int
    priority: int = 0
    is_active: bool = True


class ScoringRuleResponse(BaseModel):
    id: str
    name: str
    conditions: List[CriterionSchema]
    score_delta: int
    priority: int
    is_active: bool
```

**No añadas un validador que exija `conditions` no vacía** (V1 de F2d sigue vigente en espíritu, y
R3 sólo la prohíbe en las reglas de descalificación).

En `rule_router.py`, extrae el mapeo a una función de módulo, porque los dos endpoints lo repiten:

```python
def _to_scoring_response(rule: ScoringRule) -> ScoringRuleResponse:
    return ScoringRuleResponse(
        id=str(rule.id),
        name=rule.name,
        conditions=[CriterionSchema(**c.as_dict()) for c in rule.conditions],
        score_delta=rule.score_delta,
        priority=rule.priority,
        is_active=rule.is_active,
    )
```

Y `create_scoring_rule` construye el comando con:

```python
        conditions=[c.model_dump() for c in request.conditions],
```

`model_dump()` deja el operador como su valor plano, que es justo lo que `Criterion.from_dict`
espera.

## Paso 5: el doble in-memory deduplica

`in_memory_rule_repo.py` guarda las reglas de puntuación en una lista con `append`, así que dos
guardados del mismo id producen dos reglas. El SQL real hace `ON CONFLICT (id) DO UPDATE`. Alinéalo:

```python
    def save_scoring_rule(self, tenant_id: UUID, rule: ScoringRule) -> ScoringRule:
        # Mirrors the SQL adapter's ON CONFLICT (id) DO UPDATE: appending made
        # a re-saved rule apply twice, which no real repository would do.
        bucket = self.scoring_rules.setdefault(tenant_id, [])
        for index, existing in enumerate(bucket):
            if existing.id == rule.id:
                bucket[index] = rule
                return rule
        bucket.append(rule)
        return rule
```

Es un arreglo pequeño y va aquí porque esta tarea es la primera que guarda la misma regla dos veces
en un test.

## Tests

**No cambies lo que los tests afirman.** Sólo cómo construyen la regla:

```python
# antes
rule = ScoringRule.create(tenant_id=t, name="x", field="budget",
                          operator=Operator.GREATER_THAN, value=1000, score_delta=10)

# después
rule = ScoringRule.create(tenant_id=t, name="x", score_delta=10, conditions=[
    Criterion.create(field="budget", operator=Operator.GREATER_THAN, value=1000),
])
```

Los casos de `test_scoring_rule.py` que comprueban validación de campo
(`test_a_field_outside_the_allow_list_is_rejected`, `test_custom_attributes_are_always_allowed`,
`test_the_in_operator_demands_a_list`) ahora fallan al construir el `Criterion`, no la regla. **El
código de error es el mismo**, así que la aserción no cambia; sólo la línea que lanza.

Tests nuevos, en `test_scoring_rule.py`:

| Caso | Esperado |
|---|---|
| Regla con dos condiciones, el lead cumple ambas | Aplica |
| Regla con dos condiciones, el lead cumple sólo una | **No aplica** |
| Regla con la lista vacía | Aplica siempre |
| Ida y vuelta por el repositorio in-memory guardando dos veces la misma regla | Una sola regla, la última |

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q
cd .. && ./scripts/verify-e2e.sh
```

`verify-e2e.sh` **debe seguir verde**: no crea reglas de puntuación por HTTP. Si se pone rojo,
revisa qué comprobación toca reglas y dilo en tu respuesta.

```bash
git commit -m "feat(domain): let a scoring rule demand several conditions at once"
```
