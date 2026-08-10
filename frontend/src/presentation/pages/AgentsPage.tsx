import { useState } from 'react';
import * as agentsService from '../../application/services/agents.service';
import * as groupsService from '../../application/services/groups.service';
import { useAsync } from '../../application/data/use-async';
import { usePaginated } from '../../application/data/use-paginated';
import { AsyncView } from '../components/ui/AsyncView';
import { AgentSettings } from '../components/AgentSettings';
import { Button } from '../components/ui/Button';

/**
 * GET /agents only returns active agents when `is_active` is absent — the
 * checkbox is the only way to reach a deactivated one and reactivate it.
 */
export function AgentsPage() {
  const [showInactive, setShowInactive] = useState(false);

  // Groups are an optional selector, not a gate: a failed or slow fetch
  // shouldn't block the agents list from rendering.
  const { data: groupsPage } = useAsync(() => groupsService.list(100, 0), []);
  const groups = groupsPage?.items ?? [];

  const paginated = usePaginated(
    (limit, offset) => agentsService.list(limit, offset, showInactive ? { isActive: false } : {}),
    { deps: [showInactive] }
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">Asesores</h2>
          <p className="text-sm text-slate-400">Alta, edición y control de acceso de los asesores de la organización.</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded border-slate-700 bg-slate-950"
          />
          Ver desactivados
        </label>
      </div>

      <AsyncView
        state={{ data: paginated.items, error: paginated.error, loading: paginated.loading, refetch: paginated.refetch }}
        emptyText={showInactive ? 'No hay asesores desactivados.' : 'No hay asesores activos.'}
        isEmpty={(items) => items.length === 0}
      >
        {(agents) => (
          <div className="space-y-4">
            <AgentSettings
              agents={agents}
              groups={groups}
              onCreate={async (body) => {
                await agentsService.create(body);
                paginated.refetch();
              }}
              onUpdate={async (id, body) => {
                await agentsService.update(id, body);
                paginated.refetch();
              }}
              onDeactivate={async (id) => {
                await agentsService.deactivate(id);
                paginated.refetch();
              }}
              onReactivate={async (id) => {
                await agentsService.update(id, { is_active: true });
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
