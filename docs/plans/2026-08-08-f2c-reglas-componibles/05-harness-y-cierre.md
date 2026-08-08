# Tarea 5 — Harness y cierre

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, las tres
> decisiones que el plan cierra, el harness y lo que la fase no hace. Vinculan a esta tarea.

Devuelve el harness de negocio a verde y cierra la fase. **La Tarea 4 anotó en su respuesta qué
comprobaciones fallan**: son las que asumían el umbral fijo de 30.

## Ficheros

**Modificar:**

| Fichero | Qué cambia |
|---|---|
| `scripts/verify-e2e.sh` | Adapta lo que la Tarea 4 rompió y añade `verify_f2c` |
| `docs/specs/2026-08-08-f2c-reglas-componibles-design.md` | `**Estado:** propuesto` → `implementado` |
| `docs/specs/2026-08-07-lead-router-mvp-design.md` | §15: F2c cerrada. §7.0 deja de decir «nuevo en F2c» |
| `docs/api/endpoints.md` | Las rutas de descalificación; los cuerpos de regla llevan `conditions` |
| `docs/api/error_handling.md` | `DISQUALIFICATION_RULE_NOT_FOUND`, `INVALID_RULE_CONDITIONS`, `INVALID_RULE_NAME` |
| `docs/product/02-el-modelo-de-decision.md` | §8: las cuatro carencias que esta fase cierra |

**No toques el resto de `docs/product/`.** Describe el modelo objetivo, no el implementado. La única
excepción es la tabla de §8 de `02`, que es explícitamente un inventario de distancia con lo que hay.

## Paso 1: reparar lo que la Tarea 4 rompió

Sólo las comprobaciones que dependían del umbral fijo. El patrón: un lead que antes se quedaba `NEW`
o caía a `DISQUALIFIED` por puntuación ahora sale `QUALIFIED` y, sin regla de asignación que lo
cubra, `UNASSIGNED`.

**No cambies lo que cada comprobación afirma sobre el negocio** —el score, el desglose, el asesor
asignado, el aislamiento entre organizaciones—, sólo el estado esperado donde el umbral lo decidía.

## Paso 2: `verify_f2c`

Función nueva, llamada desde `main` después de `verify_f2d`. Necesita reglas propias, así que crea
las suyas y las borra al terminar: el harness comparte organización entre bloques y una regla de
descalificación viva envenenaría las comprobaciones de los demás.

| # | Comprobación | Esperado |
|---|---|---|
| 1 | Crear una regla de descalificación con dos condiciones `IS_EMPTY` | `201` |
| 2 | Crear una con `conditions: []` | `400` con `INVALID_RULE_CONDITIONS` |
| 3 | Ingerir un lead **sin teléfono y sin correo** | El lead queda `DISQUALIFIED` |
| 4 | Su motivo | Igual al **nombre de la regla**, no una puntuación |
| 5 | Ingerir un lead **con teléfono y sin correo** | **No** se descalifica |
| 6 | Ingerir un lead **sin teléfono y con correo** | **No** se descalifica |
| 7 | Una regla de otra organización | **404** |
| 8 | Un asesor intenta crear una regla | `403` |
| 9 | Crear una regla de puntuación con dos condiciones | `201`, y un lead que cumple sólo una **no** suma |
| 10 | Regla de asignación con condición de canal | El lead de ese canal va a ese equipo |
| 11 | Un lead de puntuación baja tras procesarse | **Nunca** queda en `NEW` |
| 12 | Borrar las reglas creadas | `204` |

Las comprobaciones 3, 5 y 6 son juntas el criterio de aceptación 1, y son el motivo de que las
condiciones sean una lista. La 11 es el criterio 5.

La ingesta es asíncrona desde F2d: usa `await_job` y resuelve el lead por
`GET /intake/records?job_id=`, como hace `verify_f2d`.

**Cuidado con `f()`:** sólo captura el fallo de `json.load`. Una clave ausente lanza `KeyError` y
deja la variable vacía **sin ningún mensaje**. Usa `d.get(...)` en las expresiones nuevas.

## Paso 3: documentación

- El spec de F2c: `propuesto` → `implementado`
- Maestro §15: fila de F2c como cerrada, con fecha
- Maestro §7.0: quita el «— *nuevo en F2c*» del encabezado, ya no lo es
- `docs/api/endpoints.md`: las cuatro rutas de `/rules/disqualification`, y que los cuerpos de las
  reglas de puntuación y asignación llevan ahora `conditions` en vez de `field`/`operator`/`value`
- `docs/api/error_handling.md`: los tres códigos nuevos con su estado
- `docs/product/02` §8: las cuatro filas que esta fase cierra —etapa de viabilidad, operadores de
  vacío, varias condiciones por regla, reparto por canal— pasan de ❌ a ✅. **Deja como está la de
  identidad del contacto**, que sigue fuera del MVP

## Validación de cierre

Desde base limpia: es la única tarea de la fase que reejecuta las migraciones desde cero, y C9 exige
que sean idempotentes. La 007 lleva un bloque `DO $$` y un `DROP COLUMN` — es exactamente lo que esta
validación comprueba.

```bash
docker compose down -v && docker compose up -d
docker compose --profile test run --rm backend-test     # suite completa, sin banderas
cd backend && uv run pytest -m unit -q                  # sin base de datos ni variables de entorno
cd .. && ./scripts/verify-e2e.sh --reset                # F2a + F2b + F2d + F2c en verde
git commit -m "test: cover composable rules in the business harness"
```
