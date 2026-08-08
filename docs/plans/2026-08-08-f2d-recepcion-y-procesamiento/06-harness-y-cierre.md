# Tarea 6 — Harness y cierre

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Devuelve el harness de negocio a verde y cierra la fase. **`verify-e2e.sh` lleva en rojo desde la
Tarea 3**, a propósito: las tareas 3, 4 y 5 anotaron en su respuesta qué comprobaciones fallan, para
reescribir el bloque una sola vez en lugar de tres.

## Ficheros

**Modificar:**

| Fichero | Qué cambia |
|---|---|
| `scripts/verify-e2e.sh` | Adapta las comprobaciones de ingesta de `verify_f2a` y `verify_f2b`, y añade `verify_f2d` |
| `docs/specs/2026-08-07-lead-router-mvp-design.md` | §15: F2d entra en la tabla de fases como cerrada |
| `docs/specs/2026-08-08-f2d-recepcion-y-procesamiento-design.md` | `**Estado:** propuesto` → `implementado` |
| `docs/api/endpoints.md` | Las rutas de ingesta responden `202`; añade jobs y reproceso |
| `docs/api/error_handling.md` | Los códigos nuevos de esta fase |

**No toques `docs/product/`.** Es documentación de negocio y describe el modelo objetivo.

## Paso 1: el sondeo

Es lo único de esta tarea que no existe en el harness. `TestClient` ejecuta las tareas de fondo antes
de devolver el control, pero `verify-e2e.sh` habla **HTTP real** contra el contenedor: ahí el trabajo
corre de verdad después de responder.

Añade un helper junto a los demás (`req`, `code`, `body`, `f`, `check`, `section`):

```bash
# await_job <token> <job_id> — espera a que un trabajo alcance estado terminal.
# Sondeo con tope, nunca un sleep fijo: un sleep corto vuelve el harness
# intermitente y uno largo lo vuelve inútil.
await_job() {
  local i r st
  for i in $(seq 1 30); do
    r=$(req "$API/intake/jobs/$2" -H "Authorization: Bearer $1")
    st=$(body "$r" | f 'd.get("status")')
    case "$st" in COMPLETED|FAILED) printf '%s' "$st"; return 0 ;; esac
    sleep 0.2
  done
  printf 'TIMEOUT'
}
```

Devuelve el estado alcanzado, así que un job que no termina se ve como `TIMEOUT` en la comprobación
que lo esperaba, en vez de como un fallo confuso más abajo.

## Paso 2: adaptar `verify_f2a` y `verify_f2b`

**Sólo las llamadas de ingesta**, no las comprobaciones de negocio. El patrón:

```bash
# antes
r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" ... )
check "el lead entra" 201 "$(code "$r")"
LEAD=$(body "$r" | f 'd["lead_id"]')

# después
r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" ... )
check "el lead se acepta" 202 "$(code "$r")"
job=$(body "$r" | f 'd["job_id"]')
check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
LEAD=$(body "$r" | f 'd["items"][0]["lead_id"]')
```

Todo lo que venía después —el score, el estado, el asesor asignado, el aislamiento entre
organizaciones— **se queda exactamente igual**. Lo único que cambia es de dónde sale `$LEAD`.

En `verify_f2b`, la comprobación del correo mal formado cambia de sentido: ya no da `400`, da `202` y
el registro queda `REJECTED`. Es lo que V1 buscaba y conviene que el harness lo afirme explícitamente.

## Paso 3: `verify_f2d`

Función nueva, llamada desde `main` después de `verify_f2b`.

| # | Comprobación | Esperado |
|---|---|---|
| 1 | Ingesta unitaria | `202` con `job_id` |
| 2 | El trabajo termina | `COMPLETED` con `total_items=1`, `succeeded=1` |
| 3 | Su registro lleva el lead, y el lead existe | `PROMOTED` con `lead_id` |
| 4 | Carga masiva de un CSV con una fila buena y una mala | `202` con `job_id` |
| 5 | El trabajo termina con los contadores correctos | `total_items=2`, `succeeded=1`, `failed=1` |
| 6 | Sus registros | Uno `PROMOTED`, uno `REJECTED` con error de campo `email` |
| 7 | Un correo mal formado ya no se pierde | `202`, y el registro queda `REJECTED` |
| 8 | Un fichero ilegible | El trabajo queda `FAILED`, sin registros y sin 500 |
| 9 | Consultar un trabajo de otra organización | **404** |
| 10 | Reprocesar un trabajo ya `COMPLETED` | `INVALID_JOB_TRANSITION` |

Para la 7, el correo tiene que ser **`jane@@example.com`** y no algo como `sin-arroba`: sin la
validación del esquema que la Tarea 3 retiró, ambos llegan al dominio, pero conviene usar el mismo
valor que el resto de la suite para que el caso sea comparable.

Para la 8, bastan unos bytes que no son un fichero tabular:

```bash
printf 'esto no es un csv ni un xlsx\x00\x01\x02' > /tmp/basura-$STAMP.bin
```

`rm` es interactivo en este equipo: usa `rm -f`.

## Paso 4: documentación

- `docs/specs/2026-08-07-lead-router-mvp-design.md` §15: añade la fila de F2d como cerrada, con
  fecha, y ajusta el orden respecto a F2c —F2d va antes—.
- El spec de F2d: `propuesto` → `implementado`.
- `docs/api/endpoints.md`: las dos rutas de ingesta pasan a `202` con `job_id` y `record_ids`; añade
  la sección de trabajos con sus tres rutas.
- `docs/api/error_handling.md`: añade `INTAKE_JOB_NOT_FOUND` (404), `INVALID_JOB_TRANSITION` (400) e
  `INVALID_JOB_STATUS` (400) a la tabla.

## Validación de cierre

Desde base limpia: es la única tarea de la fase que reejecuta las migraciones desde cero, y C9 exige
que sean idempotentes.

```bash
docker compose down -v && docker compose up -d
docker compose --profile test run --rm backend-test     # suite completa, sin banderas
cd backend && uv run pytest -m unit -q                  # sin base de datos ni variables de entorno
cd .. && ./scripts/verify-e2e.sh --reset                # F2a + F2b + F2d en verde
git commit -m "test: cover the two-phase intake in the business harness"
```
