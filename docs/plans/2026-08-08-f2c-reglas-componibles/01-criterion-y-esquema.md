# Tarea 1 — El esquema y `Criterion`

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, las tres
> decisiones que el plan cierra, el harness y lo que la fase no hace. Vinculan a esta tarea.

Aditiva por completo: crea la gramática de condiciones y **toda** la migración de la fase, sin que
nadie use lo nuevo todavía. `ScoringRule` pasa a delegar en `Criterion` conservando su forma externa,
así que ningún test existente cambia de resultado.

## Ficheros

**Crear:**

| Fichero | Contenido |
|---|---|
| `backend/migrations/007_composable_rules.sql` | Toda la migración de la fase |
| `backend/src/domain/value_objects/criterion.py` | El value object y su evaluación |
| `backend/tests/unit/domain/test_criterion.py` | Tests del value object |

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/domain/value_objects/enums.py` | `Operator` gana `IS_EMPTY` e `IS_NOT_EMPTY` |
| `backend/src/domain/entities/rule.py` | `ScoringRule` delega su evaluación en `Criterion` |

**Lee sólo como patrón, si lo necesitas:** `migrations/006_intake_jobs.sql`,
`domain/value_objects/score_breakdown.py`.

## Paso 1: los dos operadores nuevos

En `enums.py`, dentro de `Operator`, **al final** para no alterar el orden de los existentes:

```python
class Operator(str, Enum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"
    CONTAINS = "CONTAINS"
    IN = "IN"
    # Emptiness is a question about presence, not about value, and it is the
    # only way to express "has no way of being contacted".
    IS_EMPTY = "IS_EMPTY"
    IS_NOT_EMPTY = "IS_NOT_EMPTY"
```

## Paso 2: `criterion.py`

Fichero nuevo. Se lleva de `rule.py` la lista blanca, el prefijo, el centinela y los cuatro
comparadores **sin cambiarles el comportamiento**:

```python
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from domain.exceptions import DomainException
from domain.value_objects.enums import Operator

if TYPE_CHECKING:
    from domain.entities.lead import Lead


# Reflection over any attribute name let a rule read tenant_id or an internal
# value object. Scoring is a business concept: these are the fields a manager
# may reason about, plus anything the source itself supplied.
EVALUABLE_FIELDS = frozenset(
    {"first_name", "last_name", "email", "company", "industry", "budget", "phone", "score"}
)
_CUSTOM_PREFIX = "custom_attributes."
_MISSING = object()


@dataclass(frozen=True)
class Criterion:
    """One condition of a rule: this field, compared this way, to this value.

    Shared by the three stages — viability, scoring and assignment — so a
    manager learns to write a condition once and reuses it everywhere."""

    field: str
    operator: Operator
    value: Any = None

    @classmethod
    def create(
        cls,
        field: str,
        operator: Union[Operator, str],
        value: Any = None,
    ) -> "Criterion":
        clean_field = (field or "").strip()
        if not clean_field:
            raise DomainException(
                "El campo de la condición no puede estar vacío",
                error_code="INVALID_RULE_FIELD",
            )
        if not clean_field.startswith(_CUSTOM_PREFIX) and clean_field not in EVALUABLE_FIELDS:
            raise DomainException(
                f"El campo '{clean_field}' no es evaluable",
                error_code="FIELD_NOT_SCORABLE",
            )
        op = Operator(operator) if isinstance(operator, str) else operator
        if op == Operator.IN and not isinstance(value, (list, tuple)):
            raise DomainException(
                "El operador IN exige una lista de valores",
                error_code="INVALID_RULE_VALUE",
            )
        return cls(field=clean_field, operator=op, value=value)

    def matches(self, lead: "Lead") -> bool:
        actual = self._field_value(lead)

        # Emptiness is answered before the missing-field short circuit on
        # purpose: an absent field IS empty, and routing it through the branch
        # below would make IS_EMPTY false in exactly the case it must detect.
        if self.operator == Operator.IS_EMPTY:
            return self._is_empty(actual)
        if self.operator == Operator.IS_NOT_EMPTY:
            return not self._is_empty(actual)

        if actual is _MISSING:
            # A lead with no such field genuinely does not equal the target,
            # so only NOT_EQUALS is satisfied by absence.
            return self.operator == Operator.NOT_EQUALS

        if self.operator == Operator.EQUALS:
            return self._equal(actual, self.value)
        if self.operator == Operator.NOT_EQUALS:
            return not self._equal(actual, self.value)
        if self.operator == Operator.GREATER_THAN:
            return self._compare(actual, self.value, greater=True)
        if self.operator == Operator.LESS_THAN:
            return self._compare(actual, self.value, greater=False)
        if self.operator == Operator.CONTAINS:
            if isinstance(actual, str):
                return str(self.value) in actual
            if isinstance(actual, (list, tuple, dict)):
                return self.value in actual
            return False
        if self.operator == Operator.IN:
            return isinstance(self.value, (list, tuple)) and self._in(actual, self.value)
        return False

    def as_dict(self) -> Dict[str, Any]:
        """JSONB-serialisable form. The operator travels as its plain value."""
        return {"field": self.field, "operator": self.operator.value, "value": self.value}

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Criterion":
        return cls.create(
            field=raw.get("field", ""),
            operator=raw.get("operator", Operator.EQUALS),
            value=raw.get("value"),
        )

    @staticmethod
    def _is_empty(actual: Any) -> bool:
        if actual is _MISSING or actual is None:
            return True
        # A spreadsheet column left blank arrives as spaces. A rule that should
        # visibly match and does not is indistinguishable from a broken one.
        return isinstance(actual, str) and not actual.strip()

    def _field_value(self, lead: "Lead") -> Any:
        if self.field.startswith(_CUSTOM_PREFIX):
            key = self.field[len(_CUSTOM_PREFIX):]
            return lead.custom_attributes.get(key, _MISSING)
        raw = getattr(lead, self.field, _MISSING)
        if raw is _MISSING or raw is None:
            return _MISSING
        # Value objects expose their payload as .value or .amount.
        for attr in ("amount", "value"):
            if hasattr(raw, attr):
                return getattr(raw, attr)
        return raw

    @staticmethod
    def _equal(actual: Any, expected: Any) -> bool:
        if actual == expected:
            return True
        as_numbers = Criterion._as_decimals(actual, expected)
        if as_numbers is not None:
            return as_numbers[0] == as_numbers[1]
        return str(actual) == str(expected)

    @staticmethod
    def _compare(actual: Any, expected: Any, greater: bool) -> bool:
        as_numbers = Criterion._as_decimals(actual, expected)
        if as_numbers is None:
            return False
        left, right = as_numbers
        return left > right if greater else left < right

    @staticmethod
    def _in(actual: Any, options: Union[list, tuple]) -> bool:
        return any(Criterion._equal(actual, option) for option in options)

    @staticmethod
    def _as_decimals(left: Any, right: Any) -> Optional[tuple]:
        """Decimal, never float: money compared through binary floating point
        gives wrong answers for values a manager typed exactly."""
        try:
            return Decimal(str(left)), Decimal(str(right))
        except (InvalidOperation, ValueError, TypeError):
            return None


def all_match(conditions: List[Criterion], lead: "Lead") -> bool:
    """A rule holds when every one of its conditions holds.

    There is no OR: alternatives are written as separate rules. `all` over an
    empty list is True, which is what an assignment rule with no conditions
    needs — it discriminates by score band alone."""
    return all(condition.matches(lead) for condition in conditions)
```

`uuid` no se usa en este fichero: **no lo importes**. Está listado arriba sólo porque el original lo
tenía; bórralo si tu editor lo arrastra.

## Paso 3: `ScoringRule` delega

En `rule.py`, `ScoringRule` **conserva sus campos y su factoría tal cual** —la Tarea 2 los cambia, no
ésta— y sustituye su evaluación por una delegación. Borra de `rule.py` los métodos `_field_value`,
`_equal`, `_compare`, `_in`, `_as_decimals` y `matches`, y deja:

```python
    def matches(self, lead: "Lead") -> bool:
        return self.as_criterion().matches(lead)

    def as_criterion(self) -> Criterion:
        # Uses the plain constructor, not create(): the field was already
        # validated when the rule was built, and re-validating here would make
        # a rule stored before the allow-list existed unreadable.
        return Criterion(field=self.field, operator=self.operator, value=self.value)
```

`SCORABLE_FIELDS` y `_CUSTOM_PREFIX` **se quedan en `rule.py`** como reexportación, porque
`ScoringRule.create` los usa y hay tests que los importan de ahí:

```python
from domain.value_objects.criterion import EVALUABLE_FIELDS as SCORABLE_FIELDS, _CUSTOM_PREFIX
```

`_MISSING` ya no se usa en `rule.py`: bórralo.

**Comprueba que `Decimal`, `InvalidOperation` y `Any` sigan usándose en `rule.py`** después de mover
los comparadores. Si no, quita esos imports.

## Paso 4: la migración

`007_composable_rules.sql`. Es la **única** migración de la fase: crea todo el esquema que las tareas
2, 3 y 4 van a consumir. Estilo de la 006 —comentarios que explican el porqué— e **idempotente** (C9).

```sql
-- One column instead of a conditions table: a criterion is always read whole
-- with its rule and never queried on its own, so a join would buy nothing.
ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS conditions JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE assignment_rules ADD COLUMN IF NOT EXISTS conditions JSONB NOT NULL DEFAULT '[]'::jsonb;

-- The reason travels as text, not as a rule id: deleting the rule must not
-- leave the lead unable to explain itself. Same call as ScoreBreakdown.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS disqualification_reason TEXT;

-- Guarded by the column's own existence rather than by a migration version:
-- test_migration_runner re-runs this whole file after the columns are gone.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scoring_rules' AND column_name = 'field'
    ) THEN
        UPDATE scoring_rules
        SET conditions = jsonb_build_array(
            jsonb_build_object('field', field, 'operator', operator, 'value', value)
        )
        WHERE conditions = '[]'::jsonb;
    END IF;
