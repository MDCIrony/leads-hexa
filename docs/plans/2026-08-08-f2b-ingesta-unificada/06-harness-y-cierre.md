# Tarea 6 — Harness y documentación

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Cierra la fase: lleva al harness de negocio lo que las tres tareas de API construyeron, y pone la
documentación al día.

## Ficheros

**Modificar:**

| Fichero | Qué cambia |
|---|---|
| `scripts/verify-e2e.sh` | Añade `verify_f2b` y su llamada en `main` |
| `docs/specs/2026-08-07-lead-router-mvp-design.md` | §15: F2b pasa a ✅ con la fecha |
| `docs/specs/2026-08-08-f2b-ingesta-unificada-design.md` | Encabezado: `propuesto` → `implementado` |
| `docs/api/` | Sólo si documenta rutas de ingesta (ver Paso 3) |

**No toques `docs/product/`.** Esa documentación es de negocio y ya describe el modelo objetivo; F2b
lo implementa, no lo cambia.

`verify_f2a` ya quedó adaptado a las rutas autenticadas en la [Tarea 5a](05a-autenticacion.md): quien
rompe, arregla. **No reescribas nada de lo que ya hay**, sólo añade.

## Paso 1: `verify_f2b`

Va donde hoy está el comentario `# ---- next up ---` (`scripts/verify-e2e.sh:190`), sustituyendo su
línea `verify_f2b()` del bloque de pendientes y dejando la de `verify_f2c()`.

Las variables que `bootstrap` exporta y necesitas: `$API`, `$MGR_A`, `$MGR_B`, `$TOKEN_1` (asesor de
la organización A), `$STAMP`. Los helpers son `req`, `code`, `body`, `f`, `check` y `section`, con la
misma forma que usa `verify_f2a`.

| # | Comprobación | Esperado |
|---|---|---|
| 1 | Ingesta sin cabecera de autorización | `401` |
| 2 | Ingesta con token de asesor | `403` |
| 3 | La organización ya tiene sus dos orígenes automáticos | `2` en `GET /sources` |
| 4 | Lead **sin correo** | `201`, y `GET /leads/{id}` lo devuelve con `email: null` |
| 5 | El lead ingerido lleva el `source_id` de la fuente `MANUAL_FORM` | Coinciden |
| 6 | Correo con formato inválido | `400` con `intake_record_id` no vacío |
| 7 | Ese registro sale en `GET /intake/records?status=REJECTED` | Con error de campo `email` |
| 8 | Promoverlo con el correo corregido | `200`, y el lead existe |
| 9 | La bandeja no ganó una fila por el reintento | El mismo total que antes de promover |
| 10 | Carga masiva de un CSV con una fila buena y una mala | Un `PROMOTED` y un `REJECTED` |
| 11 | Un origen de otra organización | `404` |
| 12 | Borrar un origen que tiene leads | `SOURCE_IN_USE` |

Arranque de la función, con el estilo exacto de `verify_f2a`:

```bash
verify_f2b() {
  local r rec src total
  section "F2b · la ingesta exige credencial"

  r=$(req -X POST "$API/intake/leads/ingest" -H 'Content-Type: application/json' \
    -d '{"first_name":"X","last_name":"Y","email":"x@y.test","company":"Acme","industry":"Tech","budget":1000}')
  check "sin credencial no se ingesta" 401 "$(code "$r")"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $TOKEN_1" -H 'Content-Type: application/json' \
    -d '{"first_name":"X","last_name":"Y","email":"x@y.test","company":"Acme","industry":"Tech","budget":1000}')
  check "un asesor no ingesta" 403 "$(code "$r")"

  section "F2b · los orígenes de la organización"

  r=$(req "$API/sources" -H "Authorization: Bearer $MGR_A")
  check "la organización nace con sus dos orígenes" 2 "$(body "$r" | f 'd["total"]')"
  src=$(body "$r" | f '[s["id"] for s in d["items"] if s["kind"] == "MANUAL_FORM"][0]')
```

Para el correo ausente (comprobación 4) el cuerpo simplemente no lleva la clave `email`; comprueba el
`null` con `f 'd.get("email")'`, que imprime vacío cuando el valor es nulo:

```bash
  check "un lead sin correo se acepta" "" "$(body "$r" | f 'd.get("email") or ""')"
```

Para la carga masiva (comprobación 10), un CSV al vuelo y `curl -F`:

```bash
  printf 'first_name,last_name,email,company,industry,budget\nBuena,Fila,ok-%s@x.test,Acme,Tech,5000\nMala,Fila,sin-arroba,Acme,Tech,5000\n' \
    "$STAMP" > /tmp/leads-$STAMP.csv
  r=$(req -X POST "$API/intake/leads/batch-upload" -H "Authorization: Bearer $MGR_A" \
    -F "file=@/tmp/leads-$STAMP.csv")
  check "la fila buena entra" 1 "$(body "$r" | f 'd["successful_ingestions"]')"
  check "la fila mala no se pierde" 1 "$(body "$r" | f 'len(d["failed_rows"])')"
  check "la fila mala deja registro" True "$(body "$r" | f 'bool(d["failed_rows"][0].get("intake_record_id"))')"
  rm -f /tmp/leads-$STAMP.csv
```

`rm` es interactivo en este equipo: usa siempre `rm -f`.

Añade la llamada en `main`, después de `verify_f2a`:

```bash
verify_f2a
verify_f2b
```

## Paso 2: la comprobación que justifica la fase

De las doce, la **9** es la que no puede faltar: que promover un registro no cree una segunda fila en
la bandeja. Es lo que distingue una bandeja de un log de intentos, y ninguna otra comprobación la
cubre. Captura el total antes de promover y compáralo después:

```bash
  total=$(req "$API/intake/records" -H "Authorization: Bearer $MGR_A" | body | f 'd["total"]')
  # ... promover ...
  check "promover no duplica la fila" "$total" "$(req "$API/intake/records" -H "Authorization: Bearer $MGR_A" | body | f 'd["total"]')"
```

## Paso 3: documentación

- `docs/specs/2026-08-07-lead-router-mvp-design.md`, §15: la fila de F2b pasa a ✅ con la fecha de
  cierre.
- `docs/specs/2026-08-08-f2b-ingesta-unificada-design.md`: el encabezado `**Estado:** propuesto` pasa
  a `implementado`.
- Busca con `rg -l 'intake/\{tenant_id\}' docs/` antes de editar nada bajo `docs/api/`. Si no aparece
  nada, no hay rutas que corregir ahí y este punto se cierra sin cambios; si aparece, actualiza esas
  rutas y añade las tres de la bandeja y las cuatro de orígenes.

## Validación de cierre

Ésta sí desde base limpia: es la única tarea de la fase que reejecuta las migraciones desde cero, y
C9 exige que sean idempotentes.

```bash
docker compose down -v && docker compose up -d
docker compose --profile test run --rm backend-test     # suite completa, sin banderas
cd backend && uv run pytest -m unit -q                  # sin base de datos ni variables de entorno
cd .. && ./scripts/verify-e2e.sh --reset                # F2a + F2b en verde
git commit -m "test: cover the unified intake in the business harness"
```
