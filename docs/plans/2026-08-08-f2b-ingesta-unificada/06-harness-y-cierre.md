# Tarea 6 — Harness y documentación

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

**Ficheros:** `scripts/verify-e2e.sh`, `docs/specs/2026-08-07-lead-router-mvp-design.md`,
`docs/specs/2026-08-08-f2b-ingesta-unificada-design.md`, `docs/api/` si documenta las rutas de
ingesta.

`verify_f2a` ya quedó adaptado a las rutas autenticadas en la [Tarea 5a](05a-autenticacion.md):
quien rompe, arregla. Aquí sólo se añade la función nueva.

## Paso 1: `verify_f2b`

Rellena la función que ya está esbozada en `scripts/verify-e2e.sh:191`, con el estilo de
`verify_f2a` —helpers `req`, `code`, `body`, `f`, `check`, `section`—. Añade la llamada en `main`
después de `verify_f2a`. **No reescribas nada de lo que ya hay.**

| # | Comprobación |
|---|---|
| 1 | Ingesta sin token → 401 |
| 2 | Ingesta con token de asesor → 403 |
| 3 | La organización recién creada ya tiene sus dos fuentes en `GET /sources` |
| 4 | Lead **sin correo** → 201, y `GET /leads/{id}` lo devuelve con `email: null` |
| 5 | Correo con formato inválido → 400 con `intake_record_id` no vacío |
| 6 | Ese registro aparece en `GET /intake/records?status=REJECTED` con el error de campo `email` |
| 7 | Promoverlo con el correo corregido → 200, y el lead existe |
| 8 | Carga masiva de un CSV con una fila buena y una mala → un `PROMOTED` y un `REJECTED` |
| 9 | Fuente de otra organización → **404** |
| 10 | El lead ingerido lleva el `source_id` de la fuente `MANUAL_FORM` |

## Paso 2: documentación

- `docs/specs/2026-08-07-lead-router-mvp-design.md` §15: F2b pasa a ✅ con la fecha.
- El spec de F2b: encabezado `**Estado:** propuesto` → `implementado`.
- Si `docs/api/` documenta `/intake/{tenant_id}/...`, actualiza las rutas y añade las nuevas.

**No toques `docs/product/`.** Esa documentación es de negocio y ya describe el modelo objetivo;
F2b lo implementa, no lo cambia.

## Validación de cierre

```bash
docker compose down -v && docker compose up -d
docker compose --profile test run --rm backend-test     # suite completa, sin banderas
cd backend && uv run pytest -m unit -q                  # sin variables de entorno
./scripts/verify-e2e.sh --reset                         # F2a + F2b en verde
git commit -m "test: cover the unified intake in the business harness"
```

---

