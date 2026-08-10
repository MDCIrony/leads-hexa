# Frontend

Interfaz web del enrutador de leads. Ver [`frontend/CLAUDE.md`](CLAUDE.md) para cómo se trabaja aquí.

## Contrato de la API

`src/infrastructure/api/schema.d.ts` se regenera con `npm run gen:api` (necesita el backend en
`:8001`) y **nunca se edita a mano**.

## Tests

```bash
npm run test
```

Corre con `vitest` en entorno `jsdom` y **no necesita el backend levantado**: toda llamada HTTP en
un test pasa por `apiClient`, simulado con `mockApiClient` (`src/test/mock-api.ts`) sobre fixtures
capturadas de verdad, nunca escritas a mano.

Dos ayudantes en `src/test/` para cualquier test de vista:

- `renderWithProviders(ui, { role })` — monta el enrutador y una sesión ya resuelta al rol pedido,
  sin pasar por el formulario de login.
- `mockApiClient({ 'GET /api/v1/leads': { data: fixture } })` — sustituye `apiClient` por un router
  de "MÉTODO ruta" que devuelve la fixture o el sobre de error que el test necesite.

`src/test/render.test.tsx` es el ejemplo mínimo de los dos juntos.

## Fixtures

```bash
npm run gen:fixtures
```

Necesita el backend en `:8001`. Monta un escenario mínimo (organización, gestor, asesor, dos reglas
y un lead ingerido) sufijado con una marca temporal, y graba cada respuesta real en
`src/test/fixtures/*.json`. Se vuelve a correr cuando el contrato del backend cambie: el diff de las
fixtures enseña qué cambió.
