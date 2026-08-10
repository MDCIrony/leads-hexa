import { useState } from 'react';
import * as tenantsService from '../../application/services/tenants.service';
import { usePaginated } from '../../application/data/use-paginated';
import { AsyncView } from '../components/ui/AsyncView';
import { TenantSettings } from '../components/TenantSettings';
import { Button } from '../components/ui/Button';

/**
 * GET /tenants comes newest-first already — this view never reorders.
 *
 * The just-created manager's email is tracked here, above AsyncView: a
 * refetch briefly flips the page into its loading state, which unmounts
 * everything AsyncView renders — a banner kept inside that subtree would
 * disappear right after the one moment it needs to be seen.
 */
export function OrganizationsPage() {
  const paginated = usePaginated((limit, offset) => tenantsService.list(limit, offset));
  const [createdManagerEmail, setCreatedManagerEmail] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Organizaciones</h2>
        <p className="text-sm text-slate-400">Alta de organizaciones y de su primer gestor, y control de acceso.</p>
      </div>

      {createdManagerEmail && (
        <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-sm text-emerald-300">
          Organización creada. Su gestor entra con <strong>{createdManagerEmail}</strong> y la contraseña que
          acabas de escribir — comunícasela, porque no vuelve a mostrarse.
        </div>
      )}

      <AsyncView
        state={{ data: paginated.items, error: paginated.error, loading: paginated.loading, refetch: paginated.refetch }}
        emptyText="No hay organizaciones dadas de alta."
        isEmpty={(items) => items.length === 0}
      >
        {(tenants) => (
          <div className="space-y-4">
            <TenantSettings
              tenants={tenants}
              onCreate={async (body) => {
                const tenant = await tenantsService.create(body);
                setCreatedManagerEmail(tenant.manager?.email ?? null);
                paginated.refetch();
                return tenant;
              }}
              onUpdate={async (id, body) => {
                await tenantsService.update(id, body);
                paginated.refetch();
              }}
            />

            <div className="flex items-center justify-between text-sm text-slate-400">
              <span>
                Página {paginated.page + 1} • {paginated.total} en total
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={paginated.previousPage} disabled={paginated.page === 0}>
                  Anterior
                </Button>
                <Button variant="secondary" onClick={paginated.nextPage} disabled={!paginated.hasMore}>
                  Siguiente
                </Button>
              </div>
            </div>
          </div>
        )}
      </AsyncView>
    </div>
  );
}