END $$;

ALTER TABLE scoring_rules DROP COLUMN IF EXISTS field;
ALTER TABLE scoring_rules DROP COLUMN IF EXISTS operator;
ALTER TABLE scoring_rules DROP COLUMN IF EXISTS value;

CREATE TABLE IF NOT EXISTS disqualification_rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    priority INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_disqualification_rules_tenant
    ON disqualification_rules (tenant_id, priority DESC);
```

**El `DO $$` es la parte delicada.** `test_migration_runner.py` dropea `schema_migrations` y
reejecuta cada fichero entero: en la segunda pasada las columnas `field`, `operator` y `value` ya no
existen, y un `UPDATE` que las nombre falla al **parsear**, no al ejecutar, así que no basta con un
`WHERE` que no seleccione nada. El bloque condicional es lo que lo hace reejecutable.

**El backfill es lo que cumple el criterio de aceptación 6:** una regla escrita antes de esta fase
sigue funcionando porque su trío se convierte en una condición equivalente.

## Tests — `test_criterion.py`

Marcador `unit`, sin base de datos. Construye leads con la factoría que ya usan
`tests/unit/domain/test_scoring_rule.py` — **ábrelo para copiar cómo fabrica un `Lead`**, es la única
lectura fuera de lista que esta tarea necesita.

| Caso | Esperado |
|---|---|
| `EQUALS` entre `"100"` y `100` | Verdadero: la coerción numérica se conserva |
| `NOT_EQUALS` aplica la misma coerción que `EQUALS` | No pueden ser ambos verdaderos para el mismo par |
| Comparación numérica con decimales | Conserva precisión, no pasa por `float` |
| `IN` con una lista real | Verdadero si alguno coincide |
| `CONTAINS` dentro de una cadena | Verdadero |
| Campo ausente con operador positivo | Falso |
| Campo ausente con `NOT_EQUALS` | **Verdadero** |
| Campo fuera de la lista blanca (`tenant_id`) | `FIELD_NOT_SCORABLE` |
| `custom_attributes.lo_que_sea` | Siempre permitido |
| `IN` con un valor que no es lista | `INVALID_RULE_VALUE` |
| Campo vacío o sólo espacios | `INVALID_RULE_FIELD` |

Y los que esta tarea habilita, que son el motivo de la fase:

| Caso | Esperado |
|---|---|
| `IS_EMPTY` sobre un campo **ausente** | **Verdadero** |
| `IS_EMPTY` sobre `None` en `custom_attributes` | Verdadero |
| `IS_EMPTY` sobre cadena vacía | Verdadero |
| `IS_EMPTY` sobre `"   "` (sólo espacios) | **Verdadero** — es una decisión de producto, no un detalle |
| `IS_EMPTY` sobre un valor real | Falso |
| `IS_NOT_EMPTY` es la negación exacta en los cinco casos anteriores | — |
| `all_match([])` | Verdadero |
| `all_match` con una que falla y otra que pasa | Falso |
| `as_dict` → `from_dict` conserva los tres campos | Ida y vuelta idéntica |

El caso de `"   "` merece su propio test con ese nombre: sin él, la regla «sin correo» no se cumple
para una fila de CSV con la columna en blanco, y eso es indistinguible de una regla rota.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q      # el dominio creció: verde sin base de datos
cd .. && ./scripts/verify-e2e.sh            # nada debería haber cambiado
git commit -m "feat(domain): give every stage one grammar for conditions"
```

**Los tests existentes de `ScoringRule` deben seguir pasando sin tocarlos.** Si alguno falla, la
delegación cambió comportamiento y eso es un fallo de esta tarea, no del test.
