# Tarea 5b — CRUD de orígenes

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

Aditiva: no cambia nada existente. Es lo que permite al gestor responder «¿de dónde vienen mis
leads?», que es el criterio de aceptación 5 de la fase.

**Ficheros:**
- Crear: `src/application/ports/input/lead_source_use_case_ports.py`,
  `src/application/use_cases/lead_source_use_cases.py`,
  `src/infrastructure/adapters/input/api/source_router.py`,
  `tests/e2e/test_source_endpoints.py`
- Modificar: `src/infrastructure/adapters/input/api/schemas.py`,
  `src/infrastructure/adapters/input/api/dependencies.py`, `src/infrastructure/main.py`

**Consume de tareas previas:** `LeadSource`, `LeadSourceKind`, `uow.sources` con
`get_by_id_and_tenant`, `get_by_kind`, `list_by_tenant`, `save` y `delete`. La organización ya crea
sus dos orígenes automáticos al darse de alta.

## Paso 1: casos de uso

En `lead_source_use_cases.py`, uno por operación con el patrón exacto de `sales_group_use_cases.py`:
`Create`, `Get` (lista paginada), `Update`, `Delete`. Todos reciben el `RequestContext` y filtran
por `context.tenant_id`.

**C5 aplica:** leer, modificar o borrar un origen de otra organización devuelve **404**, no 403. Se
consigue con `get_by_id_and_tenant`, que no encuentra nada y por tanto no confirma que exista.

**`DELETE` sobre un origen con leads asociados** debe fallar con
`DomainException(error_code="SOURCE_IN_USE")`. Sin esa comprobación, la clave foránea de
`leads.source_id` revienta con un error de base de datos que sale como 500. Una consulta de recuento
antes de borrar basta.

## Paso 2: esquemas

En `schemas.py`, al estilo de los de grupo: `LeadSourceCreate`, `LeadSourceUpdate` y
`LeadSourceResponse` con `id`, `name`, `kind`, `field_mapping`, `is_active` y `created_at`.

**`secret_hash` no se expone nunca**, en ninguna respuesta. Existe para que F3b autentique fuentes
externas por firma; publicarlo anularía su único propósito.

## Paso 3: router y cableado

Router nuevo `source_router.py`, montado en `main.py`:

```python
app.include_router(source_router, prefix="/api/v1/sources", tags=["Sources"])
```

| Método | Ruta | Acceso |
|---|---|---|
| `GET·POST` | `/api/v1/sources` | Gestor |
| `PATCH·DELETE` | `/api/v1/sources/{id}` | Gestor |

Proveedores en `dependencies.py` siguiendo el patrón de `get_create_sales_group_use_case`.
`container.py` **no** construye casos de uso; todos viven en `dependencies.py`.

## Tests — `test_source_endpoints.py`

| Caso | Esperado |
|---|---|
| Una organización recién creada ya lista sus dos orígenes automáticos | 200 con `MANUAL_FORM` y `FILE_UPLOAD` |
| Crear un origen con nombre repetido en la misma organización | Error, no una segunda fila |
| `GET`, `PATCH` y `DELETE` de un origen de otra organización | **404** en los tres |
| Borrar un origen que tiene leads | `SOURCE_IN_USE`, no un 500 |
| Ninguna respuesta contiene `secret_hash` | Comprobación explícita sobre el cuerpo |

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
./scripts/verify-e2e.sh
git commit -m "feat(api): let the manager see and edit where leads come from"
```
