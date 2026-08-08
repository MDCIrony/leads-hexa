# Tarea 4 — Reparto por condiciones y retirada del umbral

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, las tres
> decisiones que el plan cierra, el harness y lo que la fase no hace. Vinculan a esta tarea.

Dos cambios que van juntos porque tocan la misma decisión: **el reparto gana el eje de atributo, y el
corte de puntuación deja de estar en el código**. Al terminar, ningún criterio comercial vive fuera
de la configuración del gestor.

Demuestra los criterios de aceptación 3, 4 y 5.

## Ficheros

**Modificar:**

| Fichero | Qué arrastra |
|---|---|
| `backend/src/domain/entities/rule.py` | `AssignmentRule` lleva `conditions` y sabe evaluarlas |
| `backend/src/domain/entities/lead.py` | `qualify()` se queda sin argumentos |
| `backend/src/domain/services/assignment_engine.py` | Filtra por banda **y** condiciones |
| `backend/src/application/use_cases/ingest_lead_use_case.py` | Deja de recibir y pasar los dos umbrales |
| `backend/src/application/dtos/commands.py` | Los dos comandos de regla de asignación |
| `backend/src/application/use_cases/rule_use_cases.py` | Crear y actualizar propagan `conditions` |
| `backend/src/infrastructure/adapters/output/persistence/raw_sql_rule_repository.py` | Lee y escribe `assignment_rules.conditions` |
| `backend/src/infrastructure/adapters/input/api/schemas.py` | Los tres esquemas de regla de asignación |
| `backend/src/infrastructure/adapters/input/api/rule_router.py` | `_to_response` y los dos endpoints de escritura |
| `backend/tests/unit/domain/test_assignment_rule.py` | 14 tests |
| `backend/tests/unit/domain/test_assignment_engine.py` | 13 tests |
| `backend/tests/unit/domain/test_entities.py` | El test que llama a `qualify` |
| `backend/tests/unit/application/test_ingest_lead_use_case.py` | Si construye el caso de uso con umbrales |

**Consume de tareas previas:** `Criterion`, `all_match`, la columna `assignment_rules.conditions` de
la migración 007, y la etapa de viabilidad de la Tarea 3, que es la que permite retirar el umbral sin
dejar la bandeja del gestor llena de basura.

## Paso 1: `AssignmentRule` gana condiciones

En `rule.py`, campo nuevo con valor por defecto **lista vacía**, que es lo que hace que las reglas
existentes sigan valiendo sin tocarlas:

```python
    conditions: List[Criterion] = field(default_factory=list)
```

`create()` y `restore()` lo aceptan con la misma conversión que `ScoringRule.create`:

```python
        parsed = [c if isinstance(c, Criterion) else Criterion.from_dict(c) for c in conditions or []]
```

Y el método que compone las dos preguntas:

```python
    def matches(self, lead: "Lead") -> bool:
        """Band and conditions, both required.

        An empty condition list means the rule discriminates by score alone,
        which is what every rule written before this phase does."""
        return self.matches_score(int(lead.score)) and all_match(self.conditions, lead)
```

**`matches_score` se queda tal cual.** Catorce tests la usan directamente y sigue siendo la pregunta
sobre la banda; `matches` la compone, no la sustituye.

## Paso 2: el motor filtra por las dos cosas

En `assignment_engine.py`, `_ordered_rules` pasa a recibir el lead entero:

```python
    @staticmethod
    def _ordered_rules(rules: List[AssignmentRule], lead: Lead) -> List[AssignmentRule]:
        applicable = [r for r in rules if r.is_active and r.matches(lead)]
        # The id breaks ties: without it, two rules of equal priority resolve
        # by whatever order the database returned them.
        return sorted(applicable, key=lambda r: (-r.priority, str(r.id)))
```

Y su llamada en `select_agent` cambia de `self._ordered_rules(rules, int(lead.score))` a
`self._ordered_rules(rules, lead)`.

Nada más del motor cambia: la cascada, los modos `ANY`/`ONLY`, la capacidad y las tres estrategias se
quedan exactamente como están.

## Paso 3: `qualify()` pierde sus umbrales

