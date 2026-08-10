import { describe, expect, it } from 'vitest';
import { mockApiClient } from '../../test/mock-api';
import sourcesPage from '../../test/fixtures/sources-page.json';
import { create, list, remove } from './sources.service';

describe('sources.list', () => {
  it('returns the paginated envelope intact', async () => {
    mockApiClient({ 'GET /api/v1/sources': { data: sourcesPage } });

    const page = await list(20, 0);

    expect(page.total).toBe(sourcesPage.total);
    // A fresh organization is seeded with both source kinds — asserting on the second
    // item's kind rather than the first keeps this stable if the seed order changes.
    expect(page.items[1].kind).toBe('MANUAL_FORM');
  });
});

describe('sources.create and sources.remove', () => {
  it('creates and deletes without reshaping the payload', async () => {
    const sourceId = sourcesPage.items[0].id;
    mockApiClient({
      'POST /api/v1/sources': { status: 201, data: sourcesPage.items[0] },
      [`DELETE /api/v1/sources/${sourceId}`]: { status: 204, data: undefined },
    });

    const source = await create({ name: 'Formulario manual', kind: 'MANUAL_FORM' });
    expect(source.id).toBe(sourceId);

    await expect(remove(source.id)).resolves.toBeUndefined();
  });
});
