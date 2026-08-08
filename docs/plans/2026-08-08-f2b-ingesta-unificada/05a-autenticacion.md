# Tarea 5a — La organización sale del token

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

**El único despacho de la fase que rompe comportamiento existente.** Hoy la ingesta responde `201`
sin credencial y la organización sale de la URL, así que cualquiera inyecta leads en cualquier
organización. Esta tarea lo cierra.

**Ficheros:**
- Modificar: `src/infrastructure/adapters/input/api/intake_router.py`,
  `src/infrastructure/main.py`, `src/application/use_cases/ingest_lead_use_case.py`,
  `src/application/use_cases/process_batch_use_case.py`
- Crear: `tests/e2e/test_intake_authentication.py`
- Tests a actualizar: `tests/e2e/test_lead_endpoints.py`, `tests/e2e/test_system_e2e.py`,
  `tests/e2e/test_assignment_flow_e2e.py`, `tests/e2e/test_lead_lifecycle_api.py`
- Harness: `scripts/verify-e2e.sh`

**Produce (lo usan 5b y 5c):** el router de ingesta ya autenticado, con `RequestContext` disponible
en ambos endpoints.

## Paso 1: el prefijo pierde la organización

En `main.py`:

```python
app.include_router(intake_router, prefix="/api/v1/intake", tags=["Intake"])
```

| Antes | Ahora | Acceso |
|---|---|---|
| `POST /api/v1/intake/{tenant_id}/leads/ingest` | `POST /api/v1/intake/leads/ingest` | Gestor |
| `POST /api/v1/intake/{tenant_id}/leads/batch-upload` | `POST /api/v1/intake/leads/batch-upload` | Gestor |

En `intake_router.py`, ambos endpoints cambian la firma: fuera el parámetro `tenant_id: UUID`,
dentro `context: RequestContext = Depends(require_organization_manager)`, y el identificador de la
organización sale de `context.tenant_id`.

Borra los dos comentarios `# Unauthenticated by design until F2 introduces LeadSource credentials`:
esta tarea es justamente lo que anunciaban.

## Paso 2: la fuente se resuelve en el caso de uso

Hoy el router hace `uow.sources.get_by_kind(...)` — la Tarea 1 lo dejó ahí a sabiendas, como
provisional, porque el router aún recibía la organización por la URL.

Ahora baja a `IngestLeadUseCase`, que recibe el `kind` y resuelve la fuente él mismo. Es lo que
exigen C4 y la separación de capas: el adaptador no consulta repositorios.

Si no encuentra fuente activa para ese `kind`, `DomainException(error_code="SOURCE_NOT_FOUND")`.
**Hoy ese caso revienta con un `AttributeError` y un 500 crudo**, señalado como riesgo al cerrar la
Tarea 1; esta tarea lo convierte en un error limpio.

`ProcessBatchUseCase` propaga el mismo cambio: deja de recibir `source_id` desde fuera.

## Paso 3: los cuatro e2e existentes

Usan la ruta vieja y sin token. Actualízalos: ruta nueva y cabecera `Authorization: Bearer` de un
gestor. **No cambies lo que afirman** — sólo cómo llaman.

`test_lead_endpoints.py` ya tiene un helper `_seed_tenant_with_sources` y otro
`_manager_auth_headers` de la Tarea 1; reutilízalos en vez de escribir otros.

## Paso 4: el harness

`scripts/verify-e2e.sh` llama a `$API/intake/$TENANT_A/leads/ingest` sin token, así que esta tarea
lo rompe. Cambia **sólo la ruta y la cabecera** en `verify_f2a`, no las comprobaciones:

```bash
r=$(req -X POST "$API/intake/leads/ingest" -H 'Content-Type: application/json' \
      -H "Authorization: Bearer $TOKEN_MANAGER_A" -d '...')
```

Va aquí y no en la Tarea 6 por una razón práctica: quien rompe, arregla. Si se deja para el final,
las tareas 5b y 5c se quedan sin validación de negocio.

## Tests nuevos — `test_intake_authentication.py`

| Caso | Esperado |
|---|---|
| `POST /api/v1/intake/leads/ingest` sin cabecera | 401 |
| Con token de asesor (rol `AGENT`) | 403 |
| Con token de gestor | 201, y el lead queda en **su** organización |
| El cuerpo trae un `tenant_id` de otra organización | Se ignora; el lead cae en la del token |

El último es el que demuestra C4: la organización sale de la credencial y de ningún otro sitio.

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
./scripts/verify-e2e.sh
git commit -m "feat(api): close the intake behind a credential"
```
