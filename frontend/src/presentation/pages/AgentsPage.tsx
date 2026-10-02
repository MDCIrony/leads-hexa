import { useState } from 'react';
import * as agentsService from '../../application/services/agents.service';
import { usePaginated } from '../../application/data/use-paginated';
import { useSession } from '../../application/session/use-session';
import { AsyncView } from '../components/ui/AsyncView';
import { AgentSettings } from '../components/AgentSettings';
import { AgentForm } from '../components/AgentForm';
import { Button } from '../components/ui/Button';

/**
 * GET /agents only returns active agents when `is_active` is absent — the
 * checkbox is the only way to reach a deactivated one and reactivate it.
 */
export function AgentsPage() {
  const [showInactive, setShowInactive] = useState(false);
  const { user } = useSession();

  const paginated = usePaginated(
    (limit, offset) => agentsService.list(limit, offset, showInactive ? { isActive: false } : {}),
    { deps: [showInactive] }
  );

  // The endpoint takes no role filter, so it hands back the whole organization,
  // signed-in manager included. Nobody deactivates themselves from this screen.
  const others = paginated.items.filter((agent) => agent.id !== user?.id);

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

      {/* Outside AsyncView: an organization with only its manager renders the empty state, which would take the form with it. */}
      <AgentForm
        onCreate={async (body) => {
          await agentsService.create(body);
          paginated.refetch();
        }}
      />

      <AsyncView
        state={{ data: others, error: paginated.error, loading: paginated.loading, refetch: paginated.refetch }}
        emptyText={showInactive ? 'No hay asesores desactivados.' : 'No hay asesores activos.'}
        isEmpty={(items) => items.length === 0}
      >
        {(agents) => (
          <div className="space-y-4">
            <AgentSettings
              agents={agents}
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
                {/* The signed-in manager is active by definition, so they only inflate the active listing. */}
                Página {paginated.page + 1} • {showInactive ? paginated.total : paginated.total - 1} en total
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