En `lead.py`:

```python
    def qualify(self) -> None:
        """NEW → QUALIFIED, with no threshold of its own.

        Viability already ruled out what cannot be worked, and the lowest band
        of the assignment rules is now the only score cut — written by the
        manager instead of frozen in the code. The old two-threshold version
        had two branches for three ranges, so a lead in between changed to
        nothing and stayed NEW forever."""
        self.status = LeadStatus.QUALIFIED
```

En `ingest_lead_use_case.py`:

- `__init__` pierde los parámetros `threshold_qualified` y `threshold_disqualified` y los dos
  atributos que guardaban
- la llamada pasa a `lead.qualify()`

**Comprueba quién construye `IngestLeadUseCase`** antes de terminar: `dependencies.py` y los tests
unitarios. Si alguno pasa los umbrales por nombre, revienta al importar.

## Paso 4: persistencia, DTOs y API

`raw_sql_rule_repository.py`: `conditions` entra en el `INSERT` de `save_assignment_rule`, en su
`ON CONFLICT DO UPDATE` y en `_to_assignment_rule`, con
`Jsonb([c.as_dict() for c in rule.conditions])` al escribir y `row["conditions"] or []` al leer.

`AssignmentRuleCreate`, `AssignmentRuleUpdate` y `AssignmentRuleResponse` ganan
`conditions: List[CriterionSchema]` (en `Update`, `Optional[...] = None` como el resto de sus
campos). `_to_response` en `rule_router.py` lo mapea con
`[CriterionSchema(**c.as_dict()) for c in rule.conditions]`.

`CreateAssignmentRuleCommand` y `UpdateAssignmentRuleCommand` lo llevan como
`List[Dict[str, Any]]` y `Optional[List[Dict[str, Any]]]`, igual que hizo la Tarea 2 con la
puntuación.

## Tests

**No cambies lo que los tests afirman.** En `test_assignment_engine.py`, las trece pruebas siguen
comprobando lo mismo; sólo cambia que `_ordered_rules` recibe el lead. Como llaman a `select_agent`
y no al método privado, **la mayoría no necesita ningún cambio**.

Casos nuevos en `test_assignment_rule.py`:

| Caso | Esperado |
|---|---|
| Regla con banda y sin condiciones | Se comporta igual que antes |
| Regla con banda y una condición que el lead cumple | Aplica |
| Regla con banda y una condición que el lead **no** cumple | **No aplica**, aunque la banda encaje |
| Regla cuya condición encaja pero la banda no | No aplica |

Casos nuevos en `test_assignment_engine.py`:

| Caso | Esperado |
|---|---|
| Dos reglas de la misma banda, una con condición de canal | El lead de ese canal va a la de la condición |
| El lead no cumple ninguna condición y sólo hay reglas condicionadas | `None`, y el caso de uso lo deja `UNASSIGNED` |

Y en `test_entities.py`, el test que llamaba `lead.qualify(threshold_qualified=30, threshold_disqualified=0)`
pasa a `lead.qualify()`. Añade uno más:

| Caso | Esperado |
|---|---|
| Un lead con puntuación baja, tras `qualify()` | **`QUALIFIED`**, no `NEW`: el umbral ya no existe y el corte lo pone la banda |

Ese test es el criterio de aceptación 5.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
cd backend && uv run pytest -m unit -q
cd .. && ./scripts/verify-e2e.sh
```

**`verify-e2e.sh` puede ponerse rojo aquí**, y es el único punto de la fase donde se espera. Su
sección «F2a · reglas de puntuación» —la Tarea 2 ya la pasó al contrato nuevo, así que el cuerpo de
las peticiones está bien— comprueba **estados** que el umbral fijo de 30 decidía: un lead que antes
quedaba `NEW` o `DISQUALIFIED` ahora sale `QUALIFIED` y, sin regla de asignación que lo cubra,
`UNASSIGNED`.

**No lo arregles**: lo reescribe la Tarea 5. Anota en tu respuesta la lista concreta de
comprobaciones que fallan, con el valor esperado y el obtenido.

```bash
git commit -m "feat(domain): route by attribute and let the manager own the score cut"
```
